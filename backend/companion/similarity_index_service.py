"""Durable library-wide Appearance fingerprint maintenance."""

from __future__ import annotations

import asyncio
import logging
from hashlib import sha256
from pathlib import Path
from tempfile import SpooledTemporaryFile
from time import perf_counter
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.duplicate_schema import SimilarityIndexCoverage, SimilarityIndexTaskStart
from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset
from companion.integrity import detect_file_format
from companion.integrity_service import INTEGRITY_TASK_TYPE
from companion.similarity_features import decode_and_extract_features
from companion.similarity_search_features import (
    MAX_SEARCH_PREVIEW_BYTES,
    SEARCH_CONFIG_FINGERPRINT,
    SEARCH_FEATURE_VERSION,
    SEARCH_MODEL_VERSION,
    extract_search_feature,
)
from companion.similarity_search_repository import SimilaritySearchRepository
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult

SIMILARITY_INDEX_TASK_TYPE = "similarity_index"
SIMILARITY_FINGERPRINT_BATCH_SIZE = 25
ORIGINAL_FALLBACK_MAX_BYTES = 128 * 1024 * 1024

logger = logging.getLogger("uvicorn.error")


class SimilarityIndexMaintainer:
    """Select and commit only missing or stale synchronized image features."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        features: SimilaritySearchRepository,
        *,
        batch_size: int = SIMILARITY_FINGERPRINT_BATCH_SIZE,
        fetch_slots: int = 2,
        decode_slots: int = 2,
        fallback_max_bytes: int = ORIGINAL_FALLBACK_MAX_BYTES,
        decode_cache_path: Path | None = None,
    ) -> None:
        if min(batch_size, fetch_slots, decode_slots, fallback_max_bytes) < 1:
            raise ValueError("Fingerprint batch and pipeline slots must be positive")
        self._immich = immich
        self._assets = assets
        self._features = features
        self._batch_size = batch_size
        self._fetch_slots = asyncio.Semaphore(fetch_slots)
        self._decode_slots = asyncio.Semaphore(decode_slots)
        self._inflight_slots = asyncio.Semaphore(fetch_slots + decode_slots)
        self._fallback_max_bytes = fallback_max_bytes
        self._decode_cache_path = decode_cache_path
        self._metrics: dict[str, int] = {}

    def _measure(self, phase: str, started: float) -> None:
        key = f"{phase}_milliseconds"
        self._metrics[key] = self._metrics.get(key, 0) + round(
            (perf_counter() - started) * 1000
        )

    def _count(self, key: str, value: int = 1) -> None:
        self._metrics[key] = self._metrics.get(key, 0) + value

    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)

    async def _original_fallback(self, context: TaskContext, asset_id: UUID):
        """Extract coarse evidence from a bounded original without integrity hashing."""

        with SpooledTemporaryFile(
            max_size=4 * 1024 * 1024, dir=self._decode_cache_path, suffix=".tmp"
        ) as spool:
            digest = sha256(usedforsecurity=False)
            prefix = bytearray()
            total = 0
            started = perf_counter()
            async with self._immich.stream_original(asset_id) as original:
                if (
                    original.content_length is not None
                    and original.content_length > self._fallback_max_bytes
                ):
                    raise ValueError("original exceeds similarity fallback size limit")
                async for chunk in original.chunks:
                    await context.ensure_active()
                    total += len(chunk)
                    if total > self._fallback_max_bytes:
                        raise ValueError("original exceeds similarity fallback size limit")
                    if len(prefix) < 64:
                        prefix.extend(chunk[:64 - len(prefix)])
                    digest.update(chunk)
                    spool.write(chunk)
            self._measure("original_fetch", started)
            self._count("original_bytes_downloaded", total)
            started = perf_counter()
            decoded, feature = await asyncio.to_thread(
                decode_and_extract_features,
                spool,
                detect_file_format(bytes(prefix)),
                include_pixel_hash=False,
            )
            self._measure("feature_extraction", started)
            self._count("original_decodes")
            if decoded.valid is not True or feature is None:
                raise ValueError("original could not produce coarse visual evidence")
            return feature, digest.hexdigest()

    async def _fingerprint_page(
        self, context: TaskContext, page: list[UUID], *, attempt: str
    ) -> list[tuple[bool, str | None]]:
        started = perf_counter()
        known = await self._assets.get_immich_assets(page)
        self._measure("metadata_preparation", started)
        tasks = [
            asyncio.create_task(
                self._fingerprint(context, asset_id, known.get(asset_id), attempt=attempt)
            )
            for asset_id in page
        ]
        try:
            return await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def coverage(self) -> SimilarityIndexCoverage:
        eligible, current, missing, stale = await self._features.coverage()
        return SimilarityIndexCoverage(
            eligible_count=eligible,
            current_count=current,
            missing_count=missing,
            stale_count=stale,
            complete=missing == 0 and stale == 0,
            model_version=SEARCH_MODEL_VERSION,
            feature_version=SEARCH_FEATURE_VERSION,
            config_fingerprint=SEARCH_CONFIG_FINGERPRINT,
        )

    async def maintain(
        self,
        context: TaskContext,
        *,
        progress_ceiling: float = 100.0,
    ) -> tuple[SimilarityIndexCoverage, int, int, set[UUID], dict[UUID, str]]:
        """Fingerprint missing assets, retry once, and report per-asset failures."""

        initial = await self.coverage()
        self._metrics = {
            "fingerprints_reused": initial.current_count,
            "preview_fingerprints_generated": 0,
            "original_fingerprints_generated": 0,
            "fallbacks_to_original": 0,
            "deep_verifications_performed": 0,
            "failed_or_skipped_attempts": 0,
            "preview_bytes_downloaded": 0,
            "original_bytes_downloaded": 0,
        }
        task = getattr(context, "task", None)
        saved = dict(getattr(task, "checkpoint", {}) or {})
        after = (
            UUID(str(saved["cursor"]))
            if saved.get("phase") == "similarity_fingerprinting" and saved.get("cursor")
            else None
        )
        total = initial.missing_count + initial.stale_count
        completed = 0
        unavailable = 0
        if total == 0 and saved.get("phase") in {"candidate_index", "scoring"}:
            # Preserve the scan's resumable candidate/scoring checkpoint.
            return initial, 0, 0, set(), {}
        await context.checkpoint(
            checkpoint={
                "phase": "similarity_fingerprinting",
                "cursor": str(after) if after else None,
            },
            counters={
                "eligible_images": initial.eligible_count,
                "current_fingerprints": initial.current_count,
                "fingerprints_pending": total,
                "fingerprints_completed": 0,
                "fingerprints_unavailable": 0,
            },
            progress={
                "phase": "similarity_fingerprinting",
                "completed": 0,
                "total": total,
                "percent": 0.0 if total else progress_ceiling,
                "detail": (
                    f"Preparing {total} missing or stale library fingerprints…"
                    if total
                    else "Every eligible synchronized image has a current fingerprint."
                ),
            },
        )
        while True:
            await context.ensure_active()
            page = await self._features.list_work(
                after_asset_id=after,
                limit=self._batch_size,
            )
            if not page:
                break
            results = await self._fingerprint_page(context, page, attempt="initial")
            for succeeded, _ in results:
                if succeeded:
                    completed += 1
                else:
                    unavailable += 1
            after = page[-1]
            done = min(total, completed + unavailable)
            await context.checkpoint(
                checkpoint={
                    "phase": "similarity_fingerprinting",
                    "cursor": str(after),
                },
                counters={
                    "eligible_images": initial.eligible_count,
                    "current_fingerprints": initial.current_count + completed,
                    "fingerprints_pending": max(0, total - done),
                    "fingerprints_completed": completed,
                    "fingerprints_unavailable": unavailable,
                },
                progress={
                    "phase": "similarity_fingerprinting",
                    "completed": done,
                    "total": total,
                    "percent": round(done / max(1, total) * progress_ceiling, 1),
                    "detail": f"Processed {done} of {total} required library fingerprints.",
                },
            )
        retry_coverage = await self.coverage()
        retry_total = retry_coverage.missing_count + retry_coverage.stale_count
        retry_attempted: set[UUID] = set()
        retry_failures: dict[UUID, str] = {}
        retry_completed = 0
        if retry_total:
            await context.checkpoint(
                checkpoint={"phase": "similarity_fingerprint_retry"},
                counters={
                    "eligible_images": retry_coverage.eligible_count,
                    "current_fingerprints": retry_coverage.current_count,
                    "fingerprints_pending": retry_total,
                    "fingerprints_completed": completed,
                    "fingerprints_unavailable": retry_total,
                },
                progress={
                    "phase": "similarity_fingerprinting",
                    "completed": 0,
                    "total": retry_total,
                    "percent": progress_ceiling,
                    "detail": f"Retrying {retry_total} remaining library fingerprints once…",
                },
            )
            retry_after: UUID | None = None
            while True:
                await context.ensure_active()
                page = await self._features.list_work(
                    after_asset_id=retry_after,
                    limit=self._batch_size,
                )
                if not page:
                    break
                results = await self._fingerprint_page(context, page, attempt="retry")
                for asset_id, (succeeded, reason) in zip(page, results, strict=True):
                    retry_attempted.add(asset_id)
                    if succeeded:
                        retry_completed += 1
                    elif reason is not None:
                        retry_failures[asset_id] = reason
                retry_after = page[-1]
                await context.checkpoint(
                    checkpoint={
                        "phase": "similarity_fingerprint_retry",
                        "cursor": str(retry_after),
                    },
                    counters={
                        "eligible_images": retry_coverage.eligible_count,
                        "current_fingerprints": retry_coverage.current_count + retry_completed,
                        "fingerprints_pending": max(0, retry_total - len(retry_attempted)),
                        "fingerprints_completed": completed + retry_completed,
                        "fingerprints_unavailable": max(0, len(retry_attempted) - retry_completed),
                    },
                    progress={
                        "phase": "similarity_fingerprinting",
                        "completed": len(retry_attempted),
                        "total": retry_total,
                        "percent": progress_ceiling,
                        "detail": f"Retried {len(retry_attempted)} of {retry_total} fingerprints.",
                    },
                )
        final = await self.coverage()
        return (
            final,
            completed + retry_completed,
            final.missing_count + final.stale_count,
            retry_attempted,
            retry_failures if not final.complete else {},
        )

    async def _fingerprint(
        self, context: TaskContext, asset_id: UUID, source: ImmichAsset | None, *, attempt: str
    ) -> tuple[bool, str | None]:
        async with self._inflight_slots:
            await context.ensure_active()
            return await self._fingerprint_unbounded(context, asset_id, source, attempt=attempt)

    async def _fingerprint_unbounded(
        self, context: TaskContext, asset_id: UUID, source: ImmichAsset | None, *, attempt: str
    ) -> tuple[bool, str | None]:
        try:
            if source is None:
                self._count("failed_or_skipped_attempts")
                return False, "asset is no longer synchronized"
            if source.file_size_bytes is None:
                # Some synchronization payloads omit size. Enrich once before
                # fetching media so a missing size cannot force a second preview.
                async with self._fetch_slots:
                    started = perf_counter()
                    source = await self._immich.get_asset(asset_id)
                    await self._assets.refresh_asset(
                        source, track_similarity_changes=False
                    )
                    self._measure("metadata_preparation", started)
            preview = None
            preview_error: Exception | None = None
            async with self._fetch_slots:
                if not (source.is_trashed or source.is_offline or source.asset_type != "IMAGE"):
                    started = perf_counter()
                    try:
                        preview = await self._immich.get_bounded_preview(
                            asset_id, max_bytes=MAX_SEARCH_PREVIEW_BYTES
                        )
                        self._count("preview_bytes_downloaded", len(preview))
                    except ImmichApiError as error:
                        preview_error = error
                    finally:
                        self._measure("preview_fetch", started)
            if source.is_trashed or source.is_offline or source.asset_type != "IMAGE":
                reason = (
                    "asset is trashed" if source.is_trashed else
                    "asset is offline" if source.is_offline else
                    f"asset type is {source.asset_type}, not IMAGE"
                )
                logger.warning(
                    "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                    asset_id, attempt, reason,
                )
                self._count("failed_or_skipped_attempts")
                return False, reason
            feature = None
            if preview is not None:
                async with self._decode_slots:
                    started = perf_counter()
                    feature = await asyncio.to_thread(extract_search_feature, preview)
                    self._measure("feature_extraction", started)
                    self._count("preview_decodes")
            origin = "preview"
            if feature is None:
                self._count("fallbacks_to_original")
                try:
                    # Hold both limits: at most the configured number of original
                    # streams and decodes, with each spool capped on disk.
                    async with self._fetch_slots, self._decode_slots:
                        feature, media_digest = await self._original_fallback(context, asset_id)
                    origin = "original"
                except (ImmichApiError, ValueError, OSError) as error:
                    reason = f"preview unavailable ({preview_error}); fallback failed: {error}"
                    logger.warning(
                        "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                        asset_id, attempt, reason,
                    )
                    self._count("failed_or_skipped_attempts")
                    return False, reason
            else:
                media_digest = sha256(preview, usedforsecurity=False).hexdigest()
            await context.ensure_active()
            # Compare the batched synchronized before-image with one live lookup
            # after media retrieval; save also guards the synchronized row.
            async with self._fetch_slots:
                started = perf_counter()
                current = await self._immich.get_asset(asset_id)
                self._measure("metadata_preparation", started)
            if not self._same_source(source, current):
                if not current.is_trashed:
                    await self._assets.refresh_asset(
                        current, track_similarity_changes=False
                    )
                reason = "Immich source changed while search evidence was generated"
                self._count("failed_or_skipped_attempts")
                return False, reason
            started = perf_counter()
            if await self._features.save(source, media_digest, feature, origin=origin):
                self._measure("db_persistence", started)
                self._count(
                    "preview_fingerprints_generated"
                    if origin == "preview" else "original_fingerprints_generated"
                )
                return True, None
            self._measure("db_persistence", started)
            reason = "synchronized source changed while preview evidence was being generated"
            logger.warning(
                "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                asset_id, attempt, reason,
            )
            self._count("failed_or_skipped_attempts")
            return False, reason
        except (PermanentTaskError, RetryableTaskError, ImmichApiError) as error:
            reason = f"{type(error).__name__}: {error}"
            logger.warning(
                "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                asset_id, attempt, reason,
            )
            self._count("failed_or_skipped_attempts")
            return False, reason

    @staticmethod
    def _same_source(left, right) -> bool:
        return (
            left.id == right.id
            and right.asset_type == "IMAGE"
            and not right.is_trashed
            and not right.is_offline
            and left.file_modified_at == right.file_modified_at
            and left.file_size_bytes == right.file_size_bytes
            and left.checksum == right.checksum
        )

    async def fingerprint_changed_asset(self, context: TaskContext, asset_id: UUID) -> bool:
        """Best-effort two-attempt update for one synchronized change."""

        for attempt in ("incremental", "incremental_retry"):
            await context.ensure_active()
            started = perf_counter()
            known = await self._assets.get_immich_assets([asset_id])
            self._measure("metadata_preparation", started)
            succeeded, _ = await self._fingerprint(
                context, asset_id, known.get(asset_id), attempt=attempt
            )
            if succeeded:
                return True
        return False


class SimilarityIndexTaskHandler:
    """Dedicated pauseable task for library-wide fingerprint maintenance."""

    task_type = SIMILARITY_INDEX_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1
    supports_pause = True

    def __init__(self, maintainer: SimilarityIndexMaintainer) -> None:
        self._maintainer = maintainer

    async def execute(self, context: TaskContext, _payload: dict[str, object]) -> TaskResult:
        coverage, completed, unavailable, _, failures = await self._maintainer.maintain(context)
        return TaskResult(
            summary={
                "coverage": coverage.model_dump(mode="json"),
                "unavailable_asset_reasons": {
                    str(asset_id): reason for asset_id, reason in list(failures.items())[:100]
                },
                "unavailable_asset_reasons_truncated": len(failures) > 100,
            },
            counters={
                "eligible_images": coverage.eligible_count,
                "current_fingerprints": coverage.current_count,
                "missing_fingerprints": coverage.missing_count,
                "stale_fingerprints": coverage.stale_count,
                "fingerprints_completed": completed,
                "fingerprints_unavailable": unavailable,
                **self._maintainer.metrics(),
            },
        )


class SimilarityIndexService:
    """Expose independent durable fingerprint maintenance and coverage."""

    def __init__(self, tasks: TaskCoordinator, maintainer: SimilarityIndexMaintainer) -> None:
        self._tasks = tasks
        self._maintainer = maintainer

    async def start(self) -> SimilarityIndexTaskStart:
        key = (
            f"{SEARCH_MODEL_VERSION}:{SEARCH_FEATURE_VERSION}:"
            f"{SEARCH_CONFIG_FINGERPRINT}"
        )
        task = await self._tasks.find_active(SIMILARITY_INDEX_TASK_TYPE, key)
        if task is None:
            task = await self._tasks.submit(
                SIMILARITY_INDEX_TASK_TYPE,
                {},
                priority=40,
                lane_key=INTEGRITY_TASK_TYPE,
                deduplication_key=key,
            )
            await self._tasks.start()
        return SimilarityIndexTaskStart(task_id=task.id)

    async def coverage(self) -> SimilarityIndexCoverage:
        return await self._maintainer.coverage()

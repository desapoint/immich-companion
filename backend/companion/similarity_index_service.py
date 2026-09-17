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
from companion.image_decode import MAX_DECODED_PIXELS
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
ALPHA_CAPABLE_MIME_TYPES = frozenset(
    {
        "image/png",
        "image/webp",
        "image/gif",
        "image/tiff",
        "image/avif",
        "image/heic",
        "image/heif",
    }
)
ALPHA_CAPABLE_SUFFIXES = frozenset(
    {".png", ".webp", ".gif", ".tif", ".tiff", ".avif", ".heic", ".heif"}
)
NON_RETRYABLE_FAILURE_MARKERS = (
    "image_decode_limit_exceeded",
    "original exceeds similarity fallback size limit",
    "bounded preview could not produce coarse visual evidence",
    "asset is trashed",
    "asset is offline",
    "not IMAGE",
)

logger = logging.getLogger("uvicorn.error")


def _source_may_have_alpha(source: ImmichAsset) -> bool:
    """Return whether the original container can carry meaningful transparency."""

    mime = (source.original_mime_type or "").split(";", 1)[0].strip().lower()
    suffix = Path(source.original_file_name).suffix.lower()
    return mime in ALPHA_CAPABLE_MIME_TYPES or suffix in ALPHA_CAPABLE_SUFFIXES


def _source_exceeds_decode_limit(source: ImmichAsset) -> bool:
    """Preflight originals that the shared decoder policy will not fully materialize."""

    return bool(
        source.width is not None
        and source.height is not None
        and source.width > 0
        and source.height > 0
        and source.width * source.height > MAX_DECODED_PIXELS
    )


def _failure_is_retryable(reason: str | None) -> bool:
    """Avoid repeating deterministic policy/geometry failures in the same task."""

    if not reason:
        return True
    return not any(marker in reason for marker in NON_RETRYABLE_FAILURE_MARKERS)


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

    def _record_timings(self, timings: dict[str, int]) -> None:
        for key, value in timings.items():
            self._count(key, value)

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
            timings: dict[str, int] = {}
            decoded, feature = await asyncio.to_thread(
                decode_and_extract_features,
                spool,
                detect_file_format(bytes(prefix)),
                include_pixel_hash=False,
                timings=timings,
            )
            self._measure("decode_feature_wall", started)
            self._record_timings(timings)
            self._count("original_decodes")
            if decoded.valid is not True or feature is None:
                raise ValueError(decoded.issue or "original could not produce coarse visual evidence")
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
        """Fingerprint missing assets, retry transient failures once, and report failures."""

        initial = await self.coverage()
        self._metrics = {
            "fingerprints_reused": initial.current_count,
            "preview_fingerprints_generated": 0,
            "bounded_fingerprints_generated": 0,
            "original_fingerprints_generated": 0,
            "fallbacks_to_original": 0,
            "alpha_preserving_original_fallbacks": 0,
            "oversized_original_decodes_avoided": 0,
            "deep_verifications_performed": 0,
            "failed_or_skipped_attempts": 0,
            "preview_bytes_downloaded": 0,
            "original_bytes_downloaded": 0,
            "decode_milliseconds": 0,
            "feature_extraction_milliseconds": 0,
            "normalized_pixel_hash_milliseconds": 0,
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
        non_retryable_failures: dict[UUID, str] = {}
        if total == 0 and saved.get("phase") in {"candidate_index", "scoring"}:
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
            for asset_id, (succeeded, reason) in zip(page, results, strict=True):
                if succeeded:
                    completed += 1
                else:
                    unavailable += 1
                    if not _failure_is_retryable(reason) and reason is not None:
                        non_retryable_failures[asset_id] = reason
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
        retry_total = max(
            0,
            retry_coverage.missing_count
            + retry_coverage.stale_count
            - len(non_retryable_failures),
        )
        retry_attempted: set[UUID] = set()
        retry_failures: dict[UUID, str] = dict(non_retryable_failures)
        retry_completed = 0
        if retry_total:
            await context.checkpoint(
                checkpoint={"phase": "similarity_fingerprint_retry"},
                counters={
                    "eligible_images": retry_coverage.eligible_count,
                    "current_fingerprints": retry_coverage.current_count,
                    "fingerprints_pending": retry_total,
                    "fingerprints_completed": completed,
                    "fingerprints_unavailable": retry_coverage.missing_count
                    + retry_coverage.stale_count,
                },
                progress={
                    "phase": "similarity_fingerprinting",
                    "completed": 0,
                    "total": retry_total,
                    "percent": progress_ceiling,
                    "detail": f"Retrying {retry_total} transient library fingerprint failures once…",
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
                retry_after = page[-1]
                retry_page = [asset_id for asset_id in page if asset_id not in non_retryable_failures]
                if not retry_page:
                    continue
                results = await self._fingerprint_page(context, retry_page, attempt="retry")
                for asset_id, (succeeded, reason) in zip(retry_page, results, strict=True):
                    retry_attempted.add(asset_id)
                    if succeeded:
                        retry_completed += 1
                        retry_failures.pop(asset_id, None)
                    elif reason is not None:
                        retry_failures[asset_id] = reason
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
                        "fingerprints_unavailable": max(
                            0,
                            retry_coverage.missing_count
                            + retry_coverage.stale_count
                            - retry_completed,
                        ),
                    },
                    progress={
                        "phase": "similarity_fingerprinting",
                        "completed": len(retry_attempted),
                        "total": retry_total,
                        "percent": progress_ceiling,
                        "detail": f"Retried {len(retry_attempted)} of {retry_total} transient fingerprints.",
                    },
                )
        final = await self.coverage()
        all_attempted = retry_attempted | set(non_retryable_failures)
        return (
            final,
            completed + retry_completed,
            final.missing_count + final.stale_count,
            all_attempted,
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
                    timings: dict[str, int] = {}
                    feature = await asyncio.to_thread(
                        extract_search_feature, preview, timings=timings
                    )
                    self._measure("decode_feature_wall", started)
                    self._record_timings(timings)
                    self._count("preview_decodes")
            origin = "preview"
            oversized_source = _source_exceeds_decode_limit(source)
            alpha_original_required = (
                feature is not None
                and not feature.has_alpha
                and _source_may_have_alpha(source)
            )
            if oversized_source:
                if feature is None:
                    reason = (
                        f"bounded preview could not produce coarse visual evidence"
                        f" ({preview_error})"
                    )
                    logger.warning(
                        "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                        asset_id, attempt, reason,
                    )
                    self._count("failed_or_skipped_attempts")
                    return False, reason
                origin = "bounded"
                media_digest = sha256(preview, usedforsecurity=False).hexdigest()
                self._count("oversized_original_decodes_avoided")
                if alpha_original_required:
                    self._count("bounded_alpha_uncertain_fingerprints")
            elif feature is None or alpha_original_required:
                self._count("fallbacks_to_original")
                if alpha_original_required:
                    self._count("alpha_preserving_original_fallbacks")
                try:
                    async with self._fetch_slots, self._decode_slots:
                        feature, media_digest = await self._original_fallback(context, asset_id)
                    origin = "original"
                except (ImmichApiError, ValueError, OSError) as error:
                    if alpha_original_required:
                        reason = f"alpha-preserving original fallback failed: {error}"
                    else:
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
                    if origin == "preview"
                    else "bounded_fingerprints_generated"
                    if origin == "bounded"
                    else "original_fingerprints_generated"
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
        """Best-effort update for one synchronized change with transient retry only."""

        for attempt in ("incremental", "incremental_retry"):
            await context.ensure_active()
            started = perf_counter()
            known = await self._assets.get_immich_assets([asset_id])
            self._measure("metadata_preparation", started)
            succeeded, reason = await self._fingerprint(
                context, asset_id, known.get(asset_id), attempt=attempt
            )
            if succeeded:
                return True
            if not _failure_is_retryable(reason):
                break
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
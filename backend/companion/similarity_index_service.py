"""Durable library-wide Appearance fingerprint maintenance."""

from __future__ import annotations

import asyncio
import inspect
import logging
from io import BytesIO
from pathlib import Path
from time import perf_counter
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.duplicate_schema import SimilarityIndexCoverage, SimilarityIndexTaskStart
from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset
from companion.integrity import detect_file_format
from companion.integrity_service import INTEGRITY_TASK_TYPE
from companion.similarity_bounded_state import SourceAlphaState
from companion.similarity_detail import extract_detail_feature
from companion.similarity_detail_service import SimilarityDetailRepository
from companion.similarity_search_features import (
    SEARCH_CONFIG_FINGERPRINT,
    SEARCH_FEATURE_VERSION,
    SEARCH_MODEL_VERSION,
    extract_search_feature,
    search_source_identity,
)
from companion.similarity_search_repository import SimilaritySearchRepository
from companion.similarity_settings import SimilarityRuntimeSettingsRepository
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult
from companion.similarity_visual_normalization import (
    SimilarityVisualNormalizer,
    VisualNormalizationError,
    source_requires_bounded_visual,
)

SIMILARITY_INDEX_TASK_TYPE = "similarity_index"
SIMILARITY_FINGERPRINT_BATCH_SIZE = 25
ORIGINAL_FALLBACK_MAX_BYTES = 128 * 1024 * 1024
NON_RETRYABLE_FAILURE_MARKERS = (
    "image_decode_limit_exceeded",
    "original exceeds similarity fallback size limit",
    "bounded_preview_decode_failed",
    "normalized_visual_feature_decode_failed",
    "visual_source_decode_limit_exceeded",
    "visual_source_decode_failed",
    "unsupported similarity representation",
    "asset is trashed",
    "asset is offline",
    "not IMAGE",
)

logger = logging.getLogger("uvicorn.error")


class SimilarityIndexCoverageDetails(SimilarityIndexCoverage):
    """Coverage including bounded and explicitly unavailable evidence."""

    bounded_count: int = 0
    unavailable_count: int = 0


def _failure_is_retryable(reason: str | None) -> bool:
    """Return False only for deterministic source/config-scoped failures."""

    if not reason:
        return True
    return not any(marker in reason for marker in NON_RETRYABLE_FAILURE_MARKERS)


def _accepts_parameter(callable_object: object, parameter: str) -> bool:
    """Allow rolling upgrades and lightweight adapters to use the legacy contract."""

    try:
        return parameter in inspect.signature(callable_object).parameters
    except (TypeError, ValueError):
        return True


class SimilarityIndexMaintainer:
    """Select and commit only missing or stale synchronized image features."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        features: SimilaritySearchRepository,
        *,
        details: SimilarityDetailRepository | None = None,
        batch_size: int = SIMILARITY_FINGERPRINT_BATCH_SIZE,
        fetch_slots: int = 2,
        decode_slots: int = 2,
        fallback_max_bytes: int = ORIGINAL_FALLBACK_MAX_BYTES,
        decode_cache_path: Path | None = None,
        runtime_settings: SimilarityRuntimeSettingsRepository | None = None,
    ) -> None:
        if min(batch_size, fetch_slots, decode_slots, fallback_max_bytes) < 1:
            raise ValueError("Fingerprint batch and pipeline slots must be positive")
        self._immich = immich
        self._assets = assets
        self._features = features
        self._details = details
        self._batch_size = batch_size
        self._fetch_slots = asyncio.Semaphore(fetch_slots)
        self._decode_slots = asyncio.Semaphore(decode_slots)
        self._normalizer = SimilarityVisualNormalizer(
            immich,
            max_bytes=fallback_max_bytes,
            cache_path=decode_cache_path,
            fetch_slots=self._fetch_slots,
            decode_slots=self._decode_slots,
        )
        self._inflight_slots = asyncio.Semaphore(fetch_slots + decode_slots)
        self._fallback_max_bytes = fallback_max_bytes
        self._decode_cache_path = decode_cache_path
        self._runtime_settings = runtime_settings
        self._metrics: dict[str, int] = {}
        self._legacy_coverage_contract = False

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

    async def _fingerprint_page_size(self) -> int:
        if self._runtime_settings is None:
            return self._batch_size
        return (await self._runtime_settings.get()).fingerprint_page_size

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

    async def coverage(self) -> SimilarityIndexCoverageDetails:
        raw_coverage = await self._features.coverage()
        if len(raw_coverage) == 4:
            self._legacy_coverage_contract = True
            eligible, current, missing, stale = raw_coverage
            bounded = 0
            unavailable = 0
        else:
            eligible, current, bounded, unavailable, missing, stale = raw_coverage
        return SimilarityIndexCoverageDetails(
            eligible_count=eligible,
            current_count=current,
            bounded_count=bounded,
            unavailable_count=unavailable,
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
        """Fingerprint pending assets, retry transient failures once, persist deterministic ones."""

        initial = await self.coverage()
        fingerprint_page_size = await self._fingerprint_page_size()
        self._metrics = {
            "fingerprints_reused": initial.current_count,
            "preview_fingerprints_generated": 0,
            "bounded_fingerprints_generated": 0,
            "bounded_search_fingerprints_generated": 0,
            "original_fingerprints_generated": 0,
            "fallbacks_to_original": 0,
            "alpha_preserving_original_fallbacks": 0,
            "oversized_original_decodes_avoided": 0,
            "alpha_uncertain_bounded_evidence": 0,
            "deterministic_retries_suppressed": 0,
            "deep_verifications_performed": 0,
            "failed_or_skipped_attempts": 0,
            "preview_bytes_downloaded": 0,
            "original_bytes_downloaded": 0,
            "decode_milliseconds": 0,
            "feature_extraction_milliseconds": 0,
            "normalized_pixel_hash_milliseconds": 0,
            "normalized_source_bytes": 0,
            "normalized_images_resized": 0,
            "detail_features_generated": 0,
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
        attempted: set[UUID] = set()
        failures: dict[UUID, str] = {}
        if total == 0 and saved.get("phase") in {"candidate_index", "scoring"}:
            return initial, 0, initial.unavailable_count, set(), {}
        await context.checkpoint(
            checkpoint={
                "phase": "similarity_fingerprinting",
                "cursor": str(after) if after else None,
            },
            counters={
                "eligible_images": initial.eligible_count,
                "current_fingerprints": initial.current_count,
                "bounded_fingerprints": initial.bounded_count,
                "fingerprints_pending": total,
                "fingerprints_completed": 0,
                "fingerprints_unavailable": initial.unavailable_count,
            },
            progress={
                "phase": "similarity_fingerprinting",
                "completed": 0,
                "total": total,
                "percent": 0.0 if total else progress_ceiling,
                "detail": (
                    f"Preparing {total} missing or stale library fingerprints…"
                    if total
                    else "Every eligible image is current or explicitly unavailable."
                ),
            },
        )
        while True:
            await context.ensure_active()
            page = await self._features.list_work(
                after_asset_id=after,
                limit=fingerprint_page_size,
            )
            if not page:
                break
            results = await self._fingerprint_page(context, page, attempt="initial")
            for asset_id, (succeeded, reason) in zip(page, results, strict=True):
                attempted.add(asset_id)
                if succeeded:
                    completed += 1
                elif reason is not None:
                    failures[asset_id] = reason
            after = page[-1]
            done = min(total, len(attempted))
            current_coverage = await self.coverage()
            await context.checkpoint(
                checkpoint={
                    "phase": "similarity_fingerprinting",
                    "cursor": str(after),
                },
                counters={
                    "eligible_images": current_coverage.eligible_count,
                    "current_fingerprints": current_coverage.current_count,
                    "bounded_fingerprints": current_coverage.bounded_count,
                    "fingerprints_pending": max(0, total - done),
                    "fingerprints_completed": completed,
                    "fingerprints_unavailable": current_coverage.unavailable_count,
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
        retry_completed = 0
        if retry_total:
            await context.checkpoint(
                checkpoint={"phase": "similarity_fingerprint_retry"},
                counters={
                    "eligible_images": retry_coverage.eligible_count,
                    "current_fingerprints": retry_coverage.current_count,
                    "bounded_fingerprints": retry_coverage.bounded_count,
                    "fingerprints_pending": retry_total,
                    "fingerprints_completed": completed,
                    "fingerprints_unavailable": retry_coverage.unavailable_count,
                },
                progress={
                    "phase": "similarity_fingerprinting",
                    "completed": 0,
                    "total": retry_total,
                    "percent": progress_ceiling,
                    "detail": (
                        f"Retrying {retry_total} transient library fingerprint "
                        "failures once…"
                    ),
                },
            )
            retry_after: UUID | None = None
            while True:
                await context.ensure_active()
                page = await self._features.list_work(
                    after_asset_id=retry_after,
                    limit=fingerprint_page_size,
                )
                if not page:
                    break
                retry_after = page[-1]
                results = await self._fingerprint_page(context, page, attempt="retry")
                for asset_id, (succeeded, reason) in zip(page, results, strict=True):
                    retry_attempted.add(asset_id)
                    attempted.add(asset_id)
                    if succeeded:
                        retry_completed += 1
                        failures.pop(asset_id, None)
                    elif reason is not None:
                        failures[asset_id] = reason
        final = await self.coverage()
        unavailable_result = (
            len(failures) if self._legacy_coverage_contract else final.unavailable_count
        )
        return (
            final,
            completed + retry_completed,
            unavailable_result,
            retry_attempted if self._legacy_coverage_contract else attempted | retry_attempted,
            failures if not final.complete or final.unavailable_count else {},
        )

    async def _persist_deterministic_failure(
        self,
        source: ImmichAsset | None,
        reason: str,
        alpha_state: SourceAlphaState = "unknown_alpha",
        evidence_epoch: int | None = None,
    ) -> None:
        if source is None or _failure_is_retryable(reason):
            return
        marker = getattr(self._features, "mark_unavailable", None)
        if marker is None:
            return
        kwargs: dict[str, object] = {}
        if _accepts_parameter(marker, "source_alpha_state"):
            kwargs["source_alpha_state"] = alpha_state
        if evidence_epoch is not None and _accepts_parameter(marker, "evidence_epoch"):
            kwargs["evidence_epoch"] = evidence_epoch
        persisted = await marker(source, reason, **kwargs)
        if persisted:
            self._count("deterministic_retries_suppressed")

    async def _failure(
        self,
        source: ImmichAsset | None,
        reason: str,
        *,
        alpha_state: SourceAlphaState = "unknown_alpha",
        warning: bool = True,
        asset_id: UUID | None = None,
        attempt: str = "",
        evidence_epoch: int | None = None,
    ) -> tuple[bool, str]:
        await self._persist_deterministic_failure(
            source,
            reason,
            alpha_state,
            evidence_epoch,
        )
        self._count("failed_or_skipped_attempts")
        if warning:
            logger.warning(
                "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                asset_id or (source.id if source else None),
                attempt,
                reason,
            )
        return False, reason

    async def _fingerprint(
        self, context: TaskContext, asset_id: UUID, source: ImmichAsset | None, *, attempt: str
    ) -> tuple[bool, str | None]:
        async with self._inflight_slots:
            await context.ensure_active()
            return await self._fingerprint_unbounded(context, asset_id, source, attempt=attempt)

    async def _fingerprint_unbounded(
        self, context: TaskContext, asset_id: UUID, source: ImmichAsset | None, *, attempt: str
    ) -> tuple[bool, str | None]:
        epoch_getter = getattr(self._features, "current_evidence_epoch", None)
        evidence_epoch = await epoch_getter() if epoch_getter is not None else None
        try:
            if source is None:
                self._count("failed_or_skipped_attempts")
                return False, "asset is no longer synchronized"
            if source.file_size_bytes is None:
                async with self._fetch_slots:
                    started = perf_counter()
                    source = await self._immich.get_asset(asset_id)
                    await self._assets.refresh_asset(source, track_similarity_changes=False)
                    self._measure("metadata_preparation", started)
            if source.is_trashed or source.is_offline or source.asset_type != "IMAGE":
                reason = (
                    "asset is trashed"
                    if source.is_trashed
                    else "asset is offline"
                    if source.is_offline
                    else f"asset type is {source.asset_type}, not IMAGE"
                )
                return await self._failure(
                    source,
                    reason,
                    warning=False,
                    asset_id=asset_id,
                    attempt=attempt,
                    evidence_epoch=evidence_epoch,
                )

            bounded_source = source_requires_bounded_visual(source)
            if bounded_source:
                self._count("oversized_original_decodes_avoided")

            started = perf_counter()
            normalized = await self._normalizer.normalize(context, asset_id, source)
            self._measure("visual_normalization", started)
            self._count("normalized_source_bytes", normalized.source_bytes)
            if normalized.resized:
                self._count("normalized_images_resized")

            timings: dict[str, int] = {}
            started = perf_counter()
            async with self._decode_slots:
                feature = await asyncio.to_thread(
                    extract_search_feature,
                    normalized.content,
                    timings=timings,
                )
                detail = await asyncio.to_thread(
                    extract_detail_feature,
                    BytesIO(normalized.content),
                    detect_file_format(normalized.content[:64]),
                )
            self._measure("decode_feature_wall", started)
            self._record_timings(timings)

            if feature is None or detail is None:
                return await self._failure(
                    source,
                    "normalized_visual_feature_decode_failed",
                    asset_id=asset_id,
                    attempt=attempt,
                    evidence_epoch=evidence_epoch,
                )

            alpha_state: SourceAlphaState = (
                "confirmed_alpha" if normalized.has_alpha else "confirmed_opaque"
            )

            await context.ensure_active()
            async with self._fetch_slots:
                started = perf_counter()
                current = await self._immich.get_asset(asset_id)
                self._measure("metadata_preparation", started)
            if not self._same_source(source, current):
                if not current.is_trashed:
                    await self._assets.refresh_asset(current, track_similarity_changes=False)
                self._count("failed_or_skipped_attempts")
                return False, "Immich source changed while visual evidence was generated"

            saver = self._features.save
            kwargs = {"origin": normalized.search_origin}
            if _accepts_parameter(saver, "source_alpha_state"):
                kwargs["source_alpha_state"] = alpha_state
            if evidence_epoch is not None and _accepts_parameter(saver, "evidence_epoch"):
                kwargs["evidence_epoch"] = evidence_epoch

            started = perf_counter()
            saved_feature = await saver(
                source,
                normalized.media_sha256,
                feature,
                **kwargs,
            )
            self._measure("db_persistence", started)
            if not saved_feature:
                self._count("failed_or_skipped_attempts")
                return False, "synchronized source changed while visual evidence was saved"

            if self._details is not None:
                source_identity = search_source_identity(
                    source,
                    normalized.media_sha256,
                    origin=normalized.search_origin,
                )
                detail_kwargs: dict[str, object] = {}
                if evidence_epoch is not None and _accepts_parameter(
                    self._details.save, "evidence_epoch"
                ):
                    detail_kwargs["evidence_epoch"] = evidence_epoch
                detail_saved = await self._details.save(
                    source_identity,
                    asset_id,
                    detail,
                    normalized.detail_origin,
                    **detail_kwargs,
                )
                if not detail_saved:
                    self._count("failed_or_skipped_attempts")
                    return False, "localized detail changed while visual evidence was saved"
                self._count("detail_features_generated")

            if normalized.source_kind == "original":
                self._count("original_fingerprints_generated")
                self._count("original_bytes_downloaded", normalized.source_bytes)
                self._count("original_decodes")
            else:
                self._count("bounded_fingerprints_generated")
                self._count("bounded_search_fingerprints_generated")
                self._count("preview_bytes_downloaded", normalized.source_bytes)
                self._count("preview_decodes")
            return True, None
        except VisualNormalizationError as error:
            return await self._failure(
                source,
                str(error),
                asset_id=asset_id,
                attempt=attempt,
                evidence_epoch=evidence_epoch,
            )
        except (PermanentTaskError, RetryableTaskError, ImmichApiError) as error:
            reason = f"{type(error).__name__}: {error}"
            return await self._failure(
                source,
                reason,
                asset_id=asset_id,
                attempt=attempt,
                evidence_epoch=evidence_epoch,
            )

    @staticmethod
    def _same_source(left: ImmichAsset, right: ImmichAsset) -> bool:
        return (
            left.id == right.id
            and right.asset_type == "IMAGE"
            and not right.is_trashed
            and not right.is_offline
            and left.file_modified_at == right.file_modified_at
            and left.file_size_bytes == right.file_size_bytes
            and left.checksum == right.checksum
            and left.width == right.width
            and left.height == right.height
        )

    async def ensure_asset(self, context: TaskContext, asset_id: UUID) -> bool:
        """Ensure one image has complete current search + localized-detail evidence."""

        if await self._features.has_current(asset_id):
            self._count("fingerprints_reused")
            return True
        return await self.fingerprint_changed_asset(context, asset_id)

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
        bounded_count = getattr(coverage, "bounded_count", 0)
        unavailable_count = getattr(coverage, "unavailable_count", unavailable)
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
                "bounded_fingerprints": bounded_count,
                "unavailable_fingerprints": unavailable_count,
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

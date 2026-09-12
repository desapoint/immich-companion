"""Durable library-wide Appearance fingerprint maintenance."""

from __future__ import annotations

import logging
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.duplicate_schema import SimilarityIndexCoverage, SimilarityIndexTaskStart
from companion.immich import ImmichApiClient, ImmichApiError
from companion.integrity_repository import (
    IntegrityRepository,
    similarity_feature_freshness,
)
from companion.integrity_service import INTEGRITY_TASK_TYPE, IntegrityTaskHandler
from companion.similarity_features import (
    SIMILARITY_CONFIG_FINGERPRINT,
    SIMILARITY_FEATURE_VERSION,
    SIMILARITY_MODEL_VERSION,
)
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult

SIMILARITY_INDEX_TASK_TYPE = "similarity_index"
SIMILARITY_FINGERPRINT_BATCH_SIZE = 25

logger = logging.getLogger("uvicorn.error")


class SimilarityIndexMaintainer:
    """Select and commit only missing or stale synchronized image features."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        features: IntegrityRepository,
        integrity: IntegrityTaskHandler,
        *,
        batch_size: int = SIMILARITY_FINGERPRINT_BATCH_SIZE,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._features = features
        self._integrity = integrity
        self._batch_size = batch_size

    async def coverage(self) -> SimilarityIndexCoverage:
        eligible, current, missing, stale = await self._features.similarity_feature_coverage()
        return SimilarityIndexCoverage(
            eligible_count=eligible,
            current_count=current,
            missing_count=missing,
            stale_count=stale,
            complete=missing == 0 and stale == 0,
            model_version=SIMILARITY_MODEL_VERSION,
            feature_version=SIMILARITY_FEATURE_VERSION,
            config_fingerprint=SIMILARITY_CONFIG_FINGERPRINT,
        )

    async def maintain(
        self,
        context: TaskContext,
        *,
        progress_ceiling: float = 100.0,
    ) -> tuple[SimilarityIndexCoverage, int, int, set[UUID], dict[UUID, str]]:
        """Fingerprint missing assets, retry once, and report per-asset failures."""

        initial = await self.coverage()
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
            page = await self._features.list_similarity_feature_work(
                after_asset_id=after,
                limit=self._batch_size,
            )
            if not page:
                break
            for asset_id in page:
                await context.ensure_active()
                succeeded, _ = await self._fingerprint(context, asset_id, attempt="initial")
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
                page = await self._features.list_similarity_feature_work(
                    after_asset_id=retry_after,
                    limit=self._batch_size,
                )
                if not page:
                    break
                for asset_id in page:
                    await context.ensure_active()
                    retry_attempted.add(asset_id)
                    succeeded, reason = await self._fingerprint(context, asset_id, attempt="retry")
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
        self, context: TaskContext, asset_id: UUID, *, attempt: str
    ) -> tuple[bool, str | None]:
        try:
            source = await self._immich.get_asset(asset_id)
            if source.is_trashed or source.is_offline or source.asset_type != "IMAGE":
                await self._assets.refresh_asset(source, track_similarity_changes=False)
                reason = (
                    "asset is trashed" if source.is_trashed else
                    "asset is offline" if source.is_offline else
                    f"asset type is {source.asset_type}, not IMAGE"
                )
                logger.warning(
                    "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                    asset_id, attempt, reason,
                )
                return False, reason
            await self._assets.refresh_asset(source, track_similarity_changes=False)
            report = await self._integrity.analyze(
                context,
                asset_id,
                publish_progress=False,
                source=source,
                track_similarity_changes=False,
            )
            feature = await self._features.get_similarity_feature(asset_id)
            freshness = similarity_feature_freshness(feature, source)
            if freshness == "current":
                return True, None
            details = ", ".join(getattr(report, "issues", [])[:3])
            reason = f"no current fingerprint persisted (freshness={freshness}"
            if details:
                reason += f"; analysis issues={details}"
            reason += ")"
            logger.warning(
                "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                asset_id, attempt, reason,
            )
            return False, reason
        except (PermanentTaskError, RetryableTaskError, ImmichApiError) as error:
            reason = f"{type(error).__name__}: {error}"
            logger.warning(
                "Library fingerprint unavailable: asset_id=%s attempt=%s reason=%s",
                asset_id, attempt, reason,
            )
            return False, reason


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
            },
        )


class SimilarityIndexService:
    """Expose independent durable fingerprint maintenance and coverage."""

    def __init__(self, tasks: TaskCoordinator, maintainer: SimilarityIndexMaintainer) -> None:
        self._tasks = tasks
        self._maintainer = maintainer

    async def start(self) -> SimilarityIndexTaskStart:
        key = (
            f"{SIMILARITY_MODEL_VERSION}:{SIMILARITY_FEATURE_VERSION}:"
            f"{SIMILARITY_CONFIG_FINGERPRINT}"
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

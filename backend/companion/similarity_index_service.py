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
    ) -> tuple[SimilarityIndexCoverage, int, int]:
        """Run one resumable keyset pass and return coverage, completed, unavailable."""

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
            return initial, 0, 0
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
                try:
                    source = await self._immich.get_asset(asset_id)
                    if source.is_trashed or source.is_offline or source.asset_type != "IMAGE":
                        await self._assets.refresh_asset(
                            source, track_similarity_changes=False
                        )
                        unavailable += 1
                        continue
                    await self._assets.refresh_asset(
                        source, track_similarity_changes=False
                    )
                    await self._integrity.analyze(
                        context,
                        asset_id,
                        publish_progress=False,
                        source=source,
                        track_similarity_changes=False,
                    )
                    feature = await self._features.get_similarity_feature(asset_id)
                    if similarity_feature_freshness(feature, source) == "current":
                        completed += 1
                    else:
                        unavailable += 1
                except (PermanentTaskError, RetryableTaskError, ImmichApiError) as error:
                    unavailable += 1
                    logger.warning(
                        "Library fingerprint unavailable: asset_id=%s error_type=%s reason=%s",
                        asset_id,
                        type(error).__name__,
                        error,
                    )
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
        return await self.coverage(), completed, unavailable


class SimilarityIndexTaskHandler:
    """Dedicated pauseable task for library-wide fingerprint maintenance."""

    task_type = SIMILARITY_INDEX_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1
    supports_pause = True

    def __init__(self, maintainer: SimilarityIndexMaintainer) -> None:
        self._maintainer = maintainer

    async def execute(self, context: TaskContext, _payload: dict[str, object]) -> TaskResult:
        coverage, completed, unavailable = await self._maintainer.maintain(context)
        return TaskResult(
            summary={"coverage": coverage.model_dump(mode="json")},
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

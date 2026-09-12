"""Incremental, durable Appearance maintenance driven by synchronized asset changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select

from companion.database import DatabaseManager
from companion.integrity_repository import IntegrityRepository
from companion.integrity_service import INTEGRITY_TASK_TYPE, IntegrityTaskHandler
from companion.models import SimilarityAssetChangeRecord
from companion.similarity_repository import SimilarityRepository
from companion.similarity_scan_repository import SimilarityScanPair, SimilarityScanRepository
from companion.task_coordinator import TaskContext, TaskCoordinator
from companion.task_schema import TaskResult, TaskStatusView

SIMILARITY_MAINTENANCE_TASK_TYPE = "similarity_maintenance"
SIMILARITY_MAINTENANCE_BATCH_SIZE = 25
SIMILARITY_FEATURE_PAGE_SIZE = 1_000


@dataclass(frozen=True, slots=True)
class SimilarityAssetChange:
    asset_id: UUID
    operation: str
    source_fingerprint: str | None
    enqueued_at: datetime


class SimilarityMaintenanceRepository:
    """Read and acknowledge coalesced asset work without claiming it in memory."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def pending(self, limit: int) -> list[SimilarityAssetChange]:
        statement = (
            select(SimilarityAssetChangeRecord)
            .order_by(
                SimilarityAssetChangeRecord.enqueued_at,
                SimilarityAssetChangeRecord.asset_id,
            )
            .limit(limit)
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return [
            SimilarityAssetChange(
                asset_id=record.asset_id,
                operation=record.operation,
                source_fingerprint=record.source_fingerprint,
                enqueued_at=record.enqueued_at,
            )
            for record in records
        ]

    async def acknowledge(self, change: SimilarityAssetChange) -> bool:
        statement = delete(SimilarityAssetChangeRecord).where(
            SimilarityAssetChangeRecord.asset_id == change.asset_id,
            SimilarityAssetChangeRecord.operation == change.operation,
            SimilarityAssetChangeRecord.source_fingerprint.is_not_distinct_from(
                change.source_fingerprint
            ),
        )
        async with self._database.sessions() as session, session.begin():
            result = await session.execute(statement)
        return bool(result.rowcount)

    async def count(self) -> int:
        async with self._database.sessions() as session:
            return int(
                await session.scalar(
                    select(func.count()).select_from(SimilarityAssetChangeRecord)
                )
                or 0
            )


class SimilarityMaintenanceService:
    """Submit at most one normal-priority incremental maintenance worker."""

    def __init__(self, tasks: TaskCoordinator, changes: SimilarityMaintenanceRepository) -> None:
        self._tasks = tasks
        self._changes = changes

    async def start_if_pending(self) -> TaskStatusView | None:
        if await self._changes.count() == 0:
            return None
        task = await self._tasks.submit(
            SIMILARITY_MAINTENANCE_TASK_TYPE,
            {},
            priority=40,
            deduplication_key="pending-asset-changes",
            lane_key=INTEGRITY_TASK_TYPE,
        )
        await self._tasks.start()
        return task


class SimilarityMaintenanceTaskHandler:
    """Refresh changed features and only their incident review relationships."""

    task_type = SIMILARITY_MAINTENANCE_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1
    supports_pause = True

    def __init__(
        self,
        changes: SimilarityMaintenanceRepository,
        integrity_handler: IntegrityTaskHandler,
        features: IntegrityRepository,
        similarity: SimilarityRepository,
        scans: SimilarityScanRepository,
    ) -> None:
        self._changes = changes
        self._integrity_handler = integrity_handler
        self._features = features
        self._similarity = similarity
        self._scans = scans

    async def _candidate_ids(self, asset_id: UUID) -> list[UUID]:
        target = await self._features.get_similarity_feature(asset_id)
        active = await self._scans.latest_completed_parameters()
        if target is None or active is None or target.height <= 0:
            return []
        _, parameters = active
        target_hash = int(target.perceptual_hash, 16)
        target_ratio = target.width / target.height
        ranked: list[tuple[int, int, UUID]] = []
        async for page in self._features.iter_current_similarity_features(
            batch_size=SIMILARITY_FEATURE_PAGE_SIZE
        ):
            for candidate in page:
                if candidate.asset_id == asset_id or candidate.height <= 0:
                    continue
                try:
                    distance = (target_hash ^ int(candidate.perceptual_hash, 16)).bit_count()
                except ValueError:
                    continue
                if distance > parameters.maximum_perceptual_distance:
                    continue
                ratio = candidate.width / candidate.height
                aspect_difference = abs(target_ratio - ratio) / max(target_ratio, ratio)
                if aspect_difference > parameters.maximum_aspect_difference:
                    continue
                ranked.append((distance, candidate.asset_id.int, candidate.asset_id))
                ranked.sort(key=lambda item: (item[0], item[1]))
                del ranked[parameters.maximum_neighbors_per_asset :]
        return [item[2] for item in ranked]

    async def _reconcile_asset(self, asset_id: UUID) -> int:
        active = await self._scans.latest_completed_parameters()
        if active is None:
            return 0
        scan_id, parameters = active
        candidate_ids = await self._candidate_ids(asset_id)
        feature_map = await self._features.get_similarity_features([asset_id, *candidate_ids])
        target = feature_map.get(asset_id)
        pairs: list[SimilarityScanPair] = []
        if target is not None and candidate_ids:
            edges = await self._similarity.reference_edges(
                [[asset_id, candidate_id] for candidate_id in candidate_ids],
                feature_map,
            )
            for candidate_id in candidate_ids:
                evidence = edges.get((asset_id, candidate_id))
                candidate = feature_map.get(candidate_id)
                if (
                    evidence is None
                    or candidate is None
                    or evidence.similarity_percent < parameters.similarity_threshold
                ):
                    continue
                low, high = (
                    (target, candidate)
                    if target.asset_id.int < candidate.asset_id.int
                    else (candidate, target)
                )
                pairs.append(
                    SimilarityScanPair(
                        asset_id_low=low.asset_id,
                        asset_id_high=high.asset_id,
                        asset_low_source_sha256=low.source_sha256,
                        asset_high_source_sha256=high.source_sha256,
                        evidence=evidence,
                    )
                )
        await self._scans.replace_asset_pairs(
            scan_id,
            asset_id,
            pairs,
            asset_count=await self._features.count_current_similarity_features(),
        )
        return len(pairs)

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        del payload
        processed = int(context.task.counters.get("assets_processed", 0))
        features_refreshed = int(context.task.counters.get("features_refreshed", 0))
        deletes_reconciled = int(context.task.counters.get("deletes_reconciled", 0))
        pairs_reconciled = int(context.task.counters.get("pairs_reconciled", 0))
        while batch := await self._changes.pending(SIMILARITY_MAINTENANCE_BATCH_SIZE):
            for change in batch:
                await context.ensure_active()
                feature_current = (
                    await self._features.has_current_similarity_feature(change.asset_id)
                    if change.operation == "upsert"
                    else False
                )
                if change.operation == "upsert" and not feature_current:
                    await self._integrity_handler.analyze(
                        context,
                        change.asset_id,
                        publish_progress=False,
                    )
                    features_refreshed += 1
                else:
                    deletes_reconciled += 1
                pairs_reconciled += await self._reconcile_asset(change.asset_id)
                await self._changes.acknowledge(change)
                processed += 1
                pending = await self._changes.count()
                await context.checkpoint(
                    checkpoint={"phase": "incremental", "last_asset_id": str(change.asset_id)},
                    counters={
                        "assets_processed": processed,
                        "features_refreshed": features_refreshed,
                        "deletes_reconciled": deletes_reconciled,
                        "pairs_reconciled": pairs_reconciled,
                        "assets_pending": pending,
                    },
                    progress={
                        "phase": "similarity_incremental",
                        "completed": processed,
                        "total": processed + pending,
                        "percent": round(processed / max(1, processed + pending) * 100, 1),
                        "detail": f"Maintained {processed} changed assets; {pending} pending",
                    },
                )
        return TaskResult(
            summary={"incremental": True, "full_scan_started": False},
            counters={
                "assets_processed": processed,
                "features_refreshed": features_refreshed,
                "deletes_reconciled": deletes_reconciled,
                "pairs_reconciled": pairs_reconciled,
                "assets_pending": 0,
            },
        )

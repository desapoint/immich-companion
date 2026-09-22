"""Durable Appearance maintenance driven by synchronized asset changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select

from companion.database import DatabaseManager
from companion.integrity_service import INTEGRITY_TASK_TYPE
from companion.models import SimilarityAssetChangeRecord
from companion.similarity_index_service import SimilarityIndexMaintainer
from companion.similarity_scan_repository import SimilarityScanRepository
from companion.similarity_search_repository import SimilaritySearchRepository
from companion.task_coordinator import TaskContext, TaskCoordinator
from companion.task_schema import TaskResult, TaskStatusView

SIMILARITY_MAINTENANCE_TASK_TYPE = "similarity_maintenance"
SIMILARITY_MAINTENANCE_BATCH_SIZE = 25
SIMILARITY_FEATURE_PAGE_SIZE = 1_000
# Lower than scheduled incremental sync (10) and user-triggered work.
SIMILARITY_BACKGROUND_PRIORITY = 5


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
    """Submit at most one low-priority Appearance maintenance worker."""

    def __init__(self, tasks: TaskCoordinator, changes: SimilarityMaintenanceRepository) -> None:
        self._tasks = tasks
        self._changes = changes

    async def start_if_pending(self) -> TaskStatusView | None:
        if await self._changes.count() == 0:
            return None
        task = await self._tasks.submit(
            SIMILARITY_MAINTENANCE_TASK_TYPE,
            {},
            priority=SIMILARITY_BACKGROUND_PRIORITY,
            deduplication_key="pending-asset-changes",
            lane_key=INTEGRITY_TASK_TYPE,
        )
        await self._tasks.start()
        return task


class SimilarityMaintenanceTaskHandler:
    """Refresh per-image Appearance evidence without running duplicate discovery."""

    task_type = SIMILARITY_MAINTENANCE_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1
    supports_pause = True

    def __init__(
        self,
        changes: SimilarityMaintenanceRepository,
        indexer: SimilarityIndexMaintainer,
        features: SimilaritySearchRepository,
        scans: SimilarityScanRepository,
    ) -> None:
        self._changes = changes
        self._indexer = indexer
        self._features = features
        self._scans = scans

    async def _invalidate_asset_pairs(self, asset_id: UUID) -> bool:
        """Remove stale published relationships without allocating new candidates."""

        active = await self._scans.latest_completed_parameters()
        if active is None:
            return False
        scan_id, _ = active
        await self._scans.replace_asset_pairs(
            scan_id,
            asset_id,
            [],
            asset_count=await self._features.count_current(),
        )
        return True

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        del payload
        processed = int(context.task.counters.get("assets_processed", 0))
        features_refreshed = int(context.task.counters.get("features_refreshed", 0))
        deletes_reconciled = int(context.task.counters.get("deletes_reconciled", 0))
        scan_assets_invalidated = int(
            context.task.counters.get("scan_assets_invalidated", 0)
        )
        while batch := await self._changes.pending(SIMILARITY_MAINTENANCE_BATCH_SIZE):
            for change in batch:
                await context.ensure_active()
                if change.operation == "upsert":
                    feature_current = await self._features.has_current(change.asset_id)
                    if not feature_current and await self._indexer.fingerprint_changed_asset(
                        context, change.asset_id
                    ):
                        features_refreshed += 1
                elif change.operation == "delete":
                    deletes_reconciled += 1

                if await self._invalidate_asset_pairs(change.asset_id):
                    scan_assets_invalidated += 1

                await self._changes.acknowledge(change)
                processed += 1
                pending = await self._changes.count()
                await context.checkpoint(
                    checkpoint={"phase": "incremental", "last_asset_id": str(change.asset_id)},
                    counters={
                        "assets_processed": processed,
                        "features_refreshed": features_refreshed,
                        "deletes_reconciled": deletes_reconciled,
                        "scan_assets_invalidated": scan_assets_invalidated,
                        "assets_pending": pending,
                    },
                    progress={
                        "phase": "similarity_incremental",
                        "completed": processed,
                        "total": processed + pending,
                        "percent": round(processed / max(1, processed + pending) * 100, 1),
                        "detail": (
                            f"Indexed {processed} changed assets; {pending} pending. "
                            "Candidate discovery is deferred."
                        ),
                    },
                )
        return TaskResult(
            summary={
                "incremental": True,
                "full_scan_started": False,
                "discovery_deferred": True,
            },
            counters={
                "assets_processed": processed,
                "features_refreshed": features_refreshed,
                "deletes_reconciled": deletes_reconciled,
                "scan_assets_invalidated": scan_assets_invalidated,
                "assets_pending": 0,
            },
        )

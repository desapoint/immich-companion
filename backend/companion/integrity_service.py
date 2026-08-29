"""Bounded, durable orchestration for asset file-integrity analysis."""

from __future__ import annotations

from time import monotonic
from typing import Any
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset
from companion.integrity import FileIntegrityAnalyzer
from companion.integrity_repository import (
    IntegrityRepository,
    public_report,
    report_freshness,
    source_file_size,
)
from companion.integrity_schema import (
    AssetIntegrityAnalyzeResponse,
    AssetIntegrityReport,
    AssetIntegrityState,
)
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult

INTEGRITY_TASK_TYPE = "asset_integrity"
INTEGRITY_CHUNK_SIZE = 1024 * 1024
INTEGRITY_PROGRESS_INTERVAL_SECONDS = 0.5


class IntegrityAssetUnavailableError(RuntimeError):
    """Raised when analysis is requested outside the active Assets workspace."""


def same_source(left: ImmichAsset, right: ImmichAsset) -> bool:
    """Compare the strongest available live content identity."""

    if left.id != right.id or left.is_trashed or right.is_trashed:
        return False
    if left.checksum is not None or right.checksum is not None:
        return left.checksum is not None and left.checksum == right.checksum
    if left.file_modified_at != right.file_modified_at:
        return False
    left_size = source_file_size(left)
    right_size = source_file_size(right)
    return left_size is None or right_size is None or left_size == right_size


class IntegrityService:
    """Resolve cache state and submit idempotent integrity tasks."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
        tasks: TaskCoordinator,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._tasks = tasks

    async def _active_asset(self, asset_id: UUID) -> ImmichAsset:
        if not await self._assets.has_asset(asset_id):
            raise IntegrityAssetUnavailableError("The active asset was not found.")
        asset = await self._immich.get_asset(asset_id)
        if asset.is_trashed:
            raise IntegrityAssetUnavailableError("Trashed assets are available in Restore.")
        return asset

    async def state(self, asset_id: UUID) -> AssetIntegrityState:
        asset = await self._active_asset(asset_id)
        record = await self._reports.get(asset_id)
        active = await self._tasks.find_active(INTEGRITY_TASK_TYPE, f"asset:{asset_id}")
        return AssetIntegrityState(
            freshness=report_freshness(record, asset),
            report=public_report(record) if record is not None else None,
            active_task_id=active.id if active is not None else None,
        )

    async def analyze(self, asset_id: UUID, *, force: bool) -> AssetIntegrityAnalyzeResponse:
        asset = await self._active_asset(asset_id)
        record = await self._reports.get(asset_id)
        freshness = report_freshness(record, asset)
        active = await self._tasks.find_active(INTEGRITY_TASK_TYPE, f"asset:{asset_id}")
        if active is not None:
            return AssetIntegrityAnalyzeResponse(
                state="pending",
                freshness=freshness,
                report=public_report(record) if record is not None else None,
                task_id=active.id,
            )
        if freshness == "current" and record is not None and not force:
            return AssetIntegrityAnalyzeResponse(
                state="ready",
                freshness="current",
                report=public_report(record),
            )

        task = await self._tasks.submit(
            INTEGRITY_TASK_TYPE,
            {"asset_id": str(asset_id)},
            priority=60,
            lane_key=INTEGRITY_TASK_TYPE,
            deduplication_key=f"asset:{asset_id}",
        )
        return AssetIntegrityAnalyzeResponse(
            state="pending",
            freshness=freshness,
            report=public_report(record) if record is not None else None,
            task_id=task.id,
        )


class IntegrityTaskHandler:
    """Stream, analyze, verify, and atomically persist one original."""

    task_type = INTEGRITY_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 2

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._reports = reports

    async def _active_asset(self, asset_id: UUID) -> ImmichAsset:
        if not await self._assets.has_asset(asset_id):
            raise PermanentTaskError("The asset is no longer in the active workspace.")
        try:
            asset = await self._immich.get_asset(asset_id)
        except ImmichApiError as error:
            if error.status_code == 404:
                raise PermanentTaskError("The Immich asset was not found.") from error
            raise RetryableTaskError("Immich metadata is temporarily unavailable.") from error
        if asset.is_trashed:
            raise PermanentTaskError("The asset moved to Restore before analysis completed.")
        return asset

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        asset_id = UUID(str(payload["asset_id"]))
        source = await self._active_asset(asset_id)
        analyzer = FileIntegrityAnalyzer(source.original_mime_type, source.checksum)
        started = monotonic()

        await context.checkpoint(
            checkpoint={"phase": "opening", "asset_id": str(asset_id)},
            counters={"bytes_processed": 0},
            progress={
                "phase": "integrity",
                "completed": 0,
                "total": None,
                "percent": None,
                "detail": "Opening original from Immich…",
            },
        )

        try:
            async with self._immich.stream_original(
                asset_id, chunk_size=INTEGRITY_CHUNK_SIZE
            ) as original:
                total = original.content_length
                last_reported = monotonic()
                async for chunk in original.chunks:
                    analyzer.update(chunk)
                    now = monotonic()
                    if now - last_reported < INTEGRITY_PROGRESS_INTERVAL_SECONDS:
                        continue
                    await self._checkpoint(context, asset_id, analyzer.byte_size, total, started)
                    last_reported = now
        except ImmichApiError as error:
            if error.status_code == 404:
                raise PermanentTaskError("The Immich original was not found.") from error
            raise RetryableTaskError("The Immich original stream was interrupted.") from error

        await self._checkpoint(context, asset_id, analyzer.byte_size, total, started)
        await context.ensure_active()
        result = analyzer.finalize()
        await context.checkpoint(
            checkpoint={
                "phase": "finalizing",
                "asset_id": str(asset_id),
                "bytes_processed": result.byte_size,
            },
            counters={"bytes_processed": result.byte_size},
            progress={
                "phase": "finalizing",
                "completed": result.byte_size,
                "total": None,
                "percent": None,
                "detail": "Verifying the source and saving the report…",
            },
        )

        current = await self._active_asset(asset_id)
        if not same_source(source, current):
            raise RetryableTaskError("The source changed during integrity analysis.")
        report: AssetIntegrityReport = await self._reports.save(current, result)
        return TaskResult(
            summary={
                "asset_id": str(asset_id),
                "classification": report.classification,
                "byte_size": report.byte_size,
            },
            counters={"bytes_processed": report.byte_size},
        )

    @staticmethod
    async def _checkpoint(
        context: TaskContext,
        asset_id: UUID,
        completed: int,
        total: int | None,
        started: float,
    ) -> None:
        await context.ensure_active()
        elapsed = max(monotonic() - started, 0.001)
        percent = min(round(completed / total * 100, 1), 99.0) if total else None
        await context.checkpoint(
            checkpoint={
                "phase": "streaming",
                "asset_id": str(asset_id),
                "bytes_processed": completed,
            },
            counters={"bytes_processed": completed},
            progress={
                "phase": "integrity",
                "completed": completed,
                "total": total,
                "percent": percent,
                "detail": "Reading and hashing the original…",
                "bytes_per_second": round(completed / elapsed),
            },
        )

"""Bounded, durable orchestration for asset file-integrity analysis."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from io import BytesIO
from tempfile import SpooledTemporaryFile
from time import monotonic
from typing import Any
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.image_decode import decode_image
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
from companion.similarity_features import extract_visual_features
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
INTEGRITY_SPOOL_MEMORY_BYTES = 4 * 1024 * 1024
PREVIEW_PIXEL_NORMALIZATION_VERSION = 0

logger = logging.getLogger("uvicorn.error")


class IntegrityAssetUnavailableError(RuntimeError):
    """Raised when analysis is requested outside the active Assets workspace."""


def same_source(left: ImmichAsset, right: ImmichAsset) -> bool:
    """Compare the strongest available live content identity."""

    if left.id != right.id or left.is_trashed or right.is_trashed:
        return False
    if left.library_id is None and right.library_id is None and (
        left.checksum is not None or right.checksum is not None
    ):
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
    max_concurrency = 1

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
            logger.warning(
                "Integrity verification unavailable for asset %s: asset is no longer in the active workspace",
                asset_id,
            )
            raise PermanentTaskError("The asset is no longer in the active workspace.")
        try:
            asset = await self._immich.get_asset(asset_id)
        except ImmichApiError as error:
            if error.status_code == 404:
                logger.warning(
                    "Integrity verification unavailable for asset %s: Immich asset was not found",
                    asset_id,
                )
                raise PermanentTaskError("The Immich asset was not found.") from error
            logger.warning(
                "Integrity verification unavailable for asset %s: Immich metadata request failed: %s",
                asset_id,
                error,
            )
            raise RetryableTaskError("Immich metadata is temporarily unavailable.") from error
        if asset.is_trashed:
            logger.warning(
                "Integrity verification unavailable for asset %s (%s): asset moved to Restore",
                asset.id,
                asset.original_file_name,
            )
            raise PermanentTaskError("The asset moved to Restore before analysis completed.")
        return asset

    async def _oversized_preview_feature(self, source: ImmichAsset):
        """Build bounded visual evidence from Immich's generated preview."""

        try:
            preview = await self._immich.get_thumbnail(source.id, size="preview")
        except ImmichApiError as error:
            logger.warning(
                "Similarity preview unavailable: asset_id=%s filename=%s reason=%s",
                source.id,
                source.original_file_name,
                error,
            )
            return None

        feature = await asyncio.to_thread(
            extract_visual_features,
            BytesIO(preview.content),
            "jpeg",
        )
        if feature is None:
            logger.warning(
                "Similarity preview extraction failed: asset_id=%s filename=%s",
                source.id,
                source.original_file_name,
            )
            return None
        return replace(
            feature,
            width=source.width or feature.width,
            height=source.height or feature.height,
            pixel_normalization_version=PREVIEW_PIXEL_NORMALIZATION_VERSION,
        )

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        asset_id = UUID(str(payload["asset_id"]))
        report = await self.analyze(context, asset_id)
        return TaskResult(
            summary={
                "asset_id": str(asset_id),
                "classification": report.classification,
                "byte_size": report.byte_size,
            },
            counters={"bytes_processed": report.byte_size},
        )

    async def analyze(
        self,
        context: TaskContext,
        asset_id: UUID,
        *,
        publish_progress: bool = True,
    ) -> AssetIntegrityReport:
        """Run the shared bounded analyzer for one known synchronized asset."""

        source = await self._active_asset(asset_id)
        immich_content_checksum = source.checksum if source.library_id is None else None
        analyzer = FileIntegrityAnalyzer(source.original_mime_type, immich_content_checksum)
        started = monotonic()

        if publish_progress:
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
        else:
            await context.ensure_active()

        with SpooledTemporaryFile(max_size=INTEGRITY_SPOOL_MEMORY_BYTES) as spool:
            try:
                async with self._immich.stream_original(
                    asset_id, chunk_size=INTEGRITY_CHUNK_SIZE
                ) as original:
                    total = original.content_length
                    last_reported = monotonic()
                    async for chunk in original.chunks:
                        analyzer.update(chunk)
                        spool.write(chunk)
                        now = monotonic()
                        if now - last_reported < INTEGRITY_PROGRESS_INTERVAL_SECONDS:
                            continue
                        await self._checkpoint(
                            context,
                            asset_id,
                            analyzer.byte_size,
                            total,
                            started,
                            publish_progress=publish_progress,
                        )
                        last_reported = now
            except ImmichApiError as error:
                if error.status_code == 404:
                    logger.warning(
                        "Integrity verification unavailable for asset %s (%s): Immich original was not found",
                        source.id,
                        source.original_file_name,
                    )
                    raise PermanentTaskError("The Immich original was not found.") from error
                logger.warning(
                    "Integrity verification unavailable for asset %s (%s): original stream failed: %s",
                    source.id,
                    source.original_file_name,
                    error,
                )
                raise RetryableTaskError("The Immich original stream was interrupted.") from error

            await self._checkpoint(
                context,
                asset_id,
                analyzer.byte_size,
                total,
                started,
                publish_progress=publish_progress,
            )
            await context.ensure_active()
            result = analyzer.finalize()
            decoded = await asyncio.to_thread(decode_image, spool, result.detected_format)
            result = result.with_decode(
                supported=decoded.supported,
                valid=decoded.valid,
                width=decoded.width,
                height=decoded.height,
                immich_width=source.width,
                immich_height=source.height,
                issue=decoded.issue,
            )
            visual_feature = None
            if decoded.valid is True:
                visual_feature = await asyncio.to_thread(
                    extract_visual_features,
                    spool,
                    result.detected_format,
                )
            elif decoded.issue == "image_decode_limit_exceeded":
                visual_feature = await self._oversized_preview_feature(source)
                if visual_feature is not None:
                    logger.warning(
                        "Similarity feature using bounded preview: asset_id=%s filename=%s original_dimensions=%sx%s",
                        source.id,
                        source.original_file_name,
                        source.width,
                        source.height,
                    )
            else:
                logger.warning(
                    "Similarity feature skipped: asset_id=%s filename=%s format=%s decode_supported=%s decode_valid=%s issue=%s",
                    source.id,
                    source.original_file_name,
                    result.detected_format,
                    decoded.supported,
                    decoded.valid,
                    decoded.issue,
                )
        expected_size = source_file_size(source)
        if expected_size is not None and result.byte_size != expected_size:
            logger.warning(
                "Integrity verification unavailable for asset %s (%s): streamed size %s did not match Immich metadata size %s",
                source.id,
                source.original_file_name,
                result.byte_size,
                expected_size,
            )
            raise RetryableTaskError("The streamed original size did not match Immich metadata.")
        if publish_progress:
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
        else:
            await context.ensure_active()

        current = await self._active_asset(asset_id)
        if not same_source(source, current):
            logger.warning(
                "Integrity verification unavailable for asset %s (%s): source changed during analysis",
                source.id,
                source.original_file_name,
            )
            raise RetryableTaskError("The source changed during integrity analysis.")
        return await self._reports.save(current, result, visual_feature)

    @staticmethod
    async def _checkpoint(
        context: TaskContext,
        asset_id: UUID,
        completed: int,
        total: int | None,
        started: float,
        *,
        publish_progress: bool,
    ) -> None:
        await context.ensure_active()
        if not publish_progress:
            return
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

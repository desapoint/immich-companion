"""Duplicate evidence task handlers."""

from __future__ import annotations

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.discovery import (
    GroupDiscoveryProvider,
    ImmichDuplicateProvider,
)
from companion.duplicate_schema import (
    DuplicateAnalysisOptions,
)
from companion.immich import (
    ImmichApiClient,
    ImmichApiError,
    ImmichAsset,
)
from companion.integrity_repository import (
    IntegrityRepository,
    preservation_feature_freshness,
    report_freshness,
)
from companion.integrity_service import (
    INTEGRITY_CHUNK_SIZE,
    INTEGRITY_TASK_TYPE,
    IntegrityTaskHandler,
)
from companion.similarity_index_service import SimilarityIndexMaintainer
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
)
from companion.task_schema import TaskResult

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"

logger = logging.getLogger(__name__)



class DuplicateResolutionTaskHandler:
    """Execute one reviewed duplicate plan in the serialized action lane."""

    task_type = DUPLICATE_RESOLUTION_TASK_TYPE
    lane_key = "asset_action"
    max_concurrency = 1

    def __init__(self, service: Any) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        return await self._service.execute_plan(context, UUID(str(payload["plan_id"])))


class CrossSourceDuplicateTaskHandler:
    """Verify originals and populate preservation evidence for discovered groups."""

    task_type = CROSS_SOURCE_DUPLICATE_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
        integrity: IntegrityTaskHandler,
        *,
        include_preservation: bool = False,
        discovery: GroupDiscoveryProvider | None = None,
        similarity_indexer: SimilarityIndexMaintainer | None = None,
        shared_original_cache_path: Path | None = None,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._integrity = integrity
        self._include_preservation = include_preservation
        self._discovery = discovery or ImmichDuplicateProvider(immich)
        self._similarity_indexer = similarity_indexer
        self._shared_original_cache_path = shared_original_cache_path

    async def _download_shared_original(
        self,
        context: TaskContext,
        asset: ImmichAsset,
    ) -> tuple[Path, int]:
        """Acquire one caller-owned original for all stale evidence branches."""

        suffix = Path(asset.original_file_name or "").suffix.lower()
        if not suffix or len(suffix) > 16 or any(character in suffix for character in "/\\"):
            suffix = ".img"
        temporary_path: Path | None = None
        total = 0
        try:
            with NamedTemporaryFile(
                prefix="immich-companion-shared-original-",
                suffix=suffix,
                dir=self._shared_original_cache_path,
                delete=False,
            ) as prepared:
                temporary_path = Path(prepared.name)
                async with self._immich.stream_original(
                    asset.id,
                    chunk_size=INTEGRITY_CHUNK_SIZE,
                ) as original:
                    expected_stream_bytes = original.content_length
                    async for chunk in original.chunks:
                        await context.ensure_active()
                        prepared.write(chunk)
                        total += len(chunk)
            if expected_stream_bytes is not None and total != expected_stream_bytes:
                raise RetryableTaskError(
                    "The shared original stream ended before its declared content length."
                )
            if asset.file_size_bytes is not None and total != asset.file_size_bytes:
                raise RetryableTaskError(
                    "The shared original size did not match synchronized Immich metadata."
                )
            assert temporary_path is not None
            return temporary_path, total
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        options = DuplicateAnalysisOptions.model_validate(payload)
        batch_reader = getattr(self._discovery, "discover_batches", None)

        async def discovery_batches():
            if callable(batch_reader):
                async for batch in batch_reader():
                    yield batch
                return
            yield await self._discovery.discover()

        group_count = 0
        candidate_file_count = 0
        files_attempted = 0
        unavailable = 0
        visual_assets = 0
        visual_unavailable = 0
        shared_original_downloads = 0
        shared_original_bytes = 0
        processed_asset_ids: set[UUID] = set()

        await context.checkpoint(
            checkpoint={"phase": "fingerprinting"},
            counters={
                "files_attempted": 0,
                "files_unavailable": 0,
                "visual_assets": 0,
                "visual_unavailable": 0,
                "shared_original_downloads": 0,
                "shared_original_bytes": 0,
            },
            progress={
                "phase": "duplicate_fingerprints",
                "completed": 0,
                "total": None,
                "percent": None,
                "detail": "Streaming exact duplicate groups for verification…",
            },
        )
        share_capable = bool(
            self._similarity_indexer is not None
            and callable(getattr(self._similarity_indexer, "has_current", None))
        )
        async for groups in discovery_batches():
            group_count += len(groups)
            candidates: dict[UUID, ImmichAsset] = {}
            for group in groups:
                for asset in group.assets:
                    if asset.id in processed_asset_ids:
                        continue
                    if (
                        asset.library_id is not None
                        or options.verify_upload_streams
                        or self._include_preservation
                        and asset.asset_type == "IMAGE"
                    ):
                        if asset.file_size_bytes is None:
                            asset = await self._immich.get_asset(asset.id)
                        candidates[asset.id] = asset
                        processed_asset_ids.add(asset.id)

            candidate_file_count += len(candidates)
            if not candidates:
                continue
            reports = await self._reports.get_many(list(candidates))
            features = (
                await self._reports.get_preservation_features(list(candidates))
                if self._include_preservation
                else {}
            )
            pending = [
                asset
                for asset in candidates.values()
                if not asset.is_offline
                and (
                    (
                        (
                            asset.library_id is None
                            and options.verify_upload_streams
                            or asset.library_id is not None
                        )
                        and report_freshness(reports.get(asset.id), asset) != "current"
                    )
                    or (
                        self._include_preservation
                        and asset.asset_type == "IMAGE"
                        and preservation_feature_freshness(features.get(asset.id), asset)
                        != "current"
                    )
                )
            ]
            visual_candidates = [
                asset
                for asset in candidates.values()
                if asset.asset_type == "IMAGE" and not asset.is_offline
            ]
            visual_assets += len(visual_candidates)
            pending_ids = {asset.id for asset in pending}
            visual_pending_ids: set[UUID] = set()

            if self._similarity_indexer is not None:
                if share_capable:
                    for asset in visual_candidates:
                        await context.ensure_active()
                        if not await self._similarity_indexer.has_current(asset.id):
                            visual_pending_ids.add(asset.id)
                    for asset in visual_candidates:
                        if asset.id not in visual_pending_ids or asset.id in pending_ids:
                            continue
                        await context.ensure_active()
                        if not await self._similarity_indexer.ensure_asset(context, asset.id):
                            visual_unavailable += 1
                            logger.warning(
                                "Duplicate candidate visual evidence unavailable: "
                                "asset_id=%s filename=%s",
                                asset.id,
                                asset.original_file_name,
                            )
                else:
                    for asset in visual_candidates:
                        await context.ensure_active()
                        if not await self._similarity_indexer.ensure_asset(context, asset.id):
                            visual_unavailable += 1
                            logger.warning(
                                "Duplicate candidate visual evidence unavailable: "
                                "asset_id=%s filename=%s",
                                asset.id,
                                asset.original_file_name,
                            )

            for asset in pending:
                await context.ensure_active()
                files_attempted += 1
                await self._assets.refresh_asset(asset)
                appearance_needed = share_capable and asset.id in visual_pending_ids
                prepared_path: Path | None = None
                prepared_bytes: int | None = None
                shared_failed = False
                if appearance_needed:
                    try:
                        prepared_path, prepared_bytes = await self._download_shared_original(
                            context,
                            asset,
                        )
                        shared_original_downloads += 1
                        shared_original_bytes += prepared_bytes
                    except (ImmichApiError, OSError, RetryableTaskError) as error:
                        shared_failed = True
                        logger.warning(
                            "Shared duplicate original acquisition failed; falling back "
                            "to independent evidence paths: asset_id=%s filename=%s "
                            "error_type=%s reason=%s",
                            asset.id,
                            asset.original_file_name,
                            type(error).__name__,
                            error,
                        )

                try:
                    if appearance_needed and self._similarity_indexer is not None:
                        visual_ready = await self._similarity_indexer.ensure_asset(
                            context,
                            asset.id,
                            source=asset,
                            original_path=None if shared_failed else prepared_path,
                            original_source_bytes=None if shared_failed else prepared_bytes,
                        )
                        if not visual_ready:
                            visual_unavailable += 1
                            logger.warning(
                                "Duplicate candidate visual evidence unavailable: "
                                "asset_id=%s filename=%s",
                                asset.id,
                                asset.original_file_name,
                            )

                    try:
                        if prepared_path is not None and not shared_failed:
                            await self._integrity.analyze(
                                context,
                                asset.id,
                                publish_progress=False,
                                source=asset,
                                original_path=prepared_path,
                                original_source_bytes=prepared_bytes,
                            )
                        else:
                            await self._integrity.analyze(
                                context,
                                asset.id,
                                publish_progress=False,
                                source=asset,
                            )
                    except (PermanentTaskError, RetryableTaskError, ImmichApiError) as error:
                        unavailable += 1
                        logger.warning(
                            "Duplicate candidate verification failed: asset_id=%s filename=%s "
                            "source=%s error_type=%s reason=%s",
                            asset.id,
                            asset.original_file_name,
                            "upload" if asset.library_id is None else "external",
                            type(error).__name__,
                            error,
                        )
                finally:
                    if prepared_path is not None:
                        prepared_path.unlink(missing_ok=True)

                await context.checkpoint(
                    checkpoint={"phase": "fingerprinting", "asset_id": str(asset.id)},
                    counters={
                        "files_attempted": files_attempted,
                        "files_unavailable": unavailable,
                        "visual_assets": visual_assets,
                        "visual_unavailable": visual_unavailable,
                        "shared_original_downloads": shared_original_downloads,
                        "shared_original_bytes": shared_original_bytes,
                    },
                    progress={
                        "phase": "duplicate_fingerprints",
                        "completed": files_attempted,
                        "total": None,
                        "percent": None,
                        "detail": (
                            f"Verified {files_attempted} exact duplicate candidate files"
                        ),
                    },
                )

        if unavailable:
            logger.warning(
                "Duplicate candidate verification completed with unavailable files: "
                "attempted=%s unavailable=%s",
                files_attempted,
                unavailable,
            )
        await context.checkpoint(
            checkpoint={"phase": "complete"},
            counters={
                "files_attempted": files_attempted,
                "files_unavailable": unavailable,
                "visual_assets": visual_assets,
                "visual_unavailable": visual_unavailable,
                "shared_original_downloads": shared_original_downloads,
                "shared_original_bytes": shared_original_bytes,
            },
            progress={
                "phase": "complete",
                "completed": files_attempted,
                "total": files_attempted,
                "percent": 100.0,
                "detail": "Exact duplicate candidate verification is ready.",
            },
        )
        return TaskResult(
            summary={"duplicate_group_count": group_count},
            counters={
                "duplicate_groups": group_count,
                "candidate_files": candidate_file_count,
                "files_attempted": files_attempted,
                "files_unavailable": unavailable,
                "visual_assets": visual_assets,
                "visual_unavailable": visual_unavailable,
                "shared_original_downloads": shared_original_downloads,
                "shared_original_bytes": shared_original_bytes,
            },
        )

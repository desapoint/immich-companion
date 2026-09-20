"""Asset detail, restore, and media proxy route registration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from companion.action_schema import AssetSelectionRequest
from companion.asset_schema import AssetDetail, AssetSelectionSyncResult
from companion.immich import ImmichApiClient, ImmichApiError
from companion.media_proxy import media_stream_response
from companion.similarity_cache import CachedPreview, SimilarityCacheManager
from companion.trash_purge_service import (
    TrashPurgeExecuteRequest,
    TrashPurgePlan,
    TrashPurgeResult,
    TrashPurgeSelection,
    TrashPurgeService,
)


class RestoreRequest(BaseModel):
    """A bounded restore target with optional server-side exclusions."""

    ids: list[UUID] = Field(default_factory=list, max_length=10_000)
    all: bool = False
    excluded_ids: list[UUID] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def validate_target(self) -> RestoreRequest:
        if self.all == bool(self.ids):
            raise ValueError("Specify either one or more ids or all=true.")
        if self.ids and self.excluded_ids:
            raise ValueError("excluded_ids are only valid with all=true.")
        if len(set(self.excluded_ids)) != len(self.excluded_ids):
            raise ValueError("excluded_ids must be unique.")
        return self


async def restore_batch_with_accounting(
    asset_ids: list[UUID],
    restore_targets: Callable[[list[UUID]], Awaitable[None]],
    get_asset: Callable[[UUID], Awaitable[object]],
) -> tuple[int, list[UUID]]:
    """Restore one bounded batch and classify provider-side partial success."""

    try:
        await restore_targets(asset_ids)
    except ImmichApiError:
        async def still_trashed(asset_id: UUID) -> bool:
            try:
                return bool((await get_asset(asset_id)).is_trashed)  # type: ignore[attr-defined]
            except ImmichApiError:
                return True

        statuses = await asyncio.gather(*(still_trashed(asset_id) for asset_id in asset_ids))
        return (
            sum(not trashed for trashed in statuses),
            [
                asset_id
                for asset_id, trashed in zip(asset_ids, statuses, strict=True)
                if trashed
            ],
        )
    return len(asset_ids), []




def register_media_restore_routes(
    app: FastAPI,
    *,
    immich: ImmichApiClient,
    require_immich: Callable[[], ImmichApiClient],
    require_asset_sync: Callable[[], object],
    require_asset_repository: Callable[[], object],
    asset_repository: object | None,
    asset_sync: object | None,
    runtime_settings,
    task_coordinator,
    similarity_cache: SimilarityCacheManager,
    selection_digest: Callable[[list[UUID]], str],
    batches: Callable[[list[UUID], int], list[list[UUID]]],
    map_immich_error: Callable[[ImmichApiError], HTTPException],
    map_action_error: Callable[[RuntimeError], HTTPException],
    trash_purge_service: TrashPurgeService | None,
) -> None:
    """Register detail, restore, synchronization, and media proxy endpoints."""

    @app.get("/api/assets/{asset_id}", response_model=AssetDetail)
    async def asset_detail(asset_id: UUID) -> AssetDetail:
        try:
            asset = await immich.get_asset(asset_id)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        if asset.is_trashed:
            raise HTTPException(status_code=404, detail="Trashed assets are available in Restore.")
        return AssetDetail.from_immich(asset, immich.public_asset_url(asset_id))

    @app.get("/api/restore/{asset_id}", response_model=AssetDetail)
    async def restore_asset_detail(asset_id: UUID) -> AssetDetail:
        try:
            asset = await require_immich().get_asset(asset_id)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        if not asset.is_trashed:
            raise HTTPException(status_code=404, detail="The asset is not in Restore.")
        return AssetDetail.from_immich(asset, immich.public_asset_url(asset_id))

    @app.post("/api/restore/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def restore_asset(asset_id: UUID) -> Response:
        """Restore one live Immich asset, then refresh its normal workspace data."""

        sync = require_asset_sync()
        try:
            asset = await require_immich().get_asset(asset_id)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        if not asset.is_trashed:
            raise HTTPException(status_code=404, detail="The asset is not in Restore.")
        try:
            await sync.restore_targets([asset_id])
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/restore")
    async def restore_assets(request: RestoreRequest) -> dict[str, object]:
        """Restore selected or all live Immich trash in paced server-side batches.

        A failed batch is inspected after the Immich call so the response reflects
        assets that were actually restored even when the provider partially applied
        the request. Remaining batches continue independently.
        """

        sync = require_asset_sync()
        pacing = await sync._runtime_sync_settings.get()
        if request.all:
            try:
                excluded_ids = set(request.excluded_ids)
                asset_ids = [
                    asset.id
                    async for asset in require_immich().iter_trashed_assets()
                    if asset.id not in excluded_ids
                ]
            except ImmichApiError as error:
                raise map_immich_error(error) from error
        else:
            asset_ids = list(dict.fromkeys(request.ids))
            resolved_assets = []
            for batch in batches(asset_ids, pacing.full_batch_size):
                try:
                    resolved_assets.extend(
                        await asyncio.gather(
                            *(require_immich().get_asset(asset_id) for asset_id in batch)
                        )
                    )
                except ImmichApiError as error:
                    raise map_immich_error(error) from error
            if any(not asset.is_trashed for asset in resolved_assets):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Some requested assets are no longer in Restore.",
                )
        if not asset_ids:
            raise HTTPException(status_code=404, detail="No matching trashed assets were found.")
        restore_batches = batches(asset_ids, pacing.full_batch_size)
        restored_count = 0
        failed_ids: list[UUID] = []
        for index, batch in enumerate(restore_batches):
            batch_restored, batch_failed = await restore_batch_with_accounting(
                batch,
                sync.restore_targets,
                require_immich().get_asset,
            )
            restored_count += batch_restored
            failed_ids.extend(batch_failed)
            if index < len(restore_batches) - 1:
                await asyncio.sleep(pacing.full_min_batch_delay_seconds)
        return {
            "restored": restored_count,
            "requested": len(asset_ids),
            "failed_ids": [str(asset_id) for asset_id in failed_ids],
        }

    def require_trash_purge_service() -> TrashPurgeService:
        if trash_purge_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Permanent trash deletion requires the companion database.",
            )
        return trash_purge_service

    @app.post("/api/trash/purge/plan", response_model=TrashPurgePlan)
    async def plan_trash_purge(request: TrashPurgeSelection) -> TrashPurgePlan:
        try:
            return await require_trash_purge_service().plan(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post("/api/trash/purge/execute", response_model=TrashPurgeResult)
    async def execute_trash_purge(
        request: TrashPurgeExecuteRequest,
    ) -> TrashPurgeResult:
        try:
            return await require_trash_purge_service().execute(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post("/api/assets/{asset_id}/sync", response_model=AssetDetail)
    async def synchronize_asset(asset_id: UUID) -> AssetDetail:
        """Refresh one asset and its metadata/relationship snapshot."""

        require_asset_repository()
        assert asset_sync is not None
        try:
            await asset_sync.reconcile_targets([asset_id])
            asset = await immich.get_asset(asset_id)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        return AssetDetail.from_immich(asset, immich.public_asset_url(asset_id))

    @app.post("/api/assets/sync/selection", response_model=AssetSelectionSyncResult)
    async def synchronize_asset_selection(
        request: AssetSelectionRequest,
    ) -> AssetSelectionSyncResult:
        """Synchronize the exact backend-resolved selection."""

        repository = require_asset_repository()
        assert asset_sync is not None
        resolution = await repository.resolve_selection(
            request,
            max_targets=runtime_settings.action_max_targets,
        )
        if task_coordinator is not None:
            task_ids = [*resolution.ids, *resolution.missing_ids]
            task = await task_coordinator.submit(
                "asset_selection_sync",
                {"asset_ids": [str(identifier) for identifier in task_ids]},
                priority=90,
                lane_key="asset_repair",
                deduplication_key="asset-selection-sync:" + selection_digest(task_ids),
            )
            await task_coordinator.start()
            return AssetSelectionSyncResult(
                requested=len(task_ids),
                synced=0,
                task_id=task.id,
            )
        await asset_sync.reconcile_targets(resolution.ids)
        return AssetSelectionSyncResult(requested=len(resolution.ids), synced=len(resolution.ids))

    @app.get("/api/assets/{asset_id}/thumbnail", response_class=Response)
    async def asset_thumbnail(
        asset_id: UUID,
        size: Literal["thumbnail", "preview", "fullsize"] = "thumbnail",
    ) -> Response:
        cache_key: str | None = None
        if size != "fullsize" and asset_repository is not None:
            synchronized = await asset_repository.get_immich_assets([asset_id])
            source = synchronized.get(asset_id)
            if source is not None:
                source_fingerprint = (
                    f"{source.file_modified_at.isoformat()}:{source.file_size_bytes}"
                )
                cache_key = f"{asset_id}:{size}:{source_fingerprint}"
        if cache_key is not None:
            cached = await asyncio.to_thread(similarity_cache.preview.get, cache_key)
            if cached is not None:
                headers = {
                    "Cache-Control": cached.cache_control or "private, max-age=300",
                    "X-Content-Type-Options": "nosniff",
                    "X-Companion-Cache": "hit",
                }
                if cached.etag:
                    headers["ETag"] = cached.etag
                return Response(
                    content=cached.content,
                    media_type=cached.media_type,
                    headers=headers,
                )
        try:
            media = await immich.get_thumbnail(asset_id, size=size)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        if cache_key is not None:
            await asyncio.to_thread(
                similarity_cache.preview.put,
                cache_key,
                CachedPreview(
                    content=media.content,
                    media_type=media.media_type,
                    etag=media.etag,
                    cache_control=media.cache_control,
                ),
            )
        headers = {
            "Cache-Control": media.cache_control or "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "X-Companion-Cache": "miss" if cache_key is not None else "bypass",
        }
        if media.etag:
            headers["ETag"] = media.etag
        return Response(content=media.content, media_type=media.media_type, headers=headers)

    @app.get("/api/assets/{asset_id}/original")
    async def asset_original(asset_id: UUID) -> StreamingResponse:
        """Stream an original from Immich without materializing it in Companion."""

        try:
            return await media_stream_response(immich.stream_original(asset_id))
        except ImmichApiError as error:
            raise map_immich_error(error) from error
    @app.get("/api/assets/{asset_id}/video/playback")
    async def asset_video_playback(asset_id: UUID, request: Request) -> StreamingResponse:
        """Proxy Immich's browser-compatible, byte-range-aware video stream."""

        try:
            return await media_stream_response(
                immich.stream_video_playback(
                    asset_id,
                    range_header=request.headers.get("range"),
                    if_range_header=request.headers.get("if-range"),
                )
            )
        except ImmichApiError as error:
            raise map_immich_error(error) from error

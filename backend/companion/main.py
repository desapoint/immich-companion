"""FastAPI entrypoint for Immich Companion."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from companion.action_repository import ActionRepository
from companion.action_schema import (
    AssetActionExecuteRequest,
    AssetActionPlan,
    AssetActionPlanRequest,
    AssetActionResult,
    AssetSelectionRequest,
    AssetSelectionResolution,
)
from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
    AssetActionService,
    DestructiveActionsDisabledError,
    EmptySelectionError,
)
from companion.asset_repository import AssetRepository
from companion.asset_schema import (
    AlbumOption,
    AssetDetail,
    AssetSearchMatchRequest,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetSortDirection,
    AssetSortField,
    AssetSummary,
    AssetSyncResult,
    StructuredAssetSearchQuery,
    TagOption,
)
from companion.asset_service import AssetSyncService
from companion.config import Settings, get_settings
from companion.database import DatabaseManager, PostgresHealthClient
from companion.immich import ImmichApiClient, ImmichApiError
from companion.migrate import run_migrations


def create_app(
    settings: Settings | None = None,
    immich_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Create an application with injectable settings/transport for tests."""

    runtime_settings = settings or get_settings()
    immich = ImmichApiClient(runtime_settings, transport=immich_transport)
    database_health = PostgresHealthClient(runtime_settings)
    database = (
        DatabaseManager(runtime_settings)
        if runtime_settings.companion_database_url is not None
        else None
    )
    asset_repository = AssetRepository(database) if database is not None else None
    asset_sync = (
        AssetSyncService(immich, asset_repository) if asset_repository is not None else None
    )
    action_service = (
        AssetActionService(
            runtime_settings,
            immich,
            asset_repository,
            ActionRepository(database),
            asset_sync,
        )
        if database is not None and asset_repository is not None and asset_sync is not None
        else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await asyncio.to_thread(run_migrations, runtime_settings)
        try:
            yield
        finally:
            if database is not None:
                await database.dispose()

    app = FastAPI(
        title="Immich Companion",
        version=runtime_settings.companion_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    async def health_payload() -> dict[str, object]:
        immich_status, database_status = await asyncio.gather(
            immich.check(),
            database_health.check(),
        )
        database_ready = database_status["status"] in {"ok", "not_configured"}
        ready = immich_status["status"] == "ok" and database_ready
        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "environment": runtime_settings.companion_env,
            "safe_mode": not runtime_settings.allow_destructive_actions,
            "dependencies": {
                "immich": immich_status,
                "companion_database": database_status,
            },
        }

    @app.get("/api/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return await health_payload()

    @app.get("/api/ready")
    async def ready() -> dict[str, object]:
        payload = await health_payload()
        if not payload["ready"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=payload,
            )
        return payload

    @app.get("/api/version")
    async def version() -> dict[str, str]:
        return {
            "name": "immich-companion",
            "version": runtime_settings.companion_version,
            "environment": runtime_settings.companion_env,
        }

    @app.get("/api/capabilities")
    async def capabilities() -> dict[str, object]:
        return {
            "destructive_actions": runtime_settings.allow_destructive_actions,
            "immich_api": runtime_settings.immich_configured,
            "companion_database": runtime_settings.companion_database_url is not None,
            "implemented": [
                "health",
                "version",
                "capabilities",
                "asset_sync",
                "asset_search",
                "asset_details",
                "asset_previews",
                "structured_asset_search",
                "album_filters",
                "tag_filters",
                "selection_resolution",
                "reviewed_asset_actions",
            ],
            "planned": [
                "action_jobs",
                "integrity",
                "exact_dedupe",
                "tagging",
                "visual_similarity",
            ],
        }

    def require_asset_repository() -> AssetRepository:
        if asset_repository is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return asset_repository

    def map_immich_error(error: ImmichApiError) -> HTTPException:
        if error.status_code == status.HTTP_404_NOT_FOUND:
            return HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The Immich asset was not found.",
            )
        if error.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
            return HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Immich rejected the companion asset request.",
            )
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Immich could not complete the asset request.",
        )

    def require_action_service() -> AssetActionService:
        if action_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return action_service

    def map_action_error(error: RuntimeError) -> HTTPException:
        if isinstance(error, ActionPlanNotFoundError):
            return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
        if isinstance(error, DestructiveActionsDisabledError):
            return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
        if isinstance(error, ActionPlanConflictError):
            return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
        if isinstance(error, EmptySelectionError):
            return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
        if isinstance(error, ValueError):
            return HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(error),
            )
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The companion action could not be completed.",
        )

    def add_public_asset_urls(response: AssetSearchResponse) -> AssetSearchResponse:
        """Attach only the configured browser-safe Immich URL to card results."""

        return response.model_copy(
            update={
                "items": [
                    item.model_copy(update={"immich_url": immich.public_asset_url(item.id)})
                    for item in response.items
                ]
            }
        )

    def add_public_asset_url(asset: AssetSummary | None) -> AssetSummary | None:
        """Attach a browser-safe Immich URL to one matching card."""

        if asset is None:
            return None
        return asset.model_copy(update={"immich_url": immich.public_asset_url(asset.id)})

    @app.post("/api/assets/sync", response_model=AssetSyncResult)
    async def synchronize_assets() -> AssetSyncResult:
        require_asset_repository()
        assert asset_sync is not None
        try:
            return await asset_sync.synchronize()
        except ImmichApiError as error:
            raise map_immich_error(error) from error

    @app.get("/api/assets", response_model=AssetSearchResponse)
    async def search_assets(
        query: str | None = Query(default=None, max_length=500),
        asset_type: Literal["IMAGE", "VIDEO", "AUDIO", "OTHER"] | None = Query(
            default=None,
            alias="type",
        ),
        taken_after: datetime | None = None,
        taken_before: datetime | None = None,
        min_width: int | None = Query(default=None, ge=1),
        max_width: int | None = Query(default=None, ge=1),
        min_height: int | None = Query(default=None, ge=1),
        max_height: int | None = Query(default=None, ge=1),
        min_aspect_ratio: float | None = Query(default=None, gt=0),
        max_aspect_ratio: float | None = Query(default=None, gt=0),
        favorite: bool | None = None,
        archived: bool | None = None,
        trashed: bool | None = None,
        sort_field: AssetSortField = "taken_at",
        sort_direction: AssetSortDirection = "desc",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=48, ge=1, le=200),
    ) -> AssetSearchResponse:
        repository = require_asset_repository()
        criteria = AssetSearchQuery(
            query=query,
            asset_type=asset_type,
            taken_after=taken_after,
            taken_before=taken_before,
            min_width=min_width,
            max_width=max_width,
            min_height=min_height,
            max_height=max_height,
            min_aspect_ratio=min_aspect_ratio,
            max_aspect_ratio=max_aspect_ratio,
            favorite=favorite,
            archived=archived,
            trashed=trashed,
            sort_field=sort_field,
            sort_direction=sort_direction,
            page=page,
            page_size=page_size,
        )
        return add_public_asset_urls(await repository.search(criteria))

    @app.post("/api/assets/search", response_model=AssetSearchResponse)
    async def search_assets_structured(
        criteria: StructuredAssetSearchQuery,
    ) -> AssetSearchResponse:
        repository = require_asset_repository()
        return add_public_asset_urls(await repository.search_structured(criteria))

    @app.post(
        "/api/assets/{asset_id}/search-match",
        response_model=AssetSummary | None,
    )
    async def match_asset_search(
        asset_id: UUID,
        criteria: AssetSearchMatchRequest,
    ) -> AssetSummary | None:
        repository = require_asset_repository()
        return add_public_asset_url(
            await repository.find_structured_match(asset_id, criteria)
        )

    @app.get("/api/albums", response_model=list[AlbumOption])
    async def search_album_options() -> list[AlbumOption]:
        repository = require_asset_repository()
        return await repository.list_albums()

    @app.get("/api/tags", response_model=list[TagOption])
    async def search_tag_options() -> list[TagOption]:
        repository = require_asset_repository()
        return await repository.list_tags()

    @app.post("/api/assets/selection/resolve", response_model=AssetSelectionResolution)
    async def resolve_asset_selection(
        selection: AssetSelectionRequest,
    ) -> AssetSelectionResolution:
        service = require_action_service()
        try:
            return await service.resolve_selection(selection)
        except ValueError as error:
            raise map_action_error(error) from error

    @app.post("/api/assets/actions/plan", response_model=AssetActionPlan)
    async def plan_asset_action(request: AssetActionPlanRequest) -> AssetActionPlan:
        service = require_action_service()
        try:
            return await service.plan(request)
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.post("/api/assets/actions/execute", response_model=AssetActionResult)
    async def execute_asset_action(
        request: AssetActionExecuteRequest,
    ) -> AssetActionResult:
        service = require_action_service()
        try:
            return await service.execute(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.get("/api/assets/{asset_id}", response_model=AssetDetail)
    async def asset_detail(asset_id: UUID) -> AssetDetail:
        try:
            asset = await immich.get_asset(asset_id)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        return AssetDetail.from_immich(asset, immich.public_asset_url(asset_id))

    @app.get("/api/assets/{asset_id}/thumbnail", response_class=Response)
    async def asset_thumbnail(
        asset_id: UUID,
        size: Literal["thumbnail", "preview"] = "thumbnail",
    ) -> Response:
        try:
            media = await immich.get_thumbnail(asset_id, size=size)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        headers = {
            "Cache-Control": media.cache_control or "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        }
        if media.etag:
            headers["ETag"] = media.etag
        return Response(content=media.content, media_type=media.media_type, headers=headers)

    @app.get("/api/assets/{asset_id}/original", response_class=Response)
    async def asset_original(asset_id: UUID) -> Response:
        try:
            media = await immich.get_original(asset_id)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        headers = {
            "Cache-Control": media.cache_control or "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        }
        if media.etag:
            headers["ETag"] = media.etag
        return Response(content=media.content, media_type=media.media_type, headers=headers)

    if runtime_settings.companion_env == "test":

        @app.get("/api/test-state")
        async def test_state() -> dict[str, object]:
            state_file = runtime_settings.companion_test_state_file
            if state_file is None or not state_file.is_file():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The disposable environment has not completed its seed bootstrap.",
                )
            try:
                payload = json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The disposable environment seed state is unreadable.",
                ) from error
            if not isinstance(payload, dict):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The disposable environment seed state is invalid.",
                )
            return payload

    frontend_dir = runtime_settings.companion_frontend_dir
    frontend_index = frontend_dir / "index.html" if frontend_dir else None

    if frontend_index and frontend_index.is_file():
        frontend_assets = frontend_dir / "assets"
        if frontend_assets.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=frontend_assets),
                name="frontend-assets",
            )

        @app.get("/", response_class=FileResponse, include_in_schema=False)
        async def frontend_index_route() -> FileResponse:
            return FileResponse(frontend_index)

        @app.get("/{frontend_path:path}", response_class=FileResponse, include_in_schema=False)
        async def frontend_fallback(frontend_path: str) -> FileResponse:
            if frontend_path == "api" or frontend_path.startswith("api/"):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return FileResponse(frontend_index)
    else:

        @app.get("/", include_in_schema=False)
        async def frontend_unavailable() -> None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Frontend assets are not installed. Run the Vite development server.",
            )

    return app


app = create_app()

"""FastAPI entrypoint for Immich Companion."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from croniter import CroniterBadCronError, croniter
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from companion.action_repository import ActionRepository
from companion.action_schema import (
    AssetActionExecuteRequest,
    AssetActionPlan,
    AssetActionPlanRequest,
    AssetActionResult,
    AssetActionTaskStart,
    AssetSelectionRequest,
    AssetSelectionResolution,
    SelectionSetMembershipRequest,
    SelectionSetMembershipResponse,
    SelectionSetMembersRequest,
    SelectionSetView,
)
from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
    AssetActionService,
    AssetActionTaskHandler,
    DestructiveActionsDisabledError,
    EmptySelectionError,
    selection_digest,
)
from companion.asset_repository import AssetRepository
from companion.asset_schema import (
    AlbumOption,
    AssetDetail,
    AssetRestoreRequest,
    AssetSearchMatchRequest,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetSelectionSyncResult,
    AssetSortDirection,
    AssetSortField,
    AssetSummary,
    AssetSyncResult,
    StructuredAssetSearchQuery,
    TagOption,
)
from companion.asset_service import AssetSyncService, batches
from companion.config import Settings, get_settings
from companion.database import DatabaseManager, PostgresHealthClient
from companion.duplicate_schema import (
    CrossSourceDuplicateResult,
    CrossSourceDuplicateTaskStart,
    DuplicateAnalysisOptions,
    DuplicateResolutionExecuteRequest,
    DuplicateResolutionPlan,
    DuplicateResolutionPlanRequest,
)
from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
    DuplicateResolutionTaskHandler,
)
from companion.immich import ImmichApiClient, ImmichApiError, ImmichTag
from companion.integrity_repository import IntegrityRepository
from companion.integrity_schema import (
    AssetIntegrityAnalyzeRequest,
    AssetIntegrityAnalyzeResponse,
    AssetIntegrityState,
)
from companion.integrity_service import (
    IntegrityAssetUnavailableError,
    IntegrityService,
    IntegrityTaskHandler,
)
from companion.migrate import run_migrations
from companion.relation_schema import (
    AlbumCreateRequest,
    AlbumManagementItem,
    AlbumUpdateRequest,
    RelationBatchDeleteRequest,
    RelationPage,
    TagCreateRequest,
    TagManagementItem,
    TagUpdateRequest,
)
from companion.sync_repository import SyncRepository
from companion.sync_schema import (
    SyncCoordinatorStatus,
    SyncRunStatus,
    SyncStartRequest,
)
from companion.sync_settings import SyncRuntimeSettingsRepository, SyncRuntimeSettingsUpdate
from companion.task_coordinator import TaskCoordinator
from companion.task_schema import TaskEvent, TaskScheduleUpdate, TaskScheduleView, TaskStatusView


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
    integrity_repository = IntegrityRepository(database) if database is not None else None
    action_repository = ActionRepository(database) if database is not None else None
    runtime_sync_settings = (
        SyncRuntimeSettingsRepository(database, runtime_settings) if database is not None else None
    )
    task_coordinator = (
        TaskCoordinator(
            database,
            lease_seconds=runtime_settings.sync_lease_seconds,
            max_attempts=runtime_settings.sync_max_attempts,
            retry_backoff_seconds=runtime_settings.sync_retry_backoff_seconds,
        )
        if database is not None
        else None
    )
    asset_sync = (
        AssetSyncService(
            immich,
            asset_repository,
            SyncRepository(database),
            runtime_settings,
            task_coordinator,
            runtime_sync_settings,
        )
        if database is not None and asset_repository is not None
        else None
    )
    if task_coordinator is not None and asset_sync is not None:
        from companion.asset_service import (
            AssetRelationRepairTaskHandler,
            AssetRepairTaskHandler,
            AssetSelectionSyncTaskHandler,
            AssetSyncTaskHandler,
        )

        task_coordinator.register_handler(AssetSyncTaskHandler(asset_sync))
        task_coordinator.register_handler(AssetRepairTaskHandler(asset_sync))
        task_coordinator.register_handler(AssetSelectionSyncTaskHandler(asset_sync))
        task_coordinator.register_handler(AssetRelationRepairTaskHandler(asset_sync))
        task_coordinator.register_schedule(
            name="asset-sync-incremental",
            interval_seconds=runtime_settings.sync_incremental_interval_seconds,
            task_type="asset_sync",
            payload={"mode": "incremental"},
            priority=10,
            enabled=False,
            cron_expression="*/15 * * * *",
            deduplication_policy="coalesce",
            blocked_by=["asset-sync:full", "schedule:asset-sync-full"],
        )
        task_coordinator.register_schedule(
            name="asset-sync-full",
            interval_seconds=runtime_settings.sync_full_interval_seconds,
            task_type="asset_sync",
            payload={"mode": "full"},
            priority=100,
            enabled=False,
            cron_expression="0 0 * * 0",
            deduplication_policy="coalesce",
        )
    action_service = (
        AssetActionService(
            runtime_settings,
            immich,
            asset_repository,
            action_repository,
            asset_sync,
            runtime_sync_settings,
        )
        if database is not None
        and asset_repository is not None
        and asset_sync is not None
        and action_repository is not None
        else None
    )
    if task_coordinator is not None and action_service is not None:
        task_coordinator.register_handler(AssetActionTaskHandler(action_service))
    integrity_service = (
        IntegrityService(immich, asset_repository, integrity_repository, task_coordinator)
        if task_coordinator is not None
        and asset_repository is not None
        and integrity_repository is not None
        else None
    )
    integrity_handler = (
        IntegrityTaskHandler(immich, asset_repository, integrity_repository)
        if asset_repository is not None and integrity_repository is not None
        else None
    )
    if (
        task_coordinator is not None
        and integrity_handler is not None
    ):
        task_coordinator.register_handler(integrity_handler)
    duplicate_service = (
        CrossSourceDuplicateService(
            runtime_settings,
            immich,
            asset_repository,
            integrity_repository,
            action_repository,
            task_coordinator,
            runtime_sync_settings,
        )
        if asset_repository is not None
        and integrity_repository is not None
        and action_repository is not None
        and task_coordinator is not None
        and runtime_sync_settings is not None
        else None
    )
    if (
        task_coordinator is not None
        and duplicate_service is not None
        and integrity_handler is not None
    ):
        task_coordinator.register_handler(
            CrossSourceDuplicateTaskHandler(
                immich,
                asset_repository,
                integrity_repository,
                integrity_handler,
            )
        )
        task_coordinator.register_handler(DuplicateResolutionTaskHandler(duplicate_service))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await asyncio.to_thread(run_migrations, runtime_settings)
        if task_coordinator is not None:
            await task_coordinator.cancel_unfinished(
                "asset_sync",
                reason="Asset sync does not resume automatically on container startup.",
            )
            await task_coordinator.start()
        try:
            yield
        finally:
            if task_coordinator is not None:
                await task_coordinator.stop()
            await immich.aclose()
            if database is not None:
                await database.dispose()

    app = FastAPI(
        title="Immich Companion",
        version=runtime_settings.companion_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    @app.exception_handler(ImmichApiError)
    async def immich_error_handler(_request, error: ImmichApiError) -> Response:
        """Keep relation-management failures safe and consistent with API actions."""
        code = (
            status.HTTP_404_NOT_FOUND
            if error.status_code == 404
            else status.HTTP_502_BAD_GATEWAY
        )
        detail = (
            "The Immich relation was not found."
            if code == 404
            else "Immich could not complete the relation request."
        )
        return Response(
            content=json.dumps({"detail": detail}),
            status_code=code,
            media_type="application/json",
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
        immich_compatibility = await immich.compatibility_report()
        return {
            "destructive_actions": runtime_settings.allow_destructive_actions,
            "immich_api": runtime_settings.immich_configured,
            "companion_database": runtime_settings.companion_database_url is not None,
            "immich_server": immich_compatibility.model_dump(mode="json"),
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
                "hybrid_staged_sync",
                "persistent_sync_status",
                "file_integrity_analysis",
                "cross_source_duplicate_analysis",
            ],
            "planned": [
                "action_jobs",
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

    def require_asset_sync() -> AssetSyncService:
        if asset_sync is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return asset_sync

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

    def require_integrity_service() -> IntegrityService:
        if integrity_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return integrity_service

    def require_duplicate_service() -> CrossSourceDuplicateService:
        if duplicate_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return duplicate_service

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
            return await asset_sync.synchronize("full")
        except ImmichApiError as error:
            raise map_immich_error(error) from error

    @app.post("/api/assets/sync/start", response_model=SyncRunStatus)
    async def start_asset_sync(request: SyncStartRequest) -> SyncRunStatus:
        require_asset_repository()
        assert asset_sync is not None
        return await asset_sync.start(request.mode)

    @app.get("/api/assets/sync/status", response_model=SyncCoordinatorStatus)
    async def asset_sync_status() -> SyncCoordinatorStatus:
        require_asset_repository()
        assert asset_sync is not None
        current = await asset_sync.status()
        capabilities = await immich.sync_capabilities()
        return current.model_copy(update={"capabilities": capabilities})

    @app.get("/api/assets/sync/runs/{run_id}", response_model=SyncRunStatus)
    async def asset_sync_run(run_id: UUID) -> SyncRunStatus:
        require_asset_repository()
        assert asset_sync is not None
        run = await asset_sync.run_status(run_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The sync run was not found.",
            )
        return run

    @app.get("/api/tasks/{task_id}", response_model=TaskStatusView)
    async def task_status(task_id: UUID) -> TaskStatusView:
        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        task = await task_coordinator.get_status(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="The task was not found."
            )
        return task

    @app.get("/api/tasks/{task_id}/events", response_model=list[TaskEvent])
    async def task_events(
        task_id: UUID,
        limit: int = Query(default=1000, ge=1, le=5000),
    ) -> list[TaskEvent]:
        """Expose durable checkpoints, including opt-in sync memory snapshots."""

        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        if await task_coordinator.get_status(task_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="The task was not found."
            )
        return await task_coordinator.task_events(task_id, limit=limit)

    @app.websocket("/api/tasks/stream")
    async def task_updates_stream(websocket: WebSocket) -> None:
        """Stream task creation and progress updates before task IDs are known."""

        origin = websocket.headers.get("origin")
        host = websocket.headers.get("host")
        if origin and host and urlsplit(origin).netloc != host:
            await websocket.close(code=1008, reason="WebSocket origin is not allowed")
            return
        await websocket.accept()
        if task_coordinator is None:
            await websocket.close(code=1011, reason="Task coordinator unavailable")
            return
        try:
            async for task in task_coordinator.stream_all():
                await websocket.send_json(task.model_dump(mode="json"))
        except WebSocketDisconnect:
            return

    @app.websocket("/api/tasks/{task_id}/stream")
    async def task_stream(websocket: WebSocket, task_id: UUID) -> None:
        """Stream task snapshots from the central coordinator event channel."""

        origin = websocket.headers.get("origin")
        host = websocket.headers.get("host")
        if origin and host and urlsplit(origin).netloc != host:
            await websocket.close(code=1008, reason="WebSocket origin is not allowed")
            return
        await websocket.accept()
        try:
            if task_coordinator is None:
                await websocket.send_json({"error": "The task coordinator is unavailable."})
                return
            async for task in task_coordinator.stream(task_id):
                await websocket.send_json(task.model_dump(mode="json"))
        except WebSocketDisconnect:
            return

    @app.get("/api/tasks", response_model=list[TaskStatusView])
    async def list_tasks(
        task_type: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> list[TaskStatusView]:
        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return await task_coordinator.list_tasks(task_type=task_type, limit=limit)

    @app.get("/api/settings/sync", response_model=list[TaskScheduleView])
    async def sync_schedule_settings() -> list[TaskScheduleView]:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return await task_coordinator.list_schedules()

    @app.get("/api/settings/sync/runtime")
    async def sync_runtime_settings() -> dict[str, object]:
        if database is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return (await SyncRuntimeSettingsRepository(database, runtime_settings).get()).model_dump()

    @app.put("/api/settings/sync/runtime")
    async def update_sync_runtime_settings(
        request: SyncRuntimeSettingsUpdate,
    ) -> dict[str, object]:
        if database is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return (
            await SyncRuntimeSettingsRepository(database, runtime_settings).update(request)
        ).model_dump()

    @app.put("/api/settings/sync/{schedule_name}", response_model=TaskScheduleView)
    async def update_sync_schedule(
        schedule_name: str, request: TaskScheduleUpdate
    ) -> TaskScheduleView:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        try:
            croniter(request.cron_expression)
        except (CroniterBadCronError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Invalid cron expression.") from error
        schedule = await task_coordinator.update_schedule(
            schedule_name,
            enabled=request.enabled,
            cron_expression=request.cron_expression,
        )
        if schedule is None:
            raise HTTPException(status_code=404, detail="The schedule was not found.")
        return schedule

    @app.post("/api/tasks/{task_id}/cancel", response_model=TaskStatusView)
    async def cancel_task(task_id: UUID) -> TaskStatusView:
        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        task = await task_coordinator.cancel(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="The task was not found."
            )
        return task

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

    @app.get("/api/restore", response_model=AssetSearchResponse)
    async def search_restore_assets(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=48, ge=1, le=200),
    ) -> AssetSearchResponse:
        """List trashed assets directly from Immich, without local index data."""

        try:
            trashed_assets = [asset async for asset in require_immich().iter_trashed_assets()]
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        total = len(trashed_assets)
        offset = (page - 1) * page_size
        return AssetSearchResponse(
            items=[
                add_public_asset_url(AssetSummary.from_immich(asset))
                for asset in trashed_assets[offset : offset + page_size]
            ],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @app.post(
        "/api/assets/{asset_id}/search-match",
        response_model=AssetSummary | None,
    )
    async def match_asset_search(
        asset_id: UUID,
        criteria: AssetSearchMatchRequest,
    ) -> AssetSummary | None:
        repository = require_asset_repository()
        return add_public_asset_url(await repository.find_structured_match(asset_id, criteria))

    @app.get(
        "/api/assets/{asset_id}/summary",
        response_model=AssetSummary | None,
    )
    async def asset_summary(asset_id: UUID) -> AssetSummary | None:
        """Return one asset summary independently of the active search."""

        repository = require_asset_repository()
        return add_public_asset_url(await repository.get_asset_summary(asset_id))

    @app.get("/api/albums", response_model=list[AlbumOption])
    async def search_album_options() -> list[AlbumOption]:
        repository = require_asset_repository()
        return await repository.list_albums()

    def require_immich() -> ImmichApiClient:
        if not runtime_settings.immich_configured:
            raise HTTPException(status_code=503, detail="Immich is not configured.")
        return immich

    @app.get("/api/albums/manage", response_model=RelationPage[AlbumManagementItem])
    async def manage_albums(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                            search: str | None = Query(None, max_length=255),
                            sort: Literal["name", "asset_count"] = "name",
                            direction: Literal["asc", "desc"] = "asc"):
        albums = await require_immich().list_album_catalog()
        counts = await require_asset_repository().album_asset_counts()
        if search:
            needle = search.casefold()
            albums = [a for a in albums if needle in a.album_name.casefold()]
        albums.sort(
            key=lambda album: album.album_name.casefold()
            if sort == "name"
            else counts.get(album.id, 0),
            reverse=direction == "desc",
        )
        total = len(albums)
        start = (page - 1) * page_size
        items = [
            AlbumManagementItem(
                id=a.id,
                name=a.album_name,
                description=a.description,
                asset_count=counts.get(a.id, 0),
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in albums[start : start + page_size]
        ]
        return RelationPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @app.post("/api/albums/manage", response_model=AlbumManagementItem)
    async def create_managed_album(request: AlbumCreateRequest):
        album = await require_immich().create_album(request.name, request.description)
        return AlbumManagementItem(
            id=album.id,
            name=album.album_name,
            description=album.description,
            asset_count=album.asset_count,
            created_at=album.created_at,
            updated_at=album.updated_at,
        )

    @app.post("/api/albums/manage/batch-delete")
    async def batch_delete_albums(request: RelationBatchDeleteRequest):
        client = require_immich()
        completed: list[UUID] = []
        failed: list[UUID] = []
        for identifier in request.ids:
            try:
                await client.delete_album(identifier)
            except ImmichApiError:
                failed.append(identifier)
            else:
                completed.append(identifier)
        return {"completed": completed, "failed": failed, "total": len(request.ids)}

    @app.patch("/api/albums/manage/{album_id}", response_model=AlbumManagementItem)
    async def update_managed_album(album_id: UUID, request: AlbumUpdateRequest):
        album = await require_immich().update_album(
            album_id, name=request.name, description=request.description
        )
        return AlbumManagementItem(
            id=album.id,
            name=album.album_name,
            description=album.description,
            asset_count=album.asset_count,
            created_at=album.created_at,
            updated_at=album.updated_at,
        )

    @app.delete("/api/albums/manage/{album_id}", status_code=204)
    async def delete_managed_album(album_id: UUID) -> Response:
        await require_immich().delete_album(album_id)
        return Response(status_code=204)

    @app.get("/api/tags", response_model=list[TagOption])
    async def search_tag_options() -> list[TagOption]:
        repository = require_asset_repository()
        return await repository.list_tags()

    @app.get("/api/tags/manage", response_model=RelationPage[TagManagementItem])
    async def manage_tags(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                          search: str | None = Query(None, max_length=255),
                          sort: Literal["name", "asset_count"] = "name",
                          direction: Literal["asc", "desc"] = "asc"):
        catalog = await require_immich().list_tag_catalog()
        counts = await require_asset_repository().tag_asset_counts()
        tags_by_id = {tag.id: tag for tag in catalog}
        children_by_parent: dict[UUID, list[ImmichTag]] = {}
        roots: list[ImmichTag] = []
        for tag in catalog:
            if tag.parent_id is not None and tag.parent_id in tags_by_id:
                children_by_parent.setdefault(tag.parent_id, []).append(tag)
            else:
                roots.append(tag)

        def parent_path(tag: ImmichTag) -> list[str]:
            path: list[str] = []
            parent_id = tag.parent_id
            visited = {tag.id}
            while parent_id is not None and parent_id not in visited:
                parent = tags_by_id.get(parent_id)
                if parent is None:
                    break
                path.append(parent.name)
                visited.add(parent.id)
                parent_id = parent.parent_id
            return list(reversed(path))

        needle = search.casefold().strip() if search else ""
        matching_ids = {
            tag.id for tag in catalog if not needle or needle in tag.name.casefold()
        }
        included_ids = set(matching_ids)
        for tag in catalog:
            if tag.id not in matching_ids:
                continue
            parent_id = tag.parent_id
            visited = {tag.id}
            while parent_id is not None and parent_id not in visited:
                included_ids.add(parent_id)
                visited.add(parent_id)
                parent = tags_by_id.get(parent_id)
                parent_id = parent.parent_id if parent is not None else None

        def sort_key(tag: ImmichTag) -> str | int:
            return tag.name.casefold() if sort == "name" else counts.get(tag.id, 0)


        def build_node(tag: ImmichTag) -> TagManagementItem | None:
            if tag.id not in included_ids:
                return None
            child_nodes = [
                node
                for child in sorted(
                    children_by_parent.get(tag.id, []), key=sort_key, reverse=direction == "desc"
                )
                if (node := build_node(child)) is not None
            ]
            return TagManagementItem(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                parent_id=tag.parent_id,
                parent_path=parent_path(tag),
                asset_count=counts.get(tag.id, 0),
                children=child_nodes,
            )

        visible_roots = [
            node
            for root in sorted(roots, key=sort_key, reverse=direction == "desc")
            if (node := build_node(root)) is not None
        ]
        total = len(visible_roots)
        start = (page - 1) * page_size
        items = visible_roots[start : start + page_size]
        return RelationPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @app.post("/api/tags/manage", response_model=TagManagementItem)
    async def create_managed_tag(request: TagCreateRequest):
        tag = await require_immich().create_tag(request.name, request.color, request.parent_id)
        return TagManagementItem(id=tag.id, name=tag.name, color=tag.color, parent_id=tag.parent_id,
                                 asset_count=tag.asset_count)

    @app.post("/api/tags/manage/batch-delete")
    async def batch_delete_tags(request: RelationBatchDeleteRequest):
        client = require_immich()
        catalog = await client.list_tag_catalog()
        children = {tag.parent_id for tag in catalog if tag.parent_id is not None}
        completed: list[UUID] = []
        failed: list[UUID] = [identifier for identifier in request.ids if identifier in children]
        for identifier in request.ids:
            if identifier in children:
                continue
            try:
                await client.delete_tag(identifier)
            except ImmichApiError:
                failed.append(identifier)
            else:
                completed.append(identifier)
        return {"completed": completed, "failed": failed, "total": len(request.ids)}

    @app.patch("/api/tags/manage/{tag_id}", response_model=TagManagementItem)
    async def update_managed_tag(tag_id: UUID, request: TagUpdateRequest):
        client = require_immich()
        catalog = await client.list_tag_catalog()
        current = next((item for item in catalog if item.id == tag_id), None)
        if current is None:
            raise HTTPException(status_code=404, detail="Tag not found.")
        parent_id = current.parent_id
        if "parent_id" in request.model_fields_set:
            parent_id = request.parent_id
            if parent_id == tag_id:
                raise HTTPException(status_code=400, detail="A tag cannot be its own parent.")
            by_id = {item.id: item for item in catalog}
            visited: set[UUID] = set()
            ancestor = parent_id
            while ancestor is not None and ancestor not in visited:
                if ancestor == tag_id:
                    raise HTTPException(
                        status_code=400, detail="A tag cannot be moved below its own child."
                    )
                visited.add(ancestor)
                parent = by_id.get(ancestor)
                ancestor = parent.parent_id if parent is not None else None
        if parent_id != current.parent_id:
            tag = await client.reparent_tag(
                tag_id,
                name=request.name if request.name is not None else current.name,
                color=request.color if request.color is not None else current.color,
                parent_id=parent_id,
                catalog=catalog,
            )
        else:
            tag = await client.update_tag(tag_id, name=request.name, color=request.color)
        return TagManagementItem(id=tag.id, name=tag.name, color=tag.color, parent_id=tag.parent_id,
                                 asset_count=tag.asset_count)

    @app.delete("/api/tags/manage/{tag_id}", status_code=204)
    async def delete_managed_tag(tag_id: UUID) -> Response:
        client = require_immich()
        if any(tag.parent_id == tag_id for tag in await client.list_tag_catalog()):
            raise HTTPException(
                status_code=409, detail="Delete child tags before deleting this parent tag."
            )
        await client.delete_tag(tag_id)
        return Response(status_code=204)

    @app.post("/api/assets/selection/resolve", response_model=AssetSelectionResolution)
    async def resolve_asset_selection(
        selection: AssetSelectionRequest,
    ) -> AssetSelectionResolution:
        service = require_action_service()
        try:
            resolution = await service.resolve_selection(selection)
            if selection.selection_id is not None:
                return resolution.model_copy(update={"ids": [], "missing_ids": []})
            return resolution
        except ValueError as error:
            raise map_action_error(error) from error

    @app.post("/api/assets/selection/ids", response_model=list[UUID])
    async def materialize_asset_selection(selection: AssetSelectionRequest) -> list[UUID]:
        repository = require_asset_repository()
        if selection.mode != "all_matching" or selection.expression is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select-all materialization requires an all-matching expression.",
            )
        return await repository.list_matching_asset_ids(selection.expression)

    def selection_view(record) -> SelectionSetView:
        if record.expires_at <= datetime.now(record.expires_at.tzinfo):
            record.status = "expired"
        return SelectionSetView(
            id=record.id,
            revision=record.revision,
            selected_count=record.selected_count,
            status=record.status,
            expires_at=record.expires_at,
        )

    @app.post("/api/assets/selections", response_model=SelectionSetView)
    async def create_asset_selection() -> SelectionSetView:
        repository = require_asset_repository()
        return selection_view(
            await repository.create_selection(ttl_seconds=runtime_settings.action_plan_ttl_seconds)
        )

    @app.post(
        "/api/assets/selections/{selection_id}/select-all",
        response_model=SelectionSetView,
    )
    async def select_all_asset_selection(
        selection_id: UUID,
        expression: StructuredAssetSearchQuery,
    ) -> SelectionSetView:
        repository = require_asset_repository()
        try:
            record = await repository.replace_selection_with_matching(
                selection_id, expression.expression
            )
        except ValueError as error:
            raise map_action_error(error) from error
        return selection_view(record)

    @app.post(
        "/api/assets/selections/{selection_id}/members",
        response_model=SelectionSetView,
    )
    async def update_asset_selection_members(
        selection_id: UUID,
        request: SelectionSetMembersRequest,
    ) -> SelectionSetView:
        repository = require_asset_repository()
        try:
            record = await repository.update_selection_members(
                selection_id,
                request.asset_ids,
                selected=request.selected,
                revision=request.revision,
            )
        except ValueError as error:
            raise map_action_error(error) from error
        return selection_view(record)

    @app.post(
        "/api/assets/selections/{selection_id}/membership",
        response_model=SelectionSetMembershipResponse,
    )
    async def asset_selection_membership(
        selection_id: UUID,
        request: SelectionSetMembershipRequest,
    ) -> SelectionSetMembershipResponse:
        repository = require_asset_repository()
        record = await repository.get_selection(selection_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Selection set was not found.")
        return SelectionSetMembershipResponse(
            selection=selection_view(record),
            selected_ids=await repository.selection_membership(selection_id, request.asset_ids),
        )

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

    @app.post("/api/assets/actions/execute-task", response_model=AssetActionTaskStart)
    async def execute_asset_action_task(
        request: AssetActionExecuteRequest,
    ) -> AssetActionTaskStart:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="Task coordinator is unavailable.")
        task = await task_coordinator.submit(
            "asset_action",
            {"plan_id": str(request.plan_id)},
            priority=80,
            lane_key="asset_action",
            deduplication_key=f"plan:{request.plan_id}",
        )
        await task_coordinator.start()
        return AssetActionTaskStart(task_id=task.id)

    @app.get(
        "/api/assets/{asset_id}/integrity",
        response_model=AssetIntegrityState,
    )
    async def asset_integrity_state(asset_id: UUID) -> AssetIntegrityState:
        try:
            return await require_integrity_service().state(asset_id)
        except IntegrityAssetUnavailableError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ImmichApiError as error:
            raise map_immich_error(error) from error

    @app.post(
        "/api/assets/{asset_id}/integrity/analyze",
        response_model=AssetIntegrityAnalyzeResponse,
    )
    async def analyze_asset_integrity(
        asset_id: UUID,
        request: AssetIntegrityAnalyzeRequest,
        response: Response,
    ) -> AssetIntegrityAnalyzeResponse:
        try:
            result = await require_integrity_service().analyze(asset_id, force=request.force)
        except IntegrityAssetUnavailableError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        if result.state == "pending":
            response.status_code = status.HTTP_202_ACCEPTED
        return result

    @app.get(
        "/api/assets/duplicates/cross-source",
        response_model=CrossSourceDuplicateResult,
    )
    async def cross_source_duplicate_result() -> CrossSourceDuplicateResult:
        try:
            return await require_duplicate_service().result()
        except ImmichApiError as error:
            raise map_immich_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/search",
        response_model=CrossSourceDuplicateResult,
    )
    async def search_cross_source_duplicates(
        request: DuplicateAnalysisOptions,
    ) -> CrossSourceDuplicateResult:
        try:
            return await require_duplicate_service().result(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/analyze",
        response_model=CrossSourceDuplicateTaskStart,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def analyze_cross_source_duplicates(
        request: DuplicateAnalysisOptions | None = None,
    ) -> CrossSourceDuplicateTaskStart:
        try:
            return await require_duplicate_service().start(
                request or DuplicateAnalysisOptions()
            )
        except ImmichApiError as error:
            raise map_immich_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/plan",
        response_model=DuplicateResolutionPlan,
    )
    async def plan_duplicate_resolution(
        request: DuplicateResolutionPlanRequest,
    ) -> DuplicateResolutionPlan:
        try:
            return await require_duplicate_service().plan(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/execute",
        response_model=CrossSourceDuplicateTaskStart,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def execute_duplicate_resolution(
        request: DuplicateResolutionExecuteRequest,
    ) -> CrossSourceDuplicateTaskStart:
        try:
            return await require_duplicate_service().start_resolution(request)
        except RuntimeError as error:
            raise map_action_error(error) from error

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
    async def restore_assets(request: AssetRestoreRequest) -> dict[str, int]:
        """Restore selected or all live Immich trash in paced server-side batches."""

        sync = require_asset_sync()
        pacing = await sync._runtime_sync_settings.get()
        if request.all:
            try:
                asset_ids = [
                    asset.id async for asset in require_immich().iter_trashed_assets()
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
        for index, batch in enumerate(restore_batches):
            try:
                await sync.restore_targets(batch)
            except ImmichApiError as error:
                raise map_immich_error(error) from error
            if index < len(restore_batches) - 1:
                await asyncio.sleep(pacing.full_min_batch_delay_seconds)
        return {"restored": len(asset_ids)}

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

"""Asset synchronization, settings, and task-control route registration."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from croniter import CroniterBadCronError, croniter
from fastapi import FastAPI, HTTPException, status

from companion.asset_schema import (
    AssetSyncResult,
)
from companion.duplicate_discovery_settings import (
    ComparisonAlignmentSettingsUpdate,
    DuplicateDiscoverySettingsPatch,
    DuplicateDiscoverySettingsUpdate,
)
from companion.duplicate_policy import DuplicatePolicy
from companion.immich import (
    ImmichApiClient,
    ImmichApiError,
    ImmichLibrary,
)
from companion.immich_duplicate_sync import (
    ImmichDuplicateSyncStatus,
    ImmichDuplicateSyncTaskStart,
)
from companion.similarity_settings import SimilarityRuntimeSettingsUpdate
from companion.sync_schema import SyncCoordinatorStatus, SyncRunStatus, SyncStartRequest
from companion.sync_settings import (
    SyncRuntimeSettingsRepository,
    SyncRuntimeSettingsUpdate,
)
from companion.task_routes import register_task_routes
from companion.task_schema import (
    TaskScheduleUpdate,
    TaskScheduleView,
    TaskStatusView,
)


def register_sync_settings_routes(
    app: FastAPI,
    *,
    asset_sync,
    database,
    immich: ImmichApiClient,
    runtime_settings,
    similarity_runtime_settings_repository,
    duplicate_discovery_settings_repository,
    duplicate_policy_repository,
    task_coordinator,
    require_asset_repository: Callable[[], object],
    require_immich: Callable[[], ImmichApiClient],
    require_immich_duplicate_sync_service: Callable[[], object],
    map_immich_error: Callable[[ImmichApiError], HTTPException],
) -> None:
    """Register synchronization, settings, and task-control endpoints."""

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
            raise HTTPException(status_code=404, detail="The sync run was not found.")
        return run

    register_task_routes(app, task_coordinator)

    @app.get("/api/settings/sync/runtime")
    async def sync_runtime_settings() -> dict[str, object]:
        if database is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return (await SyncRuntimeSettingsRepository(database, runtime_settings).get()).model_dump()

    @app.get("/api/settings/duplicates/similarity-runtime")
    async def similarity_runtime_settings() -> dict[str, object]:
        if similarity_runtime_settings_repository is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return (await similarity_runtime_settings_repository.get()).model_dump()

    @app.put("/api/settings/duplicates/similarity-runtime")
    async def update_similarity_runtime_settings(
        request: SimilarityRuntimeSettingsUpdate,
    ) -> dict[str, object]:
        if similarity_runtime_settings_repository is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return (await similarity_runtime_settings_repository.update(request)).model_dump()

    @app.get("/api/settings/duplicates/immich-sync", response_model=ImmichDuplicateSyncStatus)
    async def immich_duplicate_sync_status() -> ImmichDuplicateSyncStatus:
        return await require_immich_duplicate_sync_service().status()

    @app.post(
        "/api/settings/duplicates/immich-sync",
        response_model=ImmichDuplicateSyncTaskStart,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_immich_duplicate_sync() -> ImmichDuplicateSyncTaskStart:
        return await require_immich_duplicate_sync_service().start()

    @app.get("/api/settings/duplicates/discovery")
    async def duplicate_discovery_settings() -> dict[str, object]:
        if duplicate_discovery_settings_repository is None:
            raise HTTPException(status_code=503, detail="Companion database is unavailable")
        return (await duplicate_discovery_settings_repository.get()).model_dump()

    @app.put("/api/settings/duplicates/discovery")
    async def update_duplicate_discovery_settings(
        request: DuplicateDiscoverySettingsUpdate,
    ) -> dict[str, object]:
        if duplicate_discovery_settings_repository is None:
            raise HTTPException(status_code=503, detail="Companion database is unavailable")
        return (await duplicate_discovery_settings_repository.update(request)).model_dump()

    @app.patch("/api/settings/duplicates/discovery")
    async def patch_duplicate_discovery_settings(
        request: DuplicateDiscoverySettingsPatch,
    ) -> dict[str, object]:
        if duplicate_discovery_settings_repository is None:
            raise HTTPException(status_code=503, detail="Companion database is unavailable")
        return (
            await duplicate_discovery_settings_repository.update_discovery_settings(request)
        ).model_dump()

    @app.get("/api/settings/duplicates/comparison-alignment")
    async def comparison_alignment_settings() -> dict[str, object]:
        if duplicate_discovery_settings_repository is None:
            raise HTTPException(status_code=503, detail="Companion database is unavailable")
        return (
            await duplicate_discovery_settings_repository.comparison_alignment()
        ).model_dump()

    @app.put("/api/settings/duplicates/comparison-alignment")
    async def update_comparison_alignment_settings(
        request: ComparisonAlignmentSettingsUpdate,
    ) -> dict[str, object]:
        if duplicate_discovery_settings_repository is None:
            raise HTTPException(status_code=503, detail="Companion database is unavailable")
        return (
            await duplicate_discovery_settings_repository.update_comparison_alignment(request)
        ).model_dump()

    @app.get("/api/settings/duplicates/policy", response_model=DuplicatePolicy)
    async def duplicate_policy_settings() -> DuplicatePolicy:
        if duplicate_policy_repository is None:
            raise HTTPException(status_code=503, detail="Companion database is unavailable")
        return await duplicate_policy_repository.get()

    @app.put("/api/settings/duplicates/policy", response_model=DuplicatePolicy)
    async def update_duplicate_policy_settings(request: DuplicatePolicy) -> DuplicatePolicy:
        if duplicate_policy_repository is None:
            raise HTTPException(status_code=503, detail="Companion database is unavailable")
        return await duplicate_policy_repository.update(request)

    @app.get("/api/settings/duplicates/libraries", response_model=list[ImmichLibrary])
    async def duplicate_policy_libraries() -> list[ImmichLibrary]:
        try:
            libraries = await require_immich().list_libraries()
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        return [
            library
            for library in libraries
            if library.library_type is None or library.library_type.upper() == "EXTERNAL"
        ]

    @app.put("/api/settings/sync/runtime")
    async def update_sync_runtime_settings(
        request: SyncRuntimeSettingsUpdate,
    ) -> dict[str, object]:
        if database is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        updated = await SyncRuntimeSettingsRepository(database, runtime_settings).update(request)
        return updated.model_dump()

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
            schedule_name, enabled=request.enabled, cron_expression=request.cron_expression
        )
        if schedule is None:
            raise HTTPException(status_code=404, detail="The schedule was not found.")
        return schedule

    @app.post("/api/tasks/{task_id}/cancel", response_model=TaskStatusView)
    async def cancel_task(task_id: UUID) -> TaskStatusView:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        task = await task_coordinator.cancel(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="The task was not found.")
        return task

    @app.post("/api/tasks/{task_id}/pause", response_model=TaskStatusView)
    async def pause_task(task_id: UUID) -> TaskStatusView:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        try:
            task = await task_coordinator.pause(task_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if task is None:
            raise HTTPException(status_code=404, detail="The task was not found.")
        return task

    @app.post("/api/tasks/{task_id}/resume", response_model=TaskStatusView)
    async def resume_task(task_id: UUID) -> TaskStatusView:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        try:
            task = await task_coordinator.resume(task_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if task is None:
            raise HTTPException(status_code=404, detail="The task was not found.")
        await task_coordinator.start()
        return task

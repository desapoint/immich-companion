"""FastAPI entrypoint for Immich Companion."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import (
    FastAPI,
    HTTPException,
    Response,
    status,
)

from companion.action_duplicate_routes import register_action_duplicate_routes
from companion.action_repository import ActionRepository
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
from companion.asset_routes import register_asset_routes
from companion.asset_schema import (
    AssetSearchResponse,
    AssetSummary,
)
from companion.asset_service import AssetSyncService, batches
from companion.composite_duplicate_repository import CompositeDuplicateRepository
from companion.composite_duplicate_sync import (
    CompositeDuplicateRebuildTaskHandler,
    CompositeDuplicateStartupReconcileService,
    CompositeDuplicateStartupReconcileTaskHandler,
    CompositeDuplicateSyncService,
    FollowUpTaskHandler,
    composite_projection_is_stale,
)
from companion.config import Settings, get_settings
from companion.database import DatabaseManager, PostgresHealthClient
from companion.deployment_auth_boundary import DeploymentBearerAuthMiddleware
from companion.discovery import (
    CompositeGroupDiscoveryProvider,
    ImmichDuplicateProvider,
    PersistedCompositeDuplicateProvider,
    SimilarityDuplicateProvider,
)
from companion.duplicate_discovery_settings import (
    DuplicateDiscoverySettingsRepository,
)
from companion.duplicate_policy import DuplicatePolicyRepository
from companion.duplicate_review_repository import DuplicateReviewRepository
from companion.duplicate_routes import register_duplicate_routes
from companion.duplicate_schema import (
    SimilarityCacheStatus,
    SimilarityDiskCacheStatus,
)
from companion.duplicate_service import (
    CrossSourceDuplicateService,
)
from companion.duplicate_task_handlers import CrossSourceDuplicateTaskHandler
from companion.frontend_routes import register_frontend_routes
from companion.health_routes import register_health_routes
from companion.immich import (
    ImmichApiClient,
    ImmichApiError,
    ImmichTag,
)
from companion.immich_duplicate_repository import ImmichDuplicateRepository
from companion.immich_duplicate_sync import (
    ImmichDuplicateSyncService,
    ImmichDuplicateSyncTaskHandler,
    RefreshingDuplicateResolutionTaskHandler,
)
from companion.integrity_repository import IntegrityRepository
from companion.integrity_service import (
    IntegrityService,
    IntegrityTaskHandler,
)
from companion.media_restore_routes import (
    RestoreRequest,
    register_media_restore_routes,
    restore_batch_with_accounting,
)
from companion.migrate import run_migrations
from companion.relation_routes import register_relation_management_routes
from companion.selection_repository import RelationSelectionRepository
from companion.similarity_cache import SimilarityCacheManager
from companion.similarity_debug_api import register_similarity_debug_routes
from companion.similarity_detail_api import register_similarity_detail_routes
from companion.similarity_detail_service import SimilarityDetailRepository
from companion.similarity_generation import SimilarityEvidenceDestroyTaskHandler
from companion.similarity_index_service import (
    SimilarityIndexMaintainer,
    SimilarityIndexService,
    SimilarityIndexTaskHandler,
)
from companion.similarity_maintenance import (
    SimilarityMaintenanceRepository,
    SimilarityMaintenanceService,
    SimilarityMaintenanceTaskHandler,
)
from companion.similarity_repository import SimilarityRepository
from companion.similarity_scan_repository import SimilarityScanRepository
from companion.similarity_scan_service import (
    SimilarityScanService,
    SimilarityScanTaskHandler,
)
from companion.similarity_search_repository import SimilaritySearchRepository
from companion.similarity_settings import (
    SimilarityRuntimeSettingsRepository,
)
from companion.stack_service import StackService
from companion.sync_repository import SyncRepository
from companion.sync_settings import SyncRuntimeSettingsRepository
from companion.sync_settings_routes import register_sync_settings_routes
from companion.synchronization.runtime import (
    register_sync_step_routes,
    register_sync_steps,
)
from companion.task_coordinator import TaskCoordinator
from companion.trash_purge_service import TrashPurgeService
from companion.v2_duplicate_review_state import (
    V2DuplicateReviewStateRefreshService,
    V2DuplicateReviewStateRefreshTaskHandler,
    V2DuplicateReviewStateService,
)

__all__ = [
    "RestoreRequest",
    "create_app",
    "matching_tag_ids",
    "restore_batch_with_accounting",
    "tag_subtree_ids",
]


def tag_subtree_ids(catalog: list[ImmichTag]) -> dict[UUID, list[UUID]]:
    """Resolve each real tag and its descendants from the full catalog."""

    by_id = {tag.id: tag for tag in catalog}
    subtrees = {tag.id: [tag.id] for tag in catalog}
    for tag in catalog:
        parent_id = tag.parent_id
        visited = {tag.id}
        while parent_id is not None and parent_id in by_id and parent_id not in visited:
            subtrees[parent_id].append(tag.id)
            visited.add(parent_id)
            parent_id = by_id[parent_id].parent_id
    return subtrees


def matching_tag_ids(catalog: list[ImmichTag], query: str, include_hierarchy: bool) -> list[UUID]:
    """Resolve matching hierarchy rows to their real subtree members."""

    needle = query.strip().casefold()
    if not needle:
        return [tag.id for tag in catalog]
    by_id = {tag.id: tag for tag in catalog}
    subtrees = tag_subtree_ids(catalog)

    def path(tag: ImmichTag) -> str:
        names = [tag.name]
        parent_id = tag.parent_id
        visited = {tag.id}
        while parent_id is not None and parent_id not in visited:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            names.append(parent.name)
            visited.add(parent.id)
            parent_id = parent.parent_id
        return " / ".join(reversed(names))

    matching = [
        tag
        for tag in catalog
        if needle in (path(tag) if include_hierarchy else tag.name).casefold()
    ]
    return list(
        dict.fromkeys(descendant_id for tag in matching for descendant_id in subtrees[tag.id])
    )


def create_app(
    settings: Settings | None = None,
    immich_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Create an application with injectable settings/transport for tests."""

    runtime_settings = settings or get_settings()
    immich = ImmichApiClient(runtime_settings, transport=immich_transport)
    similarity_cache = SimilarityCacheManager(
        runtime_settings.similarity_cache_dir,
        preview_max_bytes=runtime_settings.similarity_preview_cache_max_bytes,
        preview_max_age_seconds=runtime_settings.similarity_preview_cache_max_age_seconds,
        decode_max_bytes=runtime_settings.similarity_decode_cache_max_bytes,
    )
    database_health = PostgresHealthClient(runtime_settings)
    database = (
        DatabaseManager(runtime_settings)
        if runtime_settings.companion_database_url is not None
        else None
    )
    asset_repository = AssetRepository(database) if database is not None else None
    integrity_repository = IntegrityRepository(database) if database is not None else None
    search_feature_repository = (
        SimilaritySearchRepository(database) if database is not None else None
    )
    duplicate_discovery_settings_repository = (
        DuplicateDiscoverySettingsRepository(database) if database is not None else None
    )
    similarity_runtime_settings_repository = (
        SimilarityRuntimeSettingsRepository(database, runtime_settings)
        if database is not None
        else None
    )
    detail_repository = (
        SimilarityDetailRepository(database, duplicate_discovery_settings_repository)
        if database is not None
        else None
    )
    similarity_repository = (
        SimilarityRepository(
            database,
            pair_max_bytes=runtime_settings.similarity_pair_cache_max_bytes,
            hot_max_bytes=runtime_settings.similarity_hot_cache_max_bytes,
            details=detail_repository,
        )
        if database is not None
        else None
    )
    similarity_scan_repository = (
        SimilarityScanRepository(database) if database is not None else None
    )
    similarity_maintenance_repository = (
        SimilarityMaintenanceRepository(database) if database is not None else None
    )
    action_repository = ActionRepository(database) if database is not None else None
    trash_purge_service = (
        TrashPurgeService(immich, action_repository, runtime_settings)
        if action_repository is not None
        else None
    )
    relation_selection_repository = (
        RelationSelectionRepository(database) if database is not None else None
    )
    duplicate_review_repository = (
        DuplicateReviewRepository(database) if database is not None else None
    )
    duplicate_policy_repository = (
        DuplicatePolicyRepository(database) if database is not None else None
    )
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
    immich_duplicate_repository = (
        ImmichDuplicateRepository(database) if database is not None else None
    )
    composite_duplicate_repository = (
        CompositeDuplicateRepository(database) if database is not None else None
    )
    duplicate_discovery = (
        PersistedCompositeDuplicateProvider(
            composite_duplicate_repository,
            asset_repository,
        )
        if composite_duplicate_repository is not None and asset_repository is not None
        else None
    )
    v2_duplicate_review_state_service = (
        V2DuplicateReviewStateService(
            duplicate_discovery,
            integrity_repository,
            composite_duplicate_repository,
            duplicate_review_repository,
        )
        if duplicate_discovery is not None
        and integrity_repository is not None
        and composite_duplicate_repository is not None
        and duplicate_review_repository is not None
        else None
    )
    v2_duplicate_review_state_refresh_service = None
    if task_coordinator is not None and v2_duplicate_review_state_service is not None:
        task_coordinator.register_handler(
            V2DuplicateReviewStateRefreshTaskHandler(v2_duplicate_review_state_service)
        )
        v2_duplicate_review_state_refresh_service = V2DuplicateReviewStateRefreshService(
            task_coordinator
        )
    exact_duplicate_discovery = (
        ImmichDuplicateProvider(immich_duplicate_repository, asset_repository)
        if immich_duplicate_repository is not None and asset_repository is not None
        else None
    )
    source_duplicate_discovery = (
        CompositeGroupDiscoveryProvider(
            # Similarity can carry tens of thousands of retained relationships, so keep
            # it in the streaming slot and retain the typically smaller Immich snapshot
            # only for exact-member-set coalescing.
            SimilarityDuplicateProvider(similarity_scan_repository, asset_repository),
            exact_duplicate_discovery,
        )
        if similarity_scan_repository is not None
        and asset_repository is not None
        and immich_duplicate_repository is not None
        else None
    )
    composite_duplicate_sync_service = (
        CompositeDuplicateSyncService(task_coordinator)
        if task_coordinator is not None
        and source_duplicate_discovery is not None
        and composite_duplicate_repository is not None
        else None
    )

    async def composite_projection_needs_refresh() -> bool:
        if (
            composite_duplicate_repository is None
            or immich_duplicate_repository is None
            or similarity_scan_repository is None
        ):
            return False
        composite_metadata = await composite_duplicate_repository.metadata()
        immich_metadata = await immich_duplicate_repository.metadata()
        similarity_summary = await similarity_scan_repository.latest_completed_summary()
        return composite_projection_is_stale(
            composite_metadata.last_success_at,
            immich_metadata.last_success_at,
            similarity_summary.completed_at if similarity_summary is not None else None,
        )

    composite_duplicate_startup_reconcile_service = None
    if (
        task_coordinator is not None
        and composite_duplicate_sync_service is not None
        and composite_duplicate_repository is not None
        and immich_duplicate_repository is not None
        and similarity_scan_repository is not None
    ):
        task_coordinator.register_handler(
            CompositeDuplicateStartupReconcileTaskHandler(
                task_coordinator,
                composite_projection_needs_refresh,
                composite_duplicate_sync_service.refresh_and_wait,
            )
        )
        composite_duplicate_startup_reconcile_service = (
            CompositeDuplicateStartupReconcileService(task_coordinator)
        )
    if (
        task_coordinator is not None
        and source_duplicate_discovery is not None
        and composite_duplicate_repository is not None
    ):
        composite_duplicate_handler = CompositeDuplicateRebuildTaskHandler(
            source_duplicate_discovery,
            composite_duplicate_repository,
            after_publish=(
                similarity_scan_repository.prune_completed_pair_evidence
                if similarity_scan_repository is not None
                else None
            ),
        )
        task_coordinator.register_handler(
            FollowUpTaskHandler(
                composite_duplicate_handler,
                v2_duplicate_review_state_refresh_service.refresh_after_change,
            )
            if v2_duplicate_review_state_refresh_service is not None
            else composite_duplicate_handler
        )
    immich_duplicate_sync_service = (
        ImmichDuplicateSyncService(task_coordinator, immich_duplicate_repository)
        if task_coordinator is not None and immich_duplicate_repository is not None
        else None
    )
    if task_coordinator is not None and immich_duplicate_repository is not None:
        immich_duplicate_handler = ImmichDuplicateSyncTaskHandler(
            immich, immich_duplicate_repository
        )
        task_coordinator.register_handler(
            FollowUpTaskHandler(
                immich_duplicate_handler,
                composite_duplicate_sync_service.start_after_source_change,
            )
            if composite_duplicate_sync_service is not None
            else immich_duplicate_handler
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
    sync_step_submission = None
    if (
        task_coordinator is not None
        and asset_sync is not None
        and runtime_sync_settings is not None
        and asset_repository is not None
    ):
        sync_step_submission = register_sync_steps(
            task_coordinator,
            registry=asset_sync.step_registry,
            generations=asset_sync,
            runtime_settings=runtime_sync_settings,
            assets=asset_repository,
        )
    if task_coordinator is not None and asset_sync is not None:
        from companion.asset_service import (
            AssetRelationRepairTaskHandler,
            AssetRepairTaskHandler,
            AssetSelectionSyncTaskHandler,
            AssetSyncTaskHandler,
        )

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
    stack_service = (
        StackService(immich, asset_repository, asset_sync)
        if asset_repository is not None and asset_sync is not None
        else None
    )
    action_service = (
        AssetActionService(
            runtime_settings,
            immich,
            asset_repository,
            action_repository,
            asset_sync,
            runtime_sync_settings,
            stack_service,
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
        IntegrityTaskHandler(
            immich,
            asset_repository,
            integrity_repository,
            decode_cache_path=similarity_cache.decode_path,
            decode_cache_max_bytes=runtime_settings.similarity_decode_cache_max_bytes,
        )
        if asset_repository is not None and integrity_repository is not None
        else None
    )
    if task_coordinator is not None and integrity_handler is not None:
        task_coordinator.register_handler(integrity_handler)
    similarity_index_maintainer = (
        SimilarityIndexMaintainer(
            immich,
            asset_repository,
            search_feature_repository,
            details=detail_repository,
            fetch_slots=runtime_settings.similarity_preview_fetch_slots,
            decode_slots=runtime_settings.similarity_preview_decode_slots,
            visual_source_max_bytes=runtime_settings.similarity_detail_max_bytes,
            decode_cache_path=similarity_cache.decode_path,
            batch_size=runtime_settings.similarity_fingerprint_page_size,
            runtime_settings=similarity_runtime_settings_repository,
        )
        if asset_repository is not None and search_feature_repository is not None
        else None
    )
    duplicate_service = (
        CrossSourceDuplicateService(
            runtime_settings,
            immich,
            asset_repository,
            integrity_repository,
            action_repository,
            task_coordinator,
            runtime_sync_settings,
            duplicate_review_repository,
            duplicate_policy_repository,
            similarity_repository,
            duplicate_discovery,
            stack_service,
            search_features=search_feature_repository,
            scan_evidence=similarity_scan_repository,
        )
        if asset_repository is not None
        and integrity_repository is not None
        and action_repository is not None
        and task_coordinator is not None
        and runtime_sync_settings is not None
        and similarity_scan_repository is not None
        else None
    )
    if (
        task_coordinator is not None
        and duplicate_service is not None
        and integrity_handler is not None
        and immich_duplicate_sync_service is not None
    ):
        duplicate_analysis_handler = CrossSourceDuplicateTaskHandler(
            immich,
            asset_repository,
            integrity_repository,
            integrity_handler,
            include_preservation=True,
            discovery=exact_duplicate_discovery,
            similarity_indexer=similarity_index_maintainer,
            shared_original_cache_path=similarity_cache.decode_path,
        )
        task_coordinator.register_handler(
            FollowUpTaskHandler(
                duplicate_analysis_handler,
                v2_duplicate_review_state_refresh_service.refresh_after_change,
            )
            if v2_duplicate_review_state_refresh_service is not None
            else duplicate_analysis_handler
        )
        task_coordinator.register_handler(
            RefreshingDuplicateResolutionTaskHandler(
                duplicate_service,
                immich_duplicate_sync_service,
            )
        )
    similarity_index_service = (
        SimilarityIndexService(task_coordinator, similarity_index_maintainer)
        if task_coordinator is not None and similarity_index_maintainer is not None
        else None
    )
    if task_coordinator is not None and similarity_index_maintainer is not None:
        task_coordinator.register_handler(SimilarityIndexTaskHandler(similarity_index_maintainer))

    similarity_scan_service = (
        SimilarityScanService(task_coordinator, similarity_scan_repository)
        if task_coordinator is not None
        and search_feature_repository is not None
        and similarity_repository is not None
        and similarity_scan_repository is not None
        else None
    )
    if similarity_scan_service is not None:
        assert task_coordinator is not None
        assert search_feature_repository is not None
        assert similarity_repository is not None
        assert similarity_scan_repository is not None
        similarity_scan_handler = SimilarityScanTaskHandler(
            search_feature_repository,
            similarity_repository,
            similarity_scan_repository,
            similarity_index_maintainer,
        )
        task_coordinator.register_handler(
            FollowUpTaskHandler(
                similarity_scan_handler,
                composite_duplicate_sync_service.start_after_source_change,
            )
            if composite_duplicate_sync_service is not None
            else similarity_scan_handler
        )

    similarity_maintenance_service = (
        SimilarityMaintenanceService(task_coordinator, similarity_maintenance_repository)
        if task_coordinator is not None and similarity_maintenance_repository is not None
        else None
    )
    if (
        task_coordinator is not None
        and asset_sync is not None
        and similarity_maintenance_service is not None
        and similarity_maintenance_repository is not None
        and similarity_index_maintainer is not None
        and search_feature_repository is not None
        and similarity_scan_repository is not None
    ):
        similarity_maintenance_handler = SimilarityMaintenanceTaskHandler(
            similarity_maintenance_repository,
            similarity_index_maintainer,
            search_feature_repository,
            similarity_scan_repository,
        )
        task_coordinator.register_handler(
            FollowUpTaskHandler(
                similarity_maintenance_handler,
                composite_duplicate_sync_service.start_after_source_change,
            )
            if composite_duplicate_sync_service is not None
            else similarity_maintenance_handler
        )

        async def after_asset_sync_success() -> None:
            await similarity_maintenance_service.start_if_pending()
            if immich_duplicate_sync_service is not None:
                await immich_duplicate_sync_service.start_after_asset_sync()

        task_coordinator.register_handler(
            AssetSyncTaskHandler(
                asset_sync,
                after_success=after_asset_sync_success,
            )
        )

    if task_coordinator is not None and detail_repository is not None:
        task_coordinator.register_handler(
            SimilarityEvidenceDestroyTaskHandler(detail_repository._evidence_epoch)
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if database is not None:
            await asyncio.to_thread(run_migrations, runtime_settings)
        if task_coordinator is not None:
            await task_coordinator.cancel_unfinished(
                "asset_sync",
                reason="Asset sync does not resume automatically on container startup.",
            )
            await task_coordinator.cancel_unfinished(
                "sync_step",
                reason="Manual sync steps do not resume automatically on container startup.",
            )
            await task_coordinator.start()
            if similarity_maintenance_service is not None:
                await similarity_maintenance_service.start_if_pending()
            if composite_duplicate_startup_reconcile_service is not None:
                await composite_duplicate_startup_reconcile_service.start()
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
    register_similarity_detail_routes(app, detail_repository, task_coordinator)
    register_similarity_debug_routes(
        app,
        search_feature_repository,
        similarity_repository,
        detail_repository,
    )

    @app.exception_handler(ImmichApiError)
    async def immich_error_handler(_request, error: ImmichApiError) -> Response:
        """Keep relation-management failures safe and consistent with API actions."""
        code = (
            status.HTTP_404_NOT_FOUND if error.status_code == 404 else status.HTTP_502_BAD_GATEWAY
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

    register_health_routes(app, runtime_settings, immich, database_health)

    def require_asset_repository() -> AssetRepository:
        if asset_repository is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return asset_repository

    def require_asset_sync() -> AssetSyncService:
        override = getattr(app.state, "asset_sync_override", None)
        if override is not None:
            return override
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

    def require_immich_duplicate_sync_service() -> ImmichDuplicateSyncService:
        if immich_duplicate_sync_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Immich duplicate synchronization is unavailable.",
            )
        return immich_duplicate_sync_service

    def require_similarity_scan_service() -> SimilarityScanService:
        if similarity_scan_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return similarity_scan_service

    def require_similarity_index_service() -> SimilarityIndexService:
        if similarity_index_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return similarity_index_service

    def require_similarity_repository() -> SimilarityRepository:
        if similarity_repository is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return similarity_repository

    async def build_similarity_cache_status() -> SimilarityCacheStatus:
        cache = await require_similarity_repository().cache_status()
        return SimilarityCacheStatus(
            **cache,
            previews=SimilarityDiskCacheStatus(**asdict(similarity_cache.preview.status())),
            decode=SimilarityDiskCacheStatus(**asdict(similarity_cache.decode_status())),
            generated_at=datetime.now(UTC),
        )

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

    def require_immich() -> ImmichApiClient:
        override = getattr(app.state, "immich_override", None)
        if override is not None:
            return override
        if not runtime_settings.immich_configured:
            raise HTTPException(status_code=503, detail="Immich is not configured.")
        return immich

    register_sync_step_routes(app, sync_step_submission)

    register_sync_settings_routes(
        app,
        asset_sync=asset_sync,
        database=database,
        immich=immich,
        runtime_settings=runtime_settings,
        similarity_runtime_settings_repository=similarity_runtime_settings_repository,
        duplicate_discovery_settings_repository=duplicate_discovery_settings_repository,
        duplicate_policy_repository=duplicate_policy_repository,
        task_coordinator=task_coordinator,
        require_asset_repository=require_asset_repository,
        require_immich=require_immich,
        require_immich_duplicate_sync_service=require_immich_duplicate_sync_service,
        map_immich_error=map_immich_error,
    )

    register_asset_routes(
        app,
        require_asset_repository=require_asset_repository,
        require_integrity_service=require_integrity_service,
        require_immich=require_immich,
        map_immich_error=map_immich_error,
        add_public_asset_urls=add_public_asset_urls,
        add_public_asset_url=add_public_asset_url,
        composite_duplicate_repository=composite_duplicate_repository,
    )

    register_relation_management_routes(
        app,
        require_immich=require_immich,
        require_asset_repository=require_asset_repository,
        tag_subtree_ids=tag_subtree_ids,
    )

    register_action_duplicate_routes(
        app,
        relation_selection_repository=relation_selection_repository,
        runtime_settings=runtime_settings,
        require_immich=require_immich,
        require_asset_repository=require_asset_repository,
        require_action_service=require_action_service,
        require_integrity_service=require_integrity_service,
        require_duplicate_service=require_duplicate_service,
        require_similarity_scan_service=require_similarity_scan_service,
        require_similarity_index_service=require_similarity_index_service,
        task_coordinator=task_coordinator,
        action_repository=action_repository,
        duplicate_review_repository=duplicate_review_repository,
        duplicate_discovery=duplicate_discovery,
        database=database,
        v2_duplicate_review_state_refresh_service=v2_duplicate_review_state_refresh_service,
        map_action_error=map_action_error,
        map_immich_error=map_immich_error,
    )

    register_duplicate_routes(
        app,
        build_similarity_cache_status=build_similarity_cache_status,
        similarity_cache=similarity_cache,
        require_similarity_repository=require_similarity_repository,
        require_integrity_service=require_integrity_service,
        require_duplicate_service=require_duplicate_service,
        duplicate_review_repository=duplicate_review_repository,
        duplicate_discovery=duplicate_discovery,
        database=database,
        v2_duplicate_review_state_refresh_service=v2_duplicate_review_state_refresh_service,
        require_similarity_scan_service=require_similarity_scan_service,
        require_similarity_index_service=require_similarity_index_service,
        map_action_error=map_action_error,
        map_immich_error=map_immich_error,
    )

    register_media_restore_routes(
        app,
        immich=immich,
        require_immich=require_immich,
        require_asset_sync=require_asset_sync,
        require_asset_repository=require_asset_repository,
        asset_repository=asset_repository,
        asset_sync=asset_sync,
        runtime_settings=runtime_settings,
        task_coordinator=task_coordinator,
        similarity_cache=similarity_cache,
        selection_digest=selection_digest,
        batches=batches,
        map_immich_error=map_immich_error,
        map_action_error=map_action_error,
        trash_purge_service=trash_purge_service,
    )

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

    register_frontend_routes(app, runtime_settings.companion_frontend_dir)

    app.add_middleware(
        DeploymentBearerAuthMiddleware,
        token=runtime_settings.resolve_companion_auth_token(),
    )
    return app


app = create_app()

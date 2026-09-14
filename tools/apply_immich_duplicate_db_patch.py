"""One-shot source patch for the database-backed Immich duplicate projection."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}, found {count}: {old[:80]!r}")
    path.write_text(content.replace(old, new), encoding="utf-8")


main = ROOT / "backend/companion/main.py"
settings = ROOT / "frontend/src/v2/pages/V2SettingsPage.svelte"

replace_once(
    main,
    '''from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
    DuplicateResolutionTaskHandler,
)
from companion.immich import (
''',
    '''from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
    DuplicateResolutionTaskHandler,
)
from companion.immich_duplicate_repository import ImmichDuplicateRepository
from companion.immich_duplicate_sync import (
    ImmichDuplicateSyncService,
    ImmichDuplicateSyncStatus,
    ImmichDuplicateSyncTaskHandler,
    ImmichDuplicateSyncTaskStart,
)
from companion.immich import (
''',
)

replace_once(
    main,
    '''    task_coordinator = (
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
''',
    '''    task_coordinator = (
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
    immich_duplicate_sync_service = (
        ImmichDuplicateSyncService(task_coordinator, immich_duplicate_repository)
        if task_coordinator is not None and immich_duplicate_repository is not None
        else None
    )
    if task_coordinator is not None and immich_duplicate_repository is not None:
        task_coordinator.register_handler(
            ImmichDuplicateSyncTaskHandler(immich, immich_duplicate_repository)
        )
    asset_sync = (
''',
)

replace_once(
    main,
    '''    duplicate_discovery = (
        CompositeGroupDiscoveryProvider(
            ImmichDuplicateProvider(immich, asset_repository),
            SimilarityDuplicateProvider(similarity_scan_repository, asset_repository),
        )
        if similarity_scan_repository is not None and asset_repository is not None
        else None
    )
''',
    '''    duplicate_discovery = (
        CompositeGroupDiscoveryProvider(
            ImmichDuplicateProvider(immich_duplicate_repository, asset_repository),
            SimilarityDuplicateProvider(similarity_scan_repository, asset_repository),
        )
        if similarity_scan_repository is not None
        and asset_repository is not None
        and immich_duplicate_repository is not None
        else None
    )
''',
)

replace_once(
    main,
    '''        task_coordinator.register_handler(
            AssetSyncTaskHandler(
                asset_sync,
                after_success=similarity_maintenance_service.start_if_pending,
            )
        )
''',
    '''        async def after_asset_sync_success() -> None:
            await similarity_maintenance_service.start_if_pending()
            if immich_duplicate_sync_service is not None:
                await immich_duplicate_sync_service.start_after_asset_sync()

        task_coordinator.register_handler(
            AssetSyncTaskHandler(
                asset_sync,
                after_success=after_asset_sync_success,
            )
        )
''',
)

replace_once(
    main,
    '''    def require_duplicate_service() -> CrossSourceDuplicateService:
        if duplicate_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return duplicate_service

    def require_similarity_scan_service() -> SimilarityScanService:
''',
    '''    def require_duplicate_service() -> CrossSourceDuplicateService:
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
''',
)

replace_once(
    main,
    '''    @app.get("/api/settings/duplicates/policy", response_model=DuplicatePolicy)
''',
    '''    @app.get(
        "/api/settings/duplicates/immich-sync",
        response_model=ImmichDuplicateSyncStatus,
    )
    async def immich_duplicate_sync_status() -> ImmichDuplicateSyncStatus:
        return await require_immich_duplicate_sync_service().status()

    @app.post(
        "/api/settings/duplicates/immich-sync",
        response_model=ImmichDuplicateSyncTaskStart,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_immich_duplicate_sync() -> ImmichDuplicateSyncTaskStart:
        return await require_immich_duplicate_sync_service().start()

    @app.get("/api/settings/duplicates/policy", response_model=DuplicatePolicy)
''',
)

replace_once(
    settings,
    '''  import V2ActiveTasksSettings from '../components/V2ActiveTasksSettings.svelte';
''',
    '''  import V2ActiveTasksSettings from '../components/V2ActiveTasksSettings.svelte';
  import V2ImmichDuplicateSyncSettings from '../components/V2ImmichDuplicateSyncSettings.svelte';
''',
)

replace_once(
    settings,
    '''    {:else if tab === 'Duplicates'}
      <V2Card title="Implementation not done yet">
        {#snippet actions()}<V2Badge tone="warn" text="Live actions disabled" />{/snippet}
        <V2Notice tone="warning" title="This settings area is not live yet">Duplicate settings are intentionally disabled in V2 until their live integration is complete.</V2Notice>
      </V2Card>
''',
    '''    {:else if tab === 'Duplicates'}
      <V2Stack gap="md">
        <V2ImmichDuplicateSyncSettings />
        <V2Card title="Duplicate policy">
          {#snippet actions()}<V2Badge tone="warn" text="Policy UI pending" />{/snippet}
          <V2Notice tone="info">Immich duplicate synchronization is live. The remaining duplicate policy controls will move into this section separately.</V2Notice>
        </V2Card>
      </V2Stack>
''',
)

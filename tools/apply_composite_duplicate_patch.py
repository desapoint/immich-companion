from pathlib import Path

path = Path("backend/companion/main.py")
text = path.read_text()

text = text.replace(
    "from companion.collection_delete_service import (\n",
    "from companion.collection_delete_service import (\n",
)
text = text.replace(
    "from companion.config import Settings, get_settings\n",
    "from companion.composite_duplicate_repository import CompositeDuplicateRepository\n"
    "from companion.composite_duplicate_sync import (\n"
    "    CompositeDuplicateRebuildTaskHandler,\n"
    "    CompositeDuplicateSyncService,\n"
    "    FollowUpTaskHandler,\n"
    ")\n"
    "from companion.config import Settings, get_settings\n",
)
text = text.replace(
    "from companion.discovery import (\n"
    "    CompositeGroupDiscoveryProvider,\n"
    "    ImmichDuplicateProvider,\n"
    "    SimilarityDuplicateProvider,\n"
    ")\n",
    "from companion.discovery import (\n"
    "    CompositeGroupDiscoveryProvider,\n"
    "    ImmichDuplicateProvider,\n"
    "    PersistedCompositeDuplicateProvider,\n"
    "    SimilarityDuplicateProvider,\n"
    ")\n",
)

old = '''    immich_duplicate_repository = (\n        ImmichDuplicateRepository(database) if database is not None else None\n    )\n    immich_duplicate_sync_service = (\n        ImmichDuplicateSyncService(task_coordinator, immich_duplicate_repository)\n        if task_coordinator is not None and immich_duplicate_repository is not None\n        else None\n    )\n    if task_coordinator is not None and immich_duplicate_repository is not None:\n        task_coordinator.register_handler(\n            ImmichDuplicateSyncTaskHandler(immich, immich_duplicate_repository)\n        )\n'''
new = '''    immich_duplicate_repository = (\n        ImmichDuplicateRepository(database) if database is not None else None\n    )\n    composite_duplicate_repository = (\n        CompositeDuplicateRepository(database) if database is not None else None\n    )\n    source_duplicate_discovery = (\n        CompositeGroupDiscoveryProvider(\n            ImmichDuplicateProvider(immich_duplicate_repository, asset_repository),\n            SimilarityDuplicateProvider(similarity_scan_repository, asset_repository),\n        )\n        if similarity_scan_repository is not None\n        and asset_repository is not None\n        and immich_duplicate_repository is not None\n        else None\n    )\n    composite_duplicate_sync_service = (\n        CompositeDuplicateSyncService(task_coordinator)\n        if task_coordinator is not None\n        and source_duplicate_discovery is not None\n        and composite_duplicate_repository is not None\n        else None\n    )\n    if (\n        task_coordinator is not None\n        and source_duplicate_discovery is not None\n        and composite_duplicate_repository is not None\n    ):\n        task_coordinator.register_handler(\n            CompositeDuplicateRebuildTaskHandler(\n                source_duplicate_discovery,\n                composite_duplicate_repository,\n            )\n        )\n    immich_duplicate_sync_service = (\n        ImmichDuplicateSyncService(task_coordinator, immich_duplicate_repository)\n        if task_coordinator is not None and immich_duplicate_repository is not None\n        else None\n    )\n    if task_coordinator is not None and immich_duplicate_repository is not None:\n        immich_duplicate_handler = ImmichDuplicateSyncTaskHandler(\n            immich, immich_duplicate_repository\n        )\n        task_coordinator.register_handler(\n            FollowUpTaskHandler(\n                immich_duplicate_handler,\n                composite_duplicate_sync_service.start_after_source_change,\n            )\n            if composite_duplicate_sync_service is not None\n            else immich_duplicate_handler\n        )\n'''
if old not in text:
    raise SystemExit("immich duplicate wiring block not found")
text = text.replace(old, new)

old = '''    duplicate_discovery = (\n        CompositeGroupDiscoveryProvider(\n            ImmichDuplicateProvider(immich_duplicate_repository, asset_repository),\n            SimilarityDuplicateProvider(similarity_scan_repository, asset_repository),\n        )\n        if similarity_scan_repository is not None\n        and asset_repository is not None\n        and immich_duplicate_repository is not None\n        else None\n    )\n'''
new = '''    duplicate_discovery = (\n        PersistedCompositeDuplicateProvider(\n            composite_duplicate_repository,\n            asset_repository,\n        )\n        if composite_duplicate_repository is not None\n        and asset_repository is not None\n        else None\n    )\n'''
if old not in text:
    raise SystemExit("duplicate discovery block not found")
text = text.replace(old, new)

old = '''        task_coordinator.register_handler(\n            RefreshingDuplicateResolutionTaskHandler(\n                duplicate_service,\n                immich_duplicate_sync_service,\n            )\n        )\n'''
new = '''        resolution_handler = RefreshingDuplicateResolutionTaskHandler(\n            duplicate_service,\n            immich_duplicate_sync_service,\n        )\n        task_coordinator.register_handler(\n            FollowUpTaskHandler(\n                resolution_handler,\n                composite_duplicate_sync_service.start_after_source_change,\n            )\n            if composite_duplicate_sync_service is not None\n            else resolution_handler\n        )\n'''
if old not in text:
    raise SystemExit("resolution handler block not found")
text = text.replace(old, new)

old = '''        task_coordinator.register_handler(\n            SimilarityScanTaskHandler(\n                search_feature_repository,\n                similarity_repository,\n                similarity_scan_repository,\n                similarity_index_maintainer,\n                detail_maintainer,\n            )\n        )\n'''
new = '''        similarity_scan_handler = SimilarityScanTaskHandler(\n            search_feature_repository,\n            similarity_repository,\n            similarity_scan_repository,\n            similarity_index_maintainer,\n            detail_maintainer,\n        )\n        task_coordinator.register_handler(\n            FollowUpTaskHandler(\n                similarity_scan_handler,\n                composite_duplicate_sync_service.start_after_source_change,\n            )\n            if composite_duplicate_sync_service is not None\n            else similarity_scan_handler\n        )\n'''
if old not in text:
    raise SystemExit("similarity scan handler block not found")
text = text.replace(old, new)

old = '''            await task_coordinator.start()\n            if similarity_maintenance_service is not None:\n                await similarity_maintenance_service.start_if_pending()\n'''
new = '''            await task_coordinator.start()\n            if similarity_maintenance_service is not None:\n                await similarity_maintenance_service.start_if_pending()\n            if composite_duplicate_sync_service is not None:\n                await composite_duplicate_sync_service.start_after_source_change()\n'''
if old not in text:
    raise SystemExit("lifespan startup block not found")
text = text.replace(old, new)

path.write_text(text)

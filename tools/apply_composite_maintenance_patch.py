from pathlib import Path

path = Path("backend/companion/main.py")
text = path.read_text()
old = '''        task_coordinator.register_handler(\n            SimilarityMaintenanceTaskHandler(\n                similarity_maintenance_repository,\n                similarity_index_maintainer,\n                search_feature_repository,\n                similarity_repository,\n                similarity_scan_repository,\n                detail_maintainer,\n            )\n        )\n'''
new = '''        similarity_maintenance_handler = SimilarityMaintenanceTaskHandler(\n            similarity_maintenance_repository,\n            similarity_index_maintainer,\n            search_feature_repository,\n            similarity_repository,\n            similarity_scan_repository,\n            detail_maintainer,\n        )\n        task_coordinator.register_handler(\n            FollowUpTaskHandler(\n                similarity_maintenance_handler,\n                composite_duplicate_sync_service.start_after_source_change,\n            )\n            if composite_duplicate_sync_service is not None\n            else similarity_maintenance_handler\n        )\n'''
if old not in text:
    raise SystemExit("similarity maintenance handler block not found")
path.write_text(text.replace(old, new))

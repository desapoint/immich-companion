from pathlib import Path

path = Path("backend/companion/main.py")
text = path.read_text()
old = '''        resolution_handler = RefreshingDuplicateResolutionTaskHandler(\n            duplicate_service,\n            immich_duplicate_sync_service,\n        )\n        task_coordinator.register_handler(\n            FollowUpTaskHandler(\n                resolution_handler,\n                composite_duplicate_sync_service.start_after_source_change,\n            )\n            if composite_duplicate_sync_service is not None\n            else resolution_handler\n        )\n'''
new = '''        task_coordinator.register_handler(\n            RefreshingDuplicateResolutionTaskHandler(\n                duplicate_service,\n                immich_duplicate_sync_service,\n            )\n        )\n'''
if old not in text:
    raise SystemExit("resolution composite follow-up block not found")
path.write_text(text.replace(old, new))

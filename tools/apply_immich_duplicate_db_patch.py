"""One-shot follow-up patch for duplicate-resolution snapshot refresh."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "backend/companion/main.py"


def replace_once(old: str, new: str) -> None:
    content = MAIN.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one main.py match, found {count}: {old[:80]!r}")
    MAIN.write_text(content.replace(old, new), encoding="utf-8")


replace_once(
    '''from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
    DuplicateResolutionTaskHandler,
)
''',
    '''from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
)
''',
)

replace_once(
    '''    ImmichDuplicateSyncTaskHandler,
    ImmichDuplicateSyncTaskStart,
)
''',
    '''    ImmichDuplicateSyncTaskHandler,
    ImmichDuplicateSyncTaskStart,
    RefreshingDuplicateResolutionTaskHandler,
)
''',
)

replace_once(
    '''    if (
        task_coordinator is not None
        and duplicate_service is not None
        and integrity_handler is not None
    ):
''',
    '''    if (
        task_coordinator is not None
        and duplicate_service is not None
        and integrity_handler is not None
        and immich_duplicate_sync_service is not None
    ):
''',
)

replace_once(
    '''        task_coordinator.register_handler(DuplicateResolutionTaskHandler(duplicate_service))
''',
    '''        task_coordinator.register_handler(
            RefreshingDuplicateResolutionTaskHandler(
                duplicate_service,
                immich_duplicate_sync_service,
            )
        )
''',
)

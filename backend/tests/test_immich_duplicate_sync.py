"""Tests for durable Immich duplicate snapshot synchronization."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.immich import ImmichAsset, ImmichDuplicateGroup
from companion.immich_duplicate_repository import ImmichDuplicateSnapshotMetadata
from companion.immich_duplicate_sync import (
    IMMICH_DUPLICATE_SYNC_DEDUPLICATION_KEY,
    IMMICH_DUPLICATE_SYNC_TASK_TYPE,
    ImmichDuplicateSyncService,
    ImmichDuplicateSyncTaskHandler,
)

NOW = datetime(2026, 9, 14, tzinfo=UTC)
ASSET_1 = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ASSET_2 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
GROUP_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def asset(asset_id: UUID) -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(asset_id),
            "type": "IMAGE",
            "originalFileName": f"{asset_id}.jpg",
            "originalMimeType": "image/jpeg",
            "fileCreatedAt": NOW.isoformat(),
            "fileModifiedAt": NOW.isoformat(),
            "exifInfo": {"fileSizeInByte": 100},
        }
    )


class Context:
    def __init__(self) -> None:
        self.checkpoints = []

    async def checkpoint(self, **kwargs) -> None:
        self.checkpoints.append(kwargs)


@pytest.mark.asyncio
async def test_sync_handler_fetches_and_publishes_one_complete_snapshot() -> None:
    groups = [
        ImmichDuplicateGroup(
            duplicate_id=GROUP_ID,
            assets=[asset(ASSET_1), asset(ASSET_2)],
        )
    ]

    class Immich:
        async def list_duplicate_groups(self):
            return groups

    class Repository:
        received = None

        async def replace_snapshot(self, value):
            self.received = value
            return ImmichDuplicateSnapshotMetadata(3, 1, 2, NOW)

    repository = Repository()
    context = Context()
    result = await ImmichDuplicateSyncTaskHandler(Immich(), repository).execute(context, {})

    assert repository.received == groups
    assert result.counters == {"groups": 1, "members": 2}
    assert result.summary["generation"] == 3
    assert context.checkpoints[0]["checkpoint"] == {"phase": "fetching"}
    assert context.checkpoints[-1]["checkpoint"] == {
        "phase": "published",
        "generation": 3,
    }


@pytest.mark.asyncio
async def test_sync_service_uses_durable_deduplicated_task_submission() -> None:
    task_id = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")

    class Tasks:
        submitted = None
        started = 0

        async def submit(self, *args, **kwargs):
            self.submitted = (args, kwargs)
            return SimpleNamespace(id=task_id)

        async def start(self):
            self.started += 1

    class Repository:
        async def metadata(self):
            return ImmichDuplicateSnapshotMetadata(0, 0, 0, None)

    tasks = Tasks()
    started = await ImmichDuplicateSyncService(tasks, Repository()).start()

    assert started.task_id == task_id
    assert tasks.submitted[0] == (IMMICH_DUPLICATE_SYNC_TASK_TYPE, {})
    assert tasks.submitted[1]["deduplication_key"] == IMMICH_DUPLICATE_SYNC_DEDUPLICATION_KEY
    assert tasks.started == 1

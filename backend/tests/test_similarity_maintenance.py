from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.asset_repository import similarity_upsert_changes
from companion.similarity_maintenance import (
    SIMILARITY_BACKGROUND_PRIORITY,
    SimilarityAssetChange,
    SimilarityMaintenanceService,
    SimilarityMaintenanceTaskHandler,
)
from companion.similarity_scan_repository import SimilarityScanParameters


class FakeChanges:
    def __init__(self, changes: list[SimilarityAssetChange]) -> None:
        self.changes = list(changes)
        self.acknowledged: list[UUID] = []

    async def pending(self, limit: int):
        return self.changes[:limit]

    async def acknowledge(self, change: SimilarityAssetChange) -> bool:
        current = next(
            (item for item in self.changes if item.asset_id == change.asset_id),
            None,
        )
        if current != change:
            return False
        self.changes.remove(current)
        self.acknowledged.append(change.asset_id)
        return True

    async def count(self) -> int:
        return len(self.changes)


class FakeIndexer:
    def __init__(self) -> None:
        self.asset_ids: list[UUID] = []

    async def fingerprint_changed_asset(self, _context, asset_id: UUID) -> bool:
        self.asset_ids.append(asset_id)
        return True


class FakeFeatures:
    def __init__(self, current: set[UUID] | None = None, count: int = 120) -> None:
        self.current = current or set()
        self.count = count

    async def has_current(self, asset_id: UUID) -> bool:
        return asset_id in self.current

    async def count_current(self) -> int:
        return self.count


class FakeScans:
    def __init__(self, *, active: bool = True) -> None:
        self.active = active
        self.invalidated: list[UUID] = []

    async def latest_completed_parameters(self):
        if not self.active:
            return None
        return UUID(int=999), SimilarityScanParameters(
            model_version="appearance-v1",
            feature_version=4,
            comparison_version=4,
            scope="all_eligible_assets",
            similarity_threshold=92,
            maximum_perceptual_distance=12,
            maximum_aspect_difference=0.05,
            maximum_neighbors_per_asset=8,
            maximum_matches=5_000,
        )

    async def replace_asset_pairs(
        self,
        _scan_id: UUID,
        asset_id: UUID,
        pairs,
        *,
        asset_count: int,
    ) -> None:
        assert pairs == []
        assert asset_count == 120
        self.invalidated.append(asset_id)


class FakeContext:
    def __init__(self, *, interrupt_after: int | None = None) -> None:
        self.task = SimpleNamespace(counters={})
        self.interrupt_after = interrupt_after
        self.checkpoints = 0

    async def ensure_active(self) -> None:
        return None

    async def checkpoint(self, **_values) -> None:
        self.checkpoints += 1
        if self.interrupt_after == self.checkpoints:
            raise RuntimeError("simulated worker restart")


@pytest.mark.asyncio
async def test_maintenance_indexes_asset_and_invalidates_stale_scan_without_discovery() -> None:
    asset_id = UUID(int=1)
    changes = FakeChanges(
        [SimilarityAssetChange(asset_id, "upsert", "source-1", datetime.now(UTC))]
    )
    indexer = FakeIndexer()
    scans = FakeScans()
    handler = SimilarityMaintenanceTaskHandler(
        changes,
        indexer,
        FakeFeatures(),
        scans,
    )

    result = await handler.execute(FakeContext(), {})

    assert indexer.asset_ids == [asset_id]
    assert scans.invalidated == [asset_id]
    assert changes.acknowledged == [asset_id]
    assert result.summary == {
        "incremental": True,
        "full_scan_started": False,
        "discovery_deferred": True,
    }
    assert result.counters["features_refreshed"] == 1
    assert result.counters["scan_assets_invalidated"] == 1


@pytest.mark.asyncio
async def test_maintenance_does_not_require_completed_scan_to_index_asset() -> None:
    asset_id = UUID(int=2)
    changes = FakeChanges(
        [SimilarityAssetChange(asset_id, "upsert", "source-2", datetime.now(UTC))]
    )
    indexer = FakeIndexer()
    scans = FakeScans(active=False)
    handler = SimilarityMaintenanceTaskHandler(
        changes,
        indexer,
        FakeFeatures(),
        scans,
    )

    result = await handler.execute(FakeContext(), {})

    assert indexer.asset_ids == [asset_id]
    assert scans.invalidated == []
    assert result.counters["scan_assets_invalidated"] == 0


@pytest.mark.asyncio
async def test_background_maintenance_is_submitted_below_normal_sync_priority():
    class FakeTasks:
        submitted = None
        started = False

        async def submit(self, task_type, payload, **options):
            self.submitted = (task_type, payload, options)
            return SimpleNamespace(id=UUID(int=1))

        async def start(self):
            self.started = True

    tasks = FakeTasks()
    changes = FakeChanges(
        [SimilarityAssetChange(UUID(int=1), "upsert", "source-1", datetime.now(UTC))]
    )
    service = SimilarityMaintenanceService(tasks, changes)

    await service.start_if_pending()

    assert SIMILARITY_BACKGROUND_PRIORITY < 10
    assert tasks.submitted[0] == "similarity_maintenance"
    assert tasks.submitted[2]["priority"] == SIMILARITY_BACKGROUND_PRIORITY
    assert tasks.submitted[2]["deduplication_key"] == "pending-asset-changes"
    assert tasks.started is True


def test_incremental_detection_excludes_unchanged_overlap_assets():
    created = [UUID(int=index) for index in range(1, 101)]
    modified = [UUID(int=index) for index in range(101, 121)]
    unchanged = [UUID(int=index) for index in range(121, 1_121)]
    assets = [
        SimpleNamespace(
            id=asset_id,
            asset_type="IMAGE",
            file_size_bytes=asset_id.int,
            file_modified_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        for asset_id in [*created, *modified, *unchanged]
    ]
    existing = {
        asset_id: (
            "generic-sync-fingerprint",
            1,
            asset_id.int,
            datetime(2026, 1, 1, tzinfo=UTC),
        )
        for asset_id in modified
    } | {
        asset_id: (
            "changed-generic-metadata-fingerprint",
            1,
            asset_id.int,
            datetime(2026, 1, 2, tzinfo=UTC),
        )
        for asset_id in unchanged
    }

    changes = similarity_upsert_changes(assets, existing)

    assert [asset_id for asset_id, _, _ in changes] == [*created, *modified]
    assert len(changes) == 120


def test_change_detection_reuses_known_size_when_lightweight_sync_omits_it() -> None:
    asset_id = UUID(int=1)
    modified_at = datetime(2026, 1, 2, tzinfo=UTC)
    asset = SimpleNamespace(
        id=asset_id,
        asset_type="IMAGE",
        file_size_bytes=None,
        file_modified_at=modified_at,
    )
    existing = {
        asset_id: (
            "generic-sync-fingerprint",
            1,
            42_000,
            modified_at,
        )
    }

    assert similarity_upsert_changes([asset], existing) == []


@pytest.mark.asyncio
async def test_index_maintenance_only_processes_changes_and_resumes_without_duplicates():
    now = datetime.now(UTC)
    added = [UUID(int=index) for index in range(1, 101)]
    modified = [UUID(int=index) for index in range(101, 121)]
    deleted = [UUID(int=index) for index in range(121, 131)]
    changes = FakeChanges(
        [
            SimilarityAssetChange(asset_id, "upsert", f"fingerprint-{asset_id}", now)
            for asset_id in [*added, *modified]
        ]
        + [
            SimilarityAssetChange(asset_id, "delete", None, now)
            for asset_id in deleted
        ]
    )
    indexer = FakeIndexer()
    scans = FakeScans()
    handler = SimilarityMaintenanceTaskHandler(
        changes,
        indexer,
        FakeFeatures(),
        scans,
    )

    with pytest.raises(RuntimeError, match="simulated worker restart"):
        await handler.execute(FakeContext(interrupt_after=65), {})

    assert len(changes.changes) == 65
    result = await handler.execute(FakeContext(), {})

    assert set(indexer.asset_ids) == set([*added, *modified])
    assert len(indexer.asset_ids) == 120
    assert set(scans.invalidated) == set([*added, *modified, *deleted])
    assert len(scans.invalidated) == 130
    assert set(changes.acknowledged) == set([*added, *modified, *deleted])
    assert len(changes.acknowledged) == 130
    assert changes.changes == []
    assert result.summary["discovery_deferred"] is True
    assert result.counters["assets_pending"] == 0


@pytest.mark.asyncio
async def test_worker_reuses_fingerprint_committed_by_library_index_without_counting_delete(
) -> None:
    asset_id = UUID(int=500)
    change = SimilarityAssetChange(asset_id, "upsert", "source-500", datetime.now(UTC))
    changes = FakeChanges([change])
    indexer = FakeIndexer()
    features = FakeFeatures(current={asset_id})
    handler = SimilarityMaintenanceTaskHandler(
        changes,
        indexer,
        features,
        FakeScans(),
    )

    result = await handler.execute(FakeContext(), {})

    assert indexer.asset_ids == []
    assert changes.acknowledged == [asset_id]
    assert result.counters["deletes_reconciled"] == 0
    assert result.counters["scan_assets_invalidated"] == 1

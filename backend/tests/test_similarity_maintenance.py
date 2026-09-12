from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.asset_repository import similarity_upsert_changes
from companion.similarity_maintenance import (
    SimilarityAssetChange,
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


class FakeIntegrityHandler:
    def __init__(self) -> None:
        self.asset_ids: list[UUID] = []

    async def analyze(self, _context, asset_id: UUID, *, publish_progress: bool):
        assert publish_progress is False
        self.asset_ids.append(asset_id)
        return SimpleNamespace()


class FakeFeatures:
    current: set[UUID] = set()

    async def has_current_similarity_feature(self, _asset_id: UUID) -> bool:
        return _asset_id in self.current

    async def get_similarity_feature(self, _asset_id: UUID):
        return None

    async def get_similarity_features(self, _asset_ids: list[UUID]):
        return {}

    async def iter_current_similarity_features(self, *, batch_size: int):
        assert batch_size == 1_000
        if False:
            yield []

    async def count_current_similarity_features(self) -> int:
        return 120


class FakeScans:
    def __init__(self) -> None:
        self.reconciled: list[UUID] = []

    async def latest_completed_parameters(self):
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
        self.reconciled.append(asset_id)


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


@pytest.mark.asyncio
async def test_incremental_pipeline_only_processes_changes_and_resumes_without_duplicates():
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
    integrity = FakeIntegrityHandler()
    scans = FakeScans()
    handler = SimilarityMaintenanceTaskHandler(
        changes,
        integrity,
        FakeFeatures(),
        SimpleNamespace(),
        scans,
    )

    with pytest.raises(RuntimeError, match="simulated worker restart"):
        await handler.execute(FakeContext(interrupt_after=65), {})

    assert len(changes.changes) == 65
    result = await handler.execute(FakeContext(), {})

    assert set(integrity.asset_ids) == set([*added, *modified])
    assert len(integrity.asset_ids) == 120
    assert set(scans.reconciled) == set([*added, *modified, *deleted])
    assert len(scans.reconciled) == 130
    assert set(changes.acknowledged) == set([*added, *modified, *deleted])
    assert len(changes.acknowledged) == 130
    assert changes.changes == []
    assert result.summary == {"incremental": True, "full_scan_started": False}
    assert result.counters["assets_pending"] == 0


@pytest.mark.asyncio
async def test_incremental_worker_reuses_fingerprint_committed_by_library_index() -> None:
    asset_id = UUID(int=500)
    change = SimilarityAssetChange(asset_id, "upsert", "source-500", datetime.now(UTC))
    changes = FakeChanges([change])
    integrity = FakeIntegrityHandler()
    features = FakeFeatures()
    features.current = {asset_id}
    handler = SimilarityMaintenanceTaskHandler(
        changes, integrity, features, SimpleNamespace(), FakeScans()
    )

    await handler.execute(FakeContext(), {})

    assert integrity.asset_ids == []
    assert changes.acknowledged == [asset_id]

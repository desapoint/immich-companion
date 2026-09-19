"""Tests for durable provider-neutral duplicate projection rebuilds."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.composite_duplicate_repository import (
    CompositeDuplicateRepository,
    CompositeDuplicateSnapshotGroup,
    CompositeDuplicateSnapshotMetadata,
    CompositeDuplicateSnapshotPage,
    _group_projection_summary,
)
from companion.composite_duplicate_sync import (
    COMPOSITE_DUPLICATE_REBUILD_DEDUPLICATION_KEY,
    COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE,
    CompositeDuplicateRebuildTaskHandler,
    CompositeDuplicateSyncService,
    FollowUpTaskHandler,
)
from companion.discovery import PersistedCompositeDuplicateProvider
from companion.discovery.base import DiscoveredGroup, DiscoveryEvidence
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_grouping import (
    SimilarityAdmissionEvidence,
    ValidatedSimilarityGroup,
)
from companion.task_schema import TaskResult

NOW = datetime(2026, 9, 14, tzinfo=UTC)
ASSET_1 = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ASSET_2 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
TASK_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


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


def validation() -> ValidatedSimilarityGroup:
    return ValidatedSimilarityGroup(
        asset_ids=(ASSET_1, ASSET_2),
        anchor_asset_id=ASSET_1,
        validation_mode="linked",
        minimum_similarity_percent=91.0,
        maximum_similarity_percent=94.0,
        pair_count=1,
        admission_evidence=(
            SimilarityAdmissionEvidence(
                asset_id=ASSET_1,
                admitted_by_asset_id=None,
                admission_similarity_percent=None,
                best_group_match_asset_id=ASSET_2,
                best_group_match_similarity_percent=94.0,
                link_depth=0,
            ),
            SimilarityAdmissionEvidence(
                asset_id=ASSET_2,
                admitted_by_asset_id=ASSET_1,
                admission_similarity_percent=94.0,
                best_group_match_asset_id=ASSET_1,
                best_group_match_similarity_percent=94.0,
                link_depth=0,
            ),
        ),
    )


class Context:
    def __init__(self) -> None:
        self.checkpoints = []

    async def checkpoint(self, **kwargs) -> None:
        self.checkpoints.append(kwargs)


@pytest.mark.asyncio
async def test_persisted_provider_preserves_composite_contract_without_source_discovery() -> None:
    snapshot = CompositeDuplicateSnapshotGroup(
        group_id="immich:provider-1",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="provider-1",
        asset_ids=(ASSET_1, ASSET_2),
        provider_metadata={"source": "companion_database"},
        evidence=(
            DiscoveryEvidence(
                discovery_source=DiscoverySource.IMMICH_DUPLICATE,
                provider_group_id="provider-1",
                metadata={"endpoint": "/api/duplicates"},
            ),
            DiscoveryEvidence(
                discovery_source=DiscoverySource.COMPANION_SIMILARITY,
                provider_group_id="scan-1",
                metadata={"scan_id": "scan-1"},
            ),
        ),
        similarity_validation=validation(),
    )

    class Snapshots:
        calls = 0

        async def groups(self):
            self.calls += 1
            return [snapshot]

    class Assets:
        async def get_immich_assets(self, asset_ids):
            return {asset_id: asset(asset_id) for asset_id in asset_ids}

    snapshots = Snapshots()
    groups = await PersistedCompositeDuplicateProvider(snapshots, Assets()).discover()

    assert snapshots.calls == 1
    assert len(groups) == 1
    assert groups[0].group_id == snapshot.group_id
    assert groups[0].provider_group_id == snapshot.provider_group_id
    assert groups[0].discovery_source is DiscoverySource.IMMICH_DUPLICATE
    assert groups[0].evidence == snapshot.evidence
    assert groups[0].similarity_validation == snapshot.similarity_validation
    assert [item.id for item in groups[0].assets] == [ASSET_1, ASSET_2]


@pytest.mark.asyncio
async def test_persisted_provider_pages_before_asset_hydration() -> None:
    second_group = CompositeDuplicateSnapshotGroup(
        group_id="companion:similarity:2",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id="scan-2",
        asset_ids=(ASSET_1, ASSET_2),
        provider_metadata={},
        evidence=(
            DiscoveryEvidence(
                discovery_source=DiscoverySource.COMPANION_SIMILARITY,
                provider_group_id="scan-2",
            ),
        ),
        similarity_validation=validation(),
    )

    class Snapshots:
        received = None

        async def page(self, **kwargs):
            self.received = kwargs
            return CompositeDuplicateSnapshotPage(
                groups=[second_group],
                total=23,
                page=3,
                page_size=1,
                pages=23,
            )

    class Assets:
        requested = None

        async def get_immich_assets(self, asset_ids):
            self.requested = asset_ids
            return {asset_id: asset(asset_id) for asset_id in asset_ids}

    snapshots = Snapshots()
    assets = Assets()
    result = await PersistedCompositeDuplicateProvider(snapshots, assets).discover_page(
        page=3,
        page_size=1,
        source="similarity",
        sort="similarity",
        direction="asc",
        state="needs_review",
    )

    assert snapshots.received == {
        "page": 3,
        "page_size": 1,
        "source": DiscoverySource.COMPANION_SIMILARITY,
        "sort": "similarity",
        "direction": "asc",
        "state": "needs_review",
        "group_ids": None,
    }
    assert assets.requested == [ASSET_1, ASSET_2]
    assert result.total == 23
    assert result.pages == 23
    assert [group.group_id for group in result.groups] == [second_group.group_id]


@pytest.mark.asyncio
async def test_persisted_provider_pages_selected_ids_before_asset_hydration() -> None:
    selected = ["immich:selected", "immich:off-page"]
    snapshot_group = CompositeDuplicateSnapshotGroup(
        group_id=selected[0],
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="selected",
        asset_ids=(ASSET_1, ASSET_2),
        provider_metadata={},
        evidence=(),
        similarity_validation=None,
    )

    class Snapshots:
        received = None

        async def page(self, **kwargs):
            self.received = kwargs
            return CompositeDuplicateSnapshotPage(
                groups=[snapshot_group],
                total=2,
                page=1,
                page_size=1,
                pages=2,
            )

    class Assets:
        requested = None

        async def get_immich_assets(self, asset_ids):
            self.requested = asset_ids
            return {asset_id: asset(asset_id) for asset_id in asset_ids}

    snapshots = Snapshots()
    assets = Assets()
    result = await PersistedCompositeDuplicateProvider(
        snapshots,
        assets,
    ).discover_selected_page(
        selected,
        page=1,
        page_size=1,
        source="immich",
        sort="members",
        direction="desc",
    )

    assert snapshots.received == {
        "page": 1,
        "page_size": 1,
        "source": DiscoverySource.IMMICH_DUPLICATE,
        "sort": "members",
        "direction": "desc",
        "state": "all",
        "group_ids": selected,
    }
    assert assets.requested == [ASSET_1, ASSET_2]
    assert result.total == 2
    assert [group.group_id for group in result.groups] == [selected[0]]


def test_composite_repository_exposes_paged_state_methods() -> None:
    assert callable(CompositeDuplicateRepository.page)
    assert callable(CompositeDuplicateRepository.matching_group_ids)
    assert callable(CompositeDuplicateRepository.update_v2_policy_states)
    assert callable(CompositeDuplicateRepository.replace_snapshot)


def test_projection_summary_supports_database_sorts() -> None:
    first = asset(ASSET_1).model_copy(update={"exif_info": {"fileSizeInByte": 400}})
    second = asset(ASSET_2).model_copy(update={"exif_info": {"fileSizeInByte": 100}})
    group = DiscoveredGroup(
        group_id="companion:similarity:summary",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id="scan-summary",
        assets=(first, second),
        similarity_validation=validation(),
    )

    summary = _group_projection_summary(group)

    assert summary["member_count"] == 2
    assert summary["reclaimable_bytes"] == 100
    assert summary["similarity_score"] == 91.0
    assert summary["oldest_taken_at"] == NOW
    assert summary["newest_taken_at"] == NOW


@pytest.mark.asyncio
async def test_rebuild_handler_materializes_source_discovery_once() -> None:
    source_group = DiscoveredGroup(
        group_id="immich:provider-1",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="provider-1",
        assets=(asset(ASSET_1), asset(ASSET_2)),
        provider_metadata={"source": "companion_database"},
    )

    class Discovery:
        calls = 0

        async def discover(self):
            self.calls += 1
            return [source_group]

    class Repository:
        received = None

        async def replace_snapshot(self, groups):
            self.received = groups
            return CompositeDuplicateSnapshotMetadata(4, 1, 2, 1, NOW)

    discovery = Discovery()
    repository = Repository()
    context = Context()
    result = await CompositeDuplicateRebuildTaskHandler(discovery, repository).execute(context, {})

    assert discovery.calls == 1
    assert repository.received == [source_group]
    assert result.summary["generation"] == 4
    assert result.counters == {"groups": 1, "members": 2, "evidence": 1}
    assert context.checkpoints[-1]["checkpoint"] == {"phase": "published", "generation": 4}


@pytest.mark.asyncio
async def test_sync_service_uses_one_deduplicated_durable_rebuild() -> None:
    class Tasks:
        submitted = None
        started = 0

        async def submit(self, *args, **kwargs):
            self.submitted = (args, kwargs)
            return SimpleNamespace(id=TASK_ID)

        async def start(self):
            self.started += 1

    tasks = Tasks()
    task_id = await CompositeDuplicateSyncService(tasks).start()

    assert task_id == TASK_ID
    assert tasks.submitted[0] == (COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE, {})
    assert tasks.submitted[1]["deduplication_key"] == COMPOSITE_DUPLICATE_REBUILD_DEDUPLICATION_KEY
    assert tasks.started == 1


@pytest.mark.asyncio
async def test_follow_up_handler_runs_only_after_delegate_success() -> None:
    events: list[str] = []

    class Delegate:
        task_type = "source"
        lane_key = "source"
        max_concurrency = 1

        async def execute(self, _context, _payload):
            events.append("source")
            return TaskResult(summary={}, counters={})

    async def follow_up():
        events.append("composite")
        return None

    result = await FollowUpTaskHandler(Delegate(), follow_up).execute(Context(), {})

    assert isinstance(result, TaskResult)
    assert events == ["source", "composite"]

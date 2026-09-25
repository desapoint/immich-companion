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
    COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE,
    CompositeDuplicateRebuildTaskHandler,
    CompositeDuplicateStartupReconcileTaskHandler,
    CompositeDuplicateSyncService,
    FollowUpTaskHandler,
    composite_projection_is_stale,
    source_change_in_progress,
)
from companion.discovery import PersistedCompositeDuplicateProvider
from companion.discovery.base import DiscoveredGroup, DiscoveryEvidence
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_grouping import (
    SimilarityAdmissionEvidence,
    ValidatedSimilarityGroup,
)
from companion.task_coordinator import PermanentTaskError
from companion.task_schema import TaskResult

NOW = datetime(2026, 9, 14, tzinfo=UTC)
ASSET_1 = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ASSET_2 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
TASK_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def asset(asset_id: UUID, *, asset_type: str = "IMAGE") -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(asset_id),
            "type": asset_type,
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

    async def ensure_active(self) -> None:
        return None


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
async def test_persisted_provider_hides_stale_groups_containing_video() -> None:
    snapshot = CompositeDuplicateSnapshotGroup(
        group_id="immich:video-provider",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="video-provider",
        asset_ids=(ASSET_1, ASSET_2),
        provider_metadata={},
        evidence=(),
        similarity_validation=None,
    )

    class Snapshots:
        async def groups(self):
            return [snapshot]

    class Assets:
        async def get_immich_assets(self, asset_ids):
            return {
                ASSET_1: asset(ASSET_1),
                ASSET_2: asset(ASSET_2, asset_type="VIDEO"),
            }

    groups = await PersistedCompositeDuplicateProvider(Snapshots(), Assets()).discover()

    assert groups == []


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
    assert callable(CompositeDuplicateRepository.unresolved_counts)
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
async def test_rebuild_handler_streams_bounded_batches_when_supported() -> None:
    first = DiscoveredGroup(
        group_id="immich:stream-1",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="stream-1",
        assets=(asset(ASSET_1), asset(ASSET_2)),
    )
    second = DiscoveredGroup(
        group_id="immich:stream-2",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="stream-2",
        assets=(asset(ASSET_1), asset(ASSET_2)),
    )

    class Discovery:
        discover_called = False

        async def discover(self):
            self.discover_called = True
            raise AssertionError("bounded rebuild must not materialize source discovery")

        async def discover_batches(self):
            yield [first]
            yield [second]

    class Repository:
        received: list[list[str]] = []

        async def replace_snapshot_batches(self, batches):
            async for batch in batches:
                self.received.append([group.group_id for group in batch])
            return CompositeDuplicateSnapshotMetadata(5, 2, 4, 2, NOW)

    discovery = Discovery()
    repository = Repository()
    context = Context()
    result = await CompositeDuplicateRebuildTaskHandler(discovery, repository).execute(context, {})

    assert discovery.discover_called is False
    assert repository.received == [[first.group_id], [second.group_id]]
    assert result.counters == {"groups": 2, "members": 4, "evidence": 2}
    assert any(
        checkpoint["progress"]["detail"].endswith("2 streamed")
        for checkpoint in context.checkpoints
        if checkpoint["progress"]["phase"] == "composite_duplicates_publish"
    )


@pytest.mark.asyncio
async def test_rebuild_handler_runs_post_publish_retention_cleanup() -> None:
    source_group = DiscoveredGroup(
        group_id="immich:retention-1",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="retention-1",
        assets=(asset(ASSET_1), asset(ASSET_2)),
    )

    class Discovery:
        async def discover(self):
            return [source_group]

    class Repository:
        async def replace_snapshot(self, groups):
            assert groups == [source_group]
            return CompositeDuplicateSnapshotMetadata(6, 1, 2, 1, NOW)

    cleanup_calls = 0

    async def cleanup():
        nonlocal cleanup_calls
        cleanup_calls += 1
        return 2

    result = await CompositeDuplicateRebuildTaskHandler(
        Discovery(),
        Repository(),
        after_publish=cleanup,
    ).execute(Context(), {})

    assert cleanup_calls == 1
    assert result.counters["similarity_pair_generations_pruned"] == 2


@pytest.mark.asyncio
async def test_rebuild_cleanup_failure_does_not_invalidate_published_projection() -> None:
    source_group = DiscoveredGroup(
        group_id="immich:retention-failure",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="retention-failure",
        assets=(asset(ASSET_1), asset(ASSET_2)),
    )

    class Discovery:
        async def discover(self):
            return [source_group]

    class Repository:
        async def replace_snapshot(self, groups):
            assert groups == [source_group]
            return CompositeDuplicateSnapshotMetadata(7, 1, 2, 1, NOW)

    async def cleanup():
        raise RuntimeError("retention cleanup unavailable")

    result = await CompositeDuplicateRebuildTaskHandler(
        Discovery(),
        Repository(),
        after_publish=cleanup,
    ).execute(Context(), {})

    assert result.summary["generation"] == 7
    assert "similarity_pair_generations_pruned" not in result.counters


@pytest.mark.asyncio
async def test_sync_service_submits_one_isolated_durable_rebuild() -> None:
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
    assert "deduplication_key" not in tasks.submitted[1]
    assert tasks.started == 1


@pytest.mark.asyncio
async def test_sync_service_propagates_child_rebuild_error() -> None:
    class Tasks:
        async def submit(self, *_args, **_kwargs):
            return SimpleNamespace(id=TASK_ID)

        async def start(self):
            return None

        async def wait(self, task_id):
            assert task_id == TASK_ID
            return SimpleNamespace(
                status="failed",
                error={"type": "RuntimeError", "message": "asset hydration failed"},
            )

    with pytest.raises(
        RuntimeError,
        match="Composite duplicate rebuild failed: asset hydration failed",
    ):
        await CompositeDuplicateSyncService(Tasks()).refresh_and_wait()


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

    context = Context()
    result = await FollowUpTaskHandler(Delegate(), follow_up).execute(context, {})

    assert isinstance(result, TaskResult)
    assert events == ["source", "composite"]
    assert [item["progress"]["phase"] for item in context.checkpoints] == [
        "duplicate_projection_publish",
        "duplicate_projection_publish",
    ]
    assert context.checkpoints[0]["progress"]["detail"] == "Publishing duplicate results…"
    assert context.checkpoints[-1]["progress"]["detail"] == "Duplicate results published."


@pytest.mark.asyncio
async def test_follow_up_failure_fails_the_parent_task() -> None:
    class Delegate:
        task_type = "source"
        lane_key = "source"
        max_concurrency = 1

        async def execute(self, _context, _payload):
            return TaskResult(summary={}, counters={})

    async def follow_up():
        raise RuntimeError("projection failed")

    with pytest.raises(
        PermanentTaskError,
        match="source work completed, but its required follow-up failed: projection failed",
    ) as raised:
        await FollowUpTaskHandler(Delegate(), follow_up).execute(Context(), {})

    assert isinstance(raised.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_follow_up_reclaims_delegate_memory_before_projection(monkeypatch) -> None:
    events: list[str] = []

    class Delegate:
        task_type = "source"
        lane_key = "source"
        max_concurrency = 1

        async def execute(self, _context, _payload):
            events.append("source")
            return TaskResult(summary={}, counters={})

    async def follow_up():
        events.append("projection")
        return None

    monkeypatch.setattr(
        "companion.composite_duplicate_sync.reclaim_process_memory",
        lambda: events.append("cleanup"),
    )

    await FollowUpTaskHandler(Delegate(), follow_up).execute(Context(), {})

    assert events == ["source", "cleanup", "projection"]


def test_projection_staleness_uses_source_success_watermarks() -> None:
    old = datetime(2026, 9, 13, tzinfo=UTC)
    current = datetime(2026, 9, 14, tzinfo=UTC)
    newer = datetime(2026, 9, 15, tzinfo=UTC)

    assert composite_projection_is_stale(None, current, current) is True
    assert composite_projection_is_stale(current, old, current) is False
    assert composite_projection_is_stale(current, newer, old) is True
    assert composite_projection_is_stale(current, old, newer) is True


def test_active_source_work_defers_startup_projection_refresh() -> None:
    tasks = [
        SimpleNamespace(task_type="similarity_scan", status="recovering"),
        SimpleNamespace(task_type="other", status="running"),
    ]
    assert source_change_in_progress(tasks) is True
    assert source_change_in_progress(
        [SimpleNamespace(task_type="similarity_scan", status="paused")]
    ) is False
    assert source_change_in_progress(
        [SimpleNamespace(task_type="composite_duplicate_rebuild", status="running")]
    ) is False


@pytest.mark.asyncio
async def test_task_coordinator_exposes_startup_active_task_listing() -> None:
    from companion.task_coordinator import TaskCoordinator

    assert callable(TaskCoordinator.list_tasks)
    assert not hasattr(TaskCoordinator, "list")


@pytest.mark.asyncio
async def test_startup_reconcile_waits_for_source_work_then_rechecks_staleness(
    monkeypatch,
) -> None:
    active = SimpleNamespace(task_type="similarity_scan", status="running")

    class Tasks:
        calls = 0

        async def list_tasks(self, **_kwargs):
            self.calls += 1
            return [active] if self.calls == 1 else []

    stale_checks = 0
    refreshes = 0

    async def is_stale():
        nonlocal stale_checks
        stale_checks += 1
        return True

    async def refresh():
        nonlocal refreshes
        refreshes += 1
        return None

    sleeps: list[float] = []

    async def no_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("companion.composite_duplicate_sync.asyncio.sleep", no_sleep)
    handler = CompositeDuplicateStartupReconcileTaskHandler(Tasks(), is_stale, refresh)
    context = Context()

    result = await handler.execute(context, {})

    assert stale_checks == 1
    assert refreshes == 1
    assert result.summary["projection_refreshed"] is True
    assert context.checkpoints[0]["checkpoint"] == {"phase": "waiting_for_sources"}
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_startup_reconcile_skips_projection_when_sources_made_it_current() -> None:
    class Tasks:
        async def list_tasks(self, **_kwargs):
            return []

    async def is_stale():
        return False

    async def refresh():
        raise AssertionError("current projection must not be rebuilt")

    result = await CompositeDuplicateStartupReconcileTaskHandler(
        Tasks(),
        is_stale,
        refresh,
    ).execute(Context(), {})

    assert result.summary == {
        "projection_refreshed": False,
        "reason": "already_current",
    }


@pytest.mark.asyncio
async def test_sync_service_does_not_coalesce_distinct_source_commits() -> None:
    submitted: list[dict[str, object]] = []

    class Tasks:
        next_id = 0

        async def submit(self, _task_type, _payload, **kwargs):
            self.next_id += 1
            submitted.append(kwargs)
            return SimpleNamespace(id=UUID(int=self.next_id))

        async def start(self):
            return None

    service = CompositeDuplicateSyncService(Tasks())
    first = await service.start()
    second = await service.start()

    assert first != second
    assert len(submitted) == 2
    assert all("deduplication_key" not in item for item in submitted)


@pytest.mark.asyncio
async def test_startup_reconcile_reports_waiting_only_once(monkeypatch) -> None:
    active = SimpleNamespace(task_type="similarity_scan", status="running")

    class Tasks:
        calls = 0

        async def list_tasks(self, **_kwargs):
            self.calls += 1
            return [active] if self.calls <= 3 else []

    async def is_stale():
        return False

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("companion.composite_duplicate_sync.asyncio.sleep", no_sleep)
    context = Context()
    await CompositeDuplicateStartupReconcileTaskHandler(
        Tasks(),
        is_stale,
        lambda: None,  # type: ignore[arg-type]
    ).execute(context, {})

    waiting = [
        item
        for item in context.checkpoints
        if item["checkpoint"] == {"phase": "waiting_for_sources"}
    ]
    assert len(waiting) == 1

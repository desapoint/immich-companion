"""Staged sync ordering, enrichment, and checkpoint coverage."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.asset_service import AssetSyncService
from companion.config import Settings
from companion.immich import (
    ImmichAlbum,
    ImmichAsset,
    ImmichAssetSearchPage,
    ImmichStack,
    ImmichStackAsset,
    ImmichTag,
)
from companion.sync_schema import SyncCapabilities, SyncEvent, SyncRunStatus
from companion.synchronization import service as asset_service_module
from companion.synchronization.steps import StackSyncStep
from companion.task_schema import TaskStatusView

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ALBUM_ID = UUID("44444444-4444-4444-8444-444444444444")
STACK_ID = UUID("55555555-5555-4555-8555-555555555555")
TAG_ID = UUID("66666666-6666-4666-8666-666666666666")
RUN_ID = UUID("77777777-7777-4777-8777-777777777777")
OWNER_ID = UUID("88888888-8888-4888-8888-888888888888")


@pytest.mark.asyncio
async def test_relation_repair_is_queued_behind_active_sync_without_waiting() -> None:
    class Coordinator:
        def __init__(self) -> None:
            self.submitted: list[tuple[str, dict[str, object], dict[str, object]]] = []
            self.started = False

        async def submit(self, task_type, payload, **options):
            self.submitted.append((task_type, payload, options))
            return SimpleNamespace(id=RUN_ID)

        async def start(self):
            self.started = True

    coordinator = Coordinator()
    service = object.__new__(AssetSyncService)
    service._coordinator = coordinator  # type: ignore[assignment]

    async def status():
        return SimpleNamespace(active=SimpleNamespace(id=RUN_ID), pending=None)

    service.status = status  # type: ignore[method-assign]
    queued = await service.enqueue_relation_repair_during_sync([("tag", TAG_ID)])

    assert queued is True
    assert coordinator.submitted == [
        (
            "asset_relation_repair",
            {"relations": [{"kind": "tag", "id": str(TAG_ID)}]},
            {"priority": 95, "lane_key": "asset_sync", "max_concurrency": 1},
        )
    ]
    assert coordinator.started is True


@pytest.mark.asyncio
async def test_asset_repair_is_queued_durably_during_active_sync() -> None:
    class Coordinator:
        def __init__(self) -> None:
            self.submitted: list[tuple[str, dict[str, object], dict[str, object]]] = []
            self.started = False

        async def submit(self, task_type, payload, **options):
            self.submitted.append((task_type, payload, options))

        async def start(self):
            self.started = True

    coordinator = Coordinator()
    service = object.__new__(AssetSyncService)
    service._coordinator = coordinator  # type: ignore[assignment]

    async def status():
        return SimpleNamespace(active=SimpleNamespace(id=RUN_ID), pending=None)

    service.status = status  # type: ignore[method-assign]
    queued = await service.enqueue_asset_repair_during_sync([ASSET_ONE, ASSET_ONE])

    assert queued is True
    assert coordinator.submitted == [
        (
            "asset_repair",
            {"asset_ids": [str(ASSET_ONE)], "include_stacks": False},
            {"priority": 90, "lane_key": "asset_sync", "max_concurrency": 1},
        )
    ]
    assert coordinator.started is True


@pytest.mark.asyncio
async def test_stack_snapshot_updates_only_action_affected_assets() -> None:
    class Assets:
        updated: tuple[list[UUID], dict[UUID, dict[str, object]]] | None = None

        async def replace_asset_stack_snapshots(self, ids, payloads):
            self.updated = (ids, payloads)

    stack = ImmichStack(
        id=RUN_ID,
        primaryAssetId=ASSET_ONE,
        assets=[stack_asset(ASSET_ONE, "member.png")],
    )

    class Immich:
        calls = 0

        async def list_stacks(self):
            self.calls += 1
            return [stack]

    assets = Assets()
    immich = Immich()
    service = object.__new__(AssetSyncService)
    service._immich = immich  # type: ignore[assignment]
    service._assets = assets  # type: ignore[assignment]

    await service.apply_stack_snapshot_for_targets([ASSET_ONE, ASSET_TWO])

    assert assets.updated == (
        [ASSET_ONE, ASSET_TWO],
        {ASSET_ONE: StackSyncStep.stack_payload(stack)[0]},
    )
    assert immich.calls == 1
    await service.apply_stack_snapshot_for_targets([ASSET_ONE], [stack])
    assert immich.calls == 1


def asset(asset_id: UUID, filename: str) -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(asset_id),
            "type": "IMAGE",
            "originalFileName": filename,
            "originalMimeType": "image/png",
            "width": 800,
            "height": 600,
            "fileCreatedAt": "2026-08-24T12:00:00Z",
            "fileModifiedAt": "2026-08-24T12:00:00Z",
            "updatedAt": "2026-08-24T12:00:00Z",
        }
    )


def stack_asset(asset_id: UUID, filename: str) -> ImmichStackAsset:
    return ImmichStackAsset.model_validate(
        {
            "id": str(asset_id),
            "type": "IMAGE",
            "originalFileName": filename,
            "originalMimeType": "image/png",
            "width": 800,
            "height": 600,
            "fileCreatedAt": "2026-08-24T12:00:00Z",
        }
    )


class FakeImmich:
    def __init__(self, assets: list[ImmichAsset], stack: ImmichStack | None) -> None:
        self.assets = assets
        self.stack = stack
        self.calls: list[str] = []

    async def list_album_catalog(self) -> list[ImmichAlbum]:
        self.calls.append("album_catalog")
        return [
            ImmichAlbum(
                id=ALBUM_ID,
                albumName="Review",
                assetCount=1,
                createdAt="2026-08-24T12:00:00Z",
                updatedAt="2026-08-24T12:00:00Z",
            )
        ]

    async def list_tag_catalog(self) -> list[ImmichTag]:
        self.calls.append("tag_catalog")
        return [
            ImmichTag(
                id=TAG_ID,
                name="Review",
                value="Review",
                color="#d97706",
                assetCount=1,
            )
        ]

    async def iter_assets(self, **_kwargs):
        self.calls.append("assets")
        for current in self.assets:
            yield current

    async def iter_asset_pages(self, **_kwargs):
        self.calls.append("assets")
        yield (
            1,
            ImmichAssetSearchPage.model_validate(
                {
                    "count": len(self.assets),
                    "total": len(self.assets),
                    "items": self.assets,
                    "nextPage": None,
                }
            ),
        )

    async def count_assets(self, **_kwargs) -> int:
        return len(self.assets)

    async def list_stacks(self) -> list[ImmichStack]:
        self.calls.append("stacks")
        return [self.stack] if self.stack is not None else []

    async def iter_stacks(self):
        self.calls.append("stacks")
        if self.stack is not None:
            yield self.stack

    async def iter_album_asset_ids(self, _album_id: UUID, **_kwargs):
        self.calls.append("album_memberships")
        yield [ASSET_ONE]

    async def iter_tag_asset_ids(self, _tag_id: UUID, **_kwargs):
        self.calls.append("tag_memberships")
        yield [ASSET_ONE]

    async def list_albums_for_asset(self, _asset_id: UUID):
        self.calls.append("asset_albums")
        return await self.list_album_catalog()

    async def get_asset(self, asset_id: UUID) -> ImmichAsset:
        self.calls.append("asset_detail")
        return next(asset for asset in self.assets if asset.id == asset_id)

    async def restore_assets(self, _asset_ids: list[UUID]) -> None:
        self.calls.append("restore")


class FakeAssetRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.assets: list[ImmichAsset] = []
        self.asset_batch_sizes: list[int] = []
        self.asset_similarity_tracking: list[bool] = []
        self.stack_payloads: list[tuple[dict[str, object], list[UUID]]] = []

    async def upsert_album_catalog(self, albums, _generation):
        self.calls.append("album_catalog")
        return len(albums), 0

    async def upsert_tag_catalog(self, tags, _generation):
        self.calls.append("tag_catalog")
        return len(tags), 0

    async def generation_asset_ids(self, _generation):
        return [current.id for current in self.assets]

    async def iter_generation_asset_ids(self, _generation, *, batch_size):
        ids = [current.id for current in self.assets]
        for offset in range(0, len(ids), batch_size):
            yield ids[offset : offset + batch_size]

    async def tag_asset_counts(self):
        return {TAG_ID: 1}

    async def upsert_asset_batch(
        self, assets, _generation, *, track_similarity_changes=True
    ):
        self.calls.append("assets")
        self.asset_batch_sizes.append(len(assets))
        self.asset_similarity_tracking.append(track_similarity_changes)
        self.assets.extend(assets)
        return len(assets), 0, 0

    async def apply_stack_batch(self, stacks, _generation):
        self.calls.append("stacks")
        self.stack_payloads.extend(stacks)
        return sum(len(asset_ids) for _, asset_ids in stacks)

    async def upsert_album_memberships(self, _album_id, asset_ids, _generation):
        self.calls.append("album_memberships")
        return len(asset_ids)

    async def upsert_tag_memberships(self, _tag_id, asset_ids, _generation):
        self.calls.append("tag_memberships")
        return len(asset_ids)

    async def finalize_generation(
        self,
        _generation,
        *,
        remove_assets,
        batch_size,
        window_start=None,
        window_end=None,
    ):
        self.calls.append("finalize")
        assert remove_assets is True
        assert batch_size == 25
        assert window_start is None
        assert window_end is None
        return {"assets_removed": 0}

    async def validate_generation(self, _generation, counters, *, full, allow_counter_repair):
        self.calls.append("validate")
        assert full is True
        assert allow_counter_repair is False
        assert counters["stack_members"] == 2
        return {
            "albums_seen": 1,
            "tags_seen": 1,
            "album_memberships": 1,
            "tag_memberships": 1,
            "stack_members": 2,
            "assets_seen": 2,
        }

    async def refresh_relation_counts(self):
        self.calls.append("counts")

    async def replace_album_memberships(self, _album_id, asset_ids):
        self.calls.append("replace_album")
        return len(asset_ids)

    async def replace_tag_memberships(self, _tag_id, asset_ids):
        self.calls.append("replace_tag")
        return len(asset_ids)

    async def replace_asset_album_memberships(self, _asset_id, _album_ids):
        self.calls.append("replace_asset_album")

    async def replace_asset_tag_memberships(self, _asset_id, _tag_ids):
        self.calls.append("replace_asset_tag")

    async def refresh_asset(self, asset):
        self.calls.append("refresh_asset")
        self.assets.append(asset)

    async def replace_asset_stack_snapshots(self, asset_ids, stack_payload_by_asset):
        self.calls.append("replace_asset_stacks")
        self.repaired_stack_ids = list(asset_ids)
        self.repaired_stack_payloads = dict(stack_payload_by_asset)


class IncrementalFakeAssetRepository(FakeAssetRepository):
    def __init__(self, window_start: datetime, window_end: datetime) -> None:
        super().__init__()
        self.window_start = window_start
        self.window_end = window_end

    async def validate_generation(self, _generation, counters, *, full, allow_counter_repair):
        self.calls.append("validate")
        assert full is False
        assert allow_counter_repair is False
        assert counters["stack_members"] == 2
        return {
            "albums_seen": 1,
            "tags_seen": 1,
            "album_memberships": 1,
            "tag_memberships": 1,
            "stack_members": 2,
        }

    async def finalize_generation(
        self,
        _generation,
        *,
        remove_assets,
        batch_size,
        window_start=None,
        window_end=None,
    ):
        self.calls.append("finalize")
        assert remove_assets is False
        assert batch_size == 25
        assert window_start == self.window_start
        assert window_end == self.window_end
        return {"assets_removed": 1}


class FakeSyncRepository:
    def __init__(self) -> None:
        self.checkpoints: list[tuple[str, str | None]] = []
        self.progress = []

    async def checkpoint(self, _run_id, _owner, *, phase, cursor, **_kwargs):
        self.checkpoints.append((phase, cursor))
        self.progress.append(_kwargs.get("progress"))


def run_status() -> SyncRunStatus:
    now = datetime.now(UTC)
    return SyncRunStatus(
        id=RUN_ID,
        mode="full",
        status="running",
        phase="catalogs",
        generation=3,
        window_start=None,
        window_end=now,
        cursor=None,
        counters={},
        attempts=1,
        error=None,
        created_at=now,
        started_at=now,
        heartbeat_at=now,
        completed_at=None,
    )


def test_legacy_complete_task_phase_is_reported_as_completed() -> None:
    now = datetime.now(UTC)
    task = TaskStatusView(
        id=RUN_ID,
        task_type="asset_sync",
        status="completed",
        priority=0,
        deduplication_key=None,
        lane_key="sync",
        payload={"mode": "full", "generation": 3, "window_end": now.isoformat()},
        checkpoint={"phase": "complete"},
        counters={"assets_seen": 12},
        progress={"phase": "complete", "completed": 12, "total": 12, "percent": 100},
        result=None,
        error=None,
        attempt=1,
        next_attempt_at=None,
        lease_owner=None,
        lease_expires_at=None,
        created_at=now,
        started_at=now,
        heartbeat_at=now,
        completed_at=now,
    )

    status = AssetSyncService._status_from_task(task)

    assert status.phase == "completed"
    assert status.progress is not None
    assert status.progress.phase == "completed"


def test_sync_memory_diagnostics_trace_only_during_sync(monkeypatch) -> None:
    tracing = False
    calls: list[str] = []

    def start() -> None:
        nonlocal tracing
        tracing = True
        calls.append("start")

    def stop() -> None:
        nonlocal tracing
        tracing = False
        calls.append("stop")

    monkeypatch.setattr(asset_service_module.tracemalloc, "is_tracing", lambda: tracing)
    monkeypatch.setattr(asset_service_module.tracemalloc, "start", start)
    monkeypatch.setattr(asset_service_module.tracemalloc, "stop", stop)
    service = AssetSyncService(
        FakeImmich([], None),
        FakeAssetRepository(),
        FakeSyncRepository(),
        Settings(sync_memory_diagnostics=True),
    )

    assert calls == []
    owned_trace = service._start_sync_memory_diagnostics()
    assert owned_trace is True
    assert calls == ["start"]
    service._stop_sync_memory_diagnostics(owned_trace)
    assert calls == ["start", "stop"]


def asset_counters() -> dict[str, int]:
    return {
        "assets_seen": 0,
        "assets_created": 0,
        "assets_updated": 0,
        "assets_unchanged": 0,
        "tag_cheap_path_eligible_assets": 0,
        "tag_cheap_path_fallback_assets": 0,
    }


def relationship_counters() -> dict[str, int]:
    return {
        "album_memberships": 0,
        "tag_memberships": 0,
        "tag_relationships_scanned": 0,
        "tag_empty_relationships": 0,
    }


@pytest.mark.asyncio
async def test_global_sync_orders_catalogs_before_media_and_relations_after() -> None:
    members = [asset(ASSET_ONE, "primary.png"), asset(ASSET_TWO, "child.png")]
    stack_members = [
        stack_asset(ASSET_ONE, "primary.png"),
        stack_asset(ASSET_TWO, "child.png"),
    ]
    stack = ImmichStack(id=STACK_ID, primaryAssetId=ASSET_ONE, assets=stack_members)
    immich = FakeImmich(members, stack)
    assets = FakeAssetRepository()
    syncs = FakeSyncRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        syncs,  # type: ignore[arg-type]
        Settings(sync_full_batch_size=25, sync_batch_size=25),
    )

    counters = await service._execute(run_status(), OWNER_ID)

    assert assets.calls == [
        "album_catalog",
        "tag_catalog",
        "assets",
        "stacks",
        "album_memberships",
        "tag_memberships",
        "validate",
        "finalize",
        "counts",
    ]
    assert immich.calls.index("album_catalog") < immich.calls.index("assets")
    assert immich.calls.index("tag_catalog") < immich.calls.index("assets")
    assert immich.calls.index("assets") < immich.calls.index("album_memberships")
    assert counters["assets_seen"] == 2
    assert assets.asset_similarity_tracking == [True]
    assert counters["album_memberships"] == 1
    assert counters["tag_memberships"] == 1
    assert assets.stack_payloads[0][0]["primaryAssetId"] == str(ASSET_ONE)
    assert syncs.checkpoints[-1] == ("finalizing", "validated")
    assert syncs.progress[-1].percent == 100
    relationship_progress = [
        item for item in syncs.progress if item is not None and item.phase == "relationships"
    ]
    assert relationship_progress
    assert all(item.total is None and item.percent is None for item in relationship_progress)
    media_progress = [
        item for item in syncs.progress if item is not None and item.phase == "assets"
    ]
    assert media_progress
    assert all(item.total == 2 for item in media_progress)
    assert media_progress[-1].completed == 2
    assert media_progress[-1].percent == 100


@pytest.mark.asyncio
async def test_incremental_stream_events_run_before_catalogs_through_event_step() -> None:
    members = [asset(ASSET_ONE, "primary.png"), asset(ASSET_TWO, "child.png")]
    stack = ImmichStack(
        id=STACK_ID,
        primaryAssetId=ASSET_ONE,
        assets=[
            stack_asset(ASSET_ONE, "primary.png"),
            stack_asset(ASSET_TWO, "child.png"),
        ],
    )
    window_start = datetime(2026, 8, 24, 11, 55, tzinfo=UTC)
    window_end = datetime(2026, 8, 24, 12, 5, tzinfo=UTC)

    class StreamImmich(FakeImmich):
        async def sync_capabilities(self):
            return SyncCapabilities(stream=True, acknowledgements=True)

        async def iter_sync_events(self, cursor=None):
            assert cursor is None
            self.calls.append("event")
            yield SyncEvent(id="event-1", kind="reset")

        async def acknowledge_sync_event(self, event_id):
            assert event_id == "event-1"
            self.calls.append("event_ack")

    immich = StreamImmich(members, stack)
    assets = IncrementalFakeAssetRepository(window_start, window_end)
    syncs = FakeSyncRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        syncs,  # type: ignore[arg-type]
        Settings(sync_batch_size=25),
    )
    run = run_status().model_copy(
        update={
            "mode": "incremental",
            "window_start": window_start,
            "window_end": window_end,
        }
    )

    counters = await service._execute(run, OWNER_ID)

    assert counters["events_seen"] == 1
    assert immich.calls.index("event") < immich.calls.index("album_catalog")
    assert immich.calls.index("event_ack") < immich.calls.index("album_catalog")
    assert ("catalogs", "event:event-1") in syncs.checkpoints


@pytest.mark.asyncio
async def test_incremental_sync_finalizes_missing_assets_inside_completed_window() -> None:
    members = [asset(ASSET_ONE, "primary.png"), asset(ASSET_TWO, "child.png")]
    stack = ImmichStack(
        id=STACK_ID,
        primaryAssetId=ASSET_ONE,
        assets=[
            stack_asset(ASSET_ONE, "primary.png"),
            stack_asset(ASSET_TWO, "child.png"),
        ],
    )
    window_start = datetime(2026, 8, 24, 11, 55, tzinfo=UTC)
    window_end = datetime(2026, 8, 24, 12, 5, tzinfo=UTC)
    immich = FakeImmich(members, stack)
    assets = IncrementalFakeAssetRepository(window_start, window_end)
    syncs = FakeSyncRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        syncs,  # type: ignore[arg-type]
        Settings(sync_batch_size=25),
    )
    run = run_status().model_copy(
        update={
            "mode": "incremental",
            "window_start": window_start,
            "window_end": window_end,
        }
    )

    counters = await service._execute(run, OWNER_ID)

    assert counters["assets_removed"] == 1
    assert assets.asset_similarity_tracking == [True]
    assert assets.calls[-2:] == ["finalize", "counts"]
    assert syncs.checkpoints[-1] == ("finalizing", "validated")
@pytest.mark.asyncio
async def test_restore_uses_immich_then_refreshes_asset_albums_and_tags() -> None:
    restored = asset(ASSET_ONE, "restored.png").model_copy(
        update={"tags": [{"id": str(TAG_ID), "name": "Review"}]}
    )
    stack = ImmichStack(
        id=STACK_ID,
        primaryAssetId=ASSET_ONE,
        assets=[stack_asset(ASSET_ONE, "restored.png")],
    )
    immich = FakeImmich([restored], stack)
    assets = FakeAssetRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSyncRepository(),  # type: ignore[arg-type]
        Settings(sync_batch_size=25),
    )

    await service.restore_targets([ASSET_ONE])

    assert immich.calls[:2] == ["restore", "asset_detail"]
    assert "asset_albums" in immich.calls
    assert assets.calls == [
        "refresh_asset",
        "replace_asset_album",
        "replace_asset_tag",
    ]
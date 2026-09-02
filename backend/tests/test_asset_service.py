"""Staged sync ordering, enrichment, and checkpoint coverage."""

import asyncio
from datetime import UTC, datetime
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
from companion.sync_schema import SyncRunStatus

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ALBUM_ID = UUID("44444444-4444-4444-8444-444444444444")
STACK_ID = UUID("55555555-5555-4555-8555-555555555555")
TAG_ID = UUID("66666666-6666-4666-8666-666666666666")
RUN_ID = UUID("77777777-7777-4777-8777-777777777777")
OWNER_ID = UUID("88888888-8888-4888-8888-888888888888")


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
    def __init__(self, assets: list[ImmichAsset], stack: ImmichStack) -> None:
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
        yield 1, ImmichAssetSearchPage.model_validate(
            {
                "count": len(self.assets),
                "total": len(self.assets),
                "items": self.assets,
                "nextPage": None,
            }
        )

    async def count_assets(self, **_kwargs) -> int:
        return len(self.assets)

    async def list_stacks(self) -> list[ImmichStack]:
        self.calls.append("stacks")
        return [self.stack]

    async def iter_stacks(self):
        self.calls.append("stacks")
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
        self.stack_payloads: list[tuple[dict[str, object], list[UUID]]] = []

    async def upsert_album_catalog(self, albums, _generation):
        self.calls.append("album_catalog")
        return len(albums), 0

    async def upsert_tag_catalog(self, tags, _generation):
        self.calls.append("tag_catalog")
        return len(tags), 0

    async def upsert_asset_batch(self, assets, _generation):
        self.calls.append("assets")
        self.asset_batch_sizes.append(len(assets))
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
        Settings(sync_batch_size=25),
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
    assert assets.calls[-2:] == ["finalize", "counts"]
    assert syncs.checkpoints[-1] == ("finalizing", "validated")


@pytest.mark.asyncio
async def test_stack_sync_persists_bounded_batches_and_skips_final_pacing() -> None:
    stack_models = [
        ImmichStack(
            id=UUID(int=index + 100),
            primaryAssetId=ASSET_ONE,
            assets=[stack_asset(ASSET_ONE, f"member-{index}.png")],
        )
        for index in range(5)
    ]

    class StreamingImmich:
        async def iter_stacks(self):
            for stack in stack_models:
                yield stack

        async def list_stacks(self):
            raise AssertionError("stack sync must use the streaming traversal")

    assets = FakeAssetRepository()
    syncs = FakeSyncRepository()
    service = AssetSyncService(
        StreamingImmich(),  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        syncs,  # type: ignore[arg-type]
        Settings(sync_full_batch_size=2),
    )
    paced: list[int] = []

    async def pace(_run, _started):
        paced.append(1)

    service._pace_full_batch = pace  # type: ignore[method-assign]
    run = run_status().model_copy(update={"phase": "stacks"})
    counters = {"stacks_seen": 0, "stack_members": 0}

    await service._sync_stacks(run, OWNER_ID, counters)

    assert [cursor for phase, cursor in syncs.checkpoints if phase == "stacks"] == [
        None,
        "stacks:1",
        "stacks:2",
        "stacks:3",
    ]
    assert paced == [1, 1]
    assert counters == {"stacks_seen": 5, "stack_members": 5}
    stack_progress = [item for item in syncs.progress if item and item.phase == "stacks"]
    assert all(item.total is None and item.percent is None for item in stack_progress)
    assert syncs.checkpoints[-1] == ("relationships", None)


@pytest.mark.asyncio
async def test_media_sync_uses_large_pages_bounded_writes_and_page_pacing() -> None:
    media = [asset(UUID(int=index + 1000), f"asset-{index}.png") for index in range(9)]

    class PagedImmich:
        page_size: int | None = None
        start_page: int | None = None

        async def iter_asset_pages(
            self, *, page_size, updated_after, updated_before, start_page
        ):
            assert updated_after is None
            assert updated_before is None
            self.page_size = page_size
            self.start_page = start_page
            page_items = [media[:4], media[4:8], media[8:]]
            for page_number, items in enumerate(page_items, start=1):
                yield page_number, ImmichAssetSearchPage.model_validate(
                    {
                        "count": len(items),
                        "total": len(media),
                        "items": items,
                        "nextPage": str(page_number + 1) if page_number < 3 else None,
                    }
                )

    immich = PagedImmich()
    assets = FakeAssetRepository()
    syncs = FakeSyncRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        syncs,  # type: ignore[arg-type]
        Settings(sync_full_batch_size=2, sync_media_page_size=1000),
    )
    paced: list[int] = []

    async def pace(_run):
        paced.append(1)

    service._pace_full_page = pace  # type: ignore[method-assign]
    counters = asset_counters()

    await service._sync_assets(
        run_status().model_copy(update={"phase": "assets"}),
        OWNER_ID,
        counters,
        len(media),
    )

    assert immich.page_size == 1000
    assert immich.start_page == 1
    assert len(assets.assets) == len(media)
    assert assets.asset_batch_sizes == [2, 2, 2, 2, 1]
    assert assets.calls.count("assets") == 5
    assert paced == [1, 1]
    assert [cursor for phase, cursor in syncs.checkpoints if phase == "assets"] == [
        "assets:1:1",
        "assets:1:2",
        "assets:2:1",
        "assets:2:2",
        "assets:3:1",
    ]
    assert syncs.checkpoints[-1] == ("stacks", None)


@pytest.mark.asyncio
async def test_media_sync_resumes_inside_large_api_page() -> None:
    media = [asset(UUID(int=index + 2000), f"resume-{index}.png") for index in range(5)]

    class ResumeImmich:
        start_page: int | None = None

        async def iter_asset_pages(
            self, *, page_size, updated_after, updated_before, start_page
        ):
            assert page_size == 1000
            assert updated_after is None
            assert updated_before is None
            self.start_page = start_page
            yield 2, ImmichAssetSearchPage.model_validate(
                {
                    "count": 4,
                    "total": 5,
                    "items": media[:4],
                    "nextPage": "3",
                }
            )
            yield 3, ImmichAssetSearchPage.model_validate(
                {
                    "count": 1,
                    "total": 5,
                    "items": media[4:],
                    "nextPage": None,
                }
            )

    immich = ResumeImmich()
    assets = FakeAssetRepository()
    syncs = FakeSyncRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        syncs,  # type: ignore[arg-type]
        Settings(sync_full_batch_size=2, sync_media_page_size=1000),
    )
    counters = asset_counters()
    counters["assets_seen"] = 2
    counters["assets_created"] = 2

    await service._sync_assets(
        run_status().model_copy(update={"phase": "assets", "cursor": "assets:2:1"}),
        OWNER_ID,
        counters,
        len(media),
    )

    assert immich.start_page == 2
    assert [current.id for current in assets.assets] == [
        media[2].id,
        media[3].id,
        media[4].id,
    ]
    assert assets.asset_batch_sizes == [2, 1]
    assert counters["assets_seen"] == 5
    assert syncs.checkpoints[-1] == ("stacks", None)


@pytest.mark.asyncio
async def test_relationship_sync_uses_large_pages_and_skips_final_page_pacing() -> None:
    class RelationshipImmich:
        album_page_size: int | None = None
        tag_page_size: int | None = None

        async def iter_album_asset_ids(self, _album_id, *, page_size, start_page):
            assert start_page == 1
            self.album_page_size = page_size
            yield [ASSET_ONE]
            yield [ASSET_TWO]
            yield [ASSET_ONE, ASSET_TWO]

        async def iter_tag_asset_ids(self, _tag_id, *, page_size, start_page):
            assert start_page == 1
            self.tag_page_size = page_size
            yield [ASSET_ONE]
            yield [ASSET_TWO]

    immich = RelationshipImmich()
    assets = FakeAssetRepository()
    syncs = FakeSyncRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        syncs,  # type: ignore[arg-type]
        Settings(sync_full_batch_size=25, sync_relationship_page_size=1000),
    )
    paced: list[int] = []

    async def pace(_run, _started):
        paced.append(1)

    service._pace_full_batch = pace  # type: ignore[method-assign]
    album = ImmichAlbum(
        id=ALBUM_ID,
        albumName="Large album",
        createdAt="2026-08-24T12:00:00Z",
        updatedAt="2026-08-24T12:00:00Z",
    )
    tag = ImmichTag(id=TAG_ID, name="Large tag", value="Large tag", assetCount=2)
    counters = relationship_counters()

    await service._sync_relationships(
        run_status().model_copy(update={"phase": "relationships"}),
        OWNER_ID,
        [album],
        [tag],
        counters,
    )

    assert immich.album_page_size == 1000
    assert immich.tag_page_size == 1000
    assert paced == [1, 1, 1]
    assert counters["album_memberships"] == 4
    assert counters["tag_memberships"] == 2
    assert counters["tag_relationships_scanned"] == 1
    assert counters["tag_empty_relationships"] == 0
    assert syncs.checkpoints[-1] == ("relationships", None)


@pytest.mark.asyncio
async def test_tag_relationships_skip_empty_tags_and_run_eight_searches_concurrently() -> None:
    class ConcurrentTagImmich:
        def __init__(self) -> None:
            self.active = 0
            self.maximum_active = 0
            self.calls: list[UUID] = []

        async def iter_tag_asset_ids(self, tag_id, *, page_size, start_page):
            assert page_size == 1000
            assert start_page == 1
            self.calls.append(tag_id)
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            await asyncio.sleep(0)
            yield [] if tag_id == tag_ids[0] else [ASSET_ONE]
            self.active -= 1

    tag_ids = [
        UUID(f"{index:08x}-0000-4000-8000-000000000000")
        for index in range(1, 7)
    ]
    tags = [
        ImmichTag(
            id=tag_id,
            name=f"Tag {index}",
            value=f"Tag {index}",
            assetCount=0 if index == 0 else 1,
        )
        for index, tag_id in enumerate(tag_ids)
    ]
    immich = ConcurrentTagImmich()
    assets = FakeAssetRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSyncRepository(),  # type: ignore[arg-type]
        Settings(sync_relationship_page_size=1000),
    )
    counters = relationship_counters()

    await service._sync_relationships(
        run_status().model_copy(update={"phase": "relationships"}),
        OWNER_ID,
        [],
        tags,
        counters,
    )

    assert set(immich.calls) == set(tag_ids)
    assert immich.maximum_active == 6
    assert counters["tag_memberships"] == 5
    assert counters["tag_relationships_scanned"] == 6
    assert counters["tag_empty_relationships"] == 1
    assert assets.calls.count("tag_memberships") == 5


@pytest.mark.asyncio
async def test_targeted_relation_repair_replaces_snapshot_only_after_full_traversal() -> None:
    members = [asset(ASSET_ONE, "primary.png")]
    stack = ImmichStack(
        id=STACK_ID,
        primaryAssetId=ASSET_ONE,
        assets=[stack_asset(ASSET_ONE, "primary.png")],
    )
    immich = FakeImmich(members, stack)
    assets = FakeAssetRepository()
    service = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSyncRepository(),  # type: ignore[arg-type]
        Settings(sync_batch_size=25),
    )

    counters = await service._repair_relations_now([("album", ALBUM_ID), ("tag", TAG_ID)])

    assert counters == {"albums": 1, "tags": 1, "memberships": 2}
    assert assets.calls[-2:] == ["replace_album", "replace_tag"]


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

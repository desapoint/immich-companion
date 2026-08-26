"""Staged sync ordering, enrichment, and checkpoint coverage."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion.asset_service import AssetSyncService
from companion.config import Settings
from companion.immich import ImmichAlbum, ImmichAsset, ImmichStack, ImmichTag
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
            )
        ]

    async def iter_assets(self, **_kwargs):
        self.calls.append("assets")
        for current in self.assets:
            yield current

    async def list_stacks(self) -> list[ImmichStack]:
        self.calls.append("stacks")
        return [self.stack]

    async def iter_album_asset_ids(self, _album_id: UUID, **_kwargs):
        self.calls.append("album_memberships")
        yield [ASSET_ONE]

    async def count_album_asset_ids(self, _album_id: UUID) -> int:
        return 1

    async def iter_tag_asset_ids(self, _tag_id: UUID, **_kwargs):
        self.calls.append("tag_memberships")
        yield [ASSET_ONE]

    async def count_tag_asset_ids(self, _tag_id: UUID) -> int:
        return 1


class FakeAssetRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.assets: list[ImmichAsset] = []
        self.stack_payloads: list[tuple[dict[str, object], list[UUID]]] = []

    async def upsert_album_catalog(self, albums, _generation):
        self.calls.append("album_catalog")
        return len(albums), 0

    async def upsert_tag_catalog(self, tags, _generation):
        self.calls.append("tag_catalog")
        return len(tags), 0

    async def upsert_asset_batch(self, assets, _generation):
        self.calls.append("assets")
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

    async def finalize_generation(self, _generation, *, remove_assets, batch_size):
        self.calls.append("finalize")
        assert remove_assets is True
        assert batch_size == 25
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


@pytest.mark.asyncio
async def test_global_sync_orders_catalogs_before_media_and_relations_after() -> None:
    members = [asset(ASSET_ONE, "primary.png"), asset(ASSET_TWO, "child.png")]
    stack = ImmichStack(id=STACK_ID, primaryAssetId=ASSET_ONE, assets=members)
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
    assert any(item.total == 2 and item.percent is not None for item in relationship_progress)

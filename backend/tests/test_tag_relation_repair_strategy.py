"""Regression coverage for fast tag relation repair and sync coverage decisions."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.asset_service import AssetSyncService
from companion.config import Settings
from companion.immich import ImmichAsset, ImmichTag

TAG_ID = UUID("77777777-7777-4777-8777-777777777777")
OTHER_TAG_ID = UUID("88888888-8888-4888-8888-888888888888")
ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")


def asset(asset_id: UUID, *, include_tags: bool = True) -> ImmichAsset:
    payload = {
        "id": str(asset_id),
        "type": "IMAGE",
        "originalFileName": f"{asset_id}.jpg",
        "fileCreatedAt": "2026-09-09T12:00:00Z",
        "fileModifiedAt": "2026-09-09T12:00:00Z",
    }
    if include_tags:
        payload["tags"] = [{"id": str(TAG_ID)}, {"id": str(OTHER_TAG_ID)}]
    return ImmichAsset.model_validate(payload)


def tag(tag_id: UUID = TAG_ID) -> ImmichTag:
    return ImmichTag(id=tag_id, name="test", value="test")


class FakeImmich:
    def __init__(self) -> None:
        self.details: dict[UUID, ImmichAsset] = {
            ASSET_ONE: asset(ASSET_ONE),
            ASSET_TWO: asset(ASSET_TWO),
        }
        self.detail_calls: list[UUID] = []
        self.tag_page_calls = 0

    async def get_asset(self, asset_id: UUID):
        self.detail_calls.append(asset_id)
        return self.details.get(asset_id, asset(asset_id))

    async def list_tag_catalog(self):
        return [tag()]

    async def iter_tag_asset_ids(self, _tag_id: UUID, **_kwargs):
        self.tag_page_calls += 1
        yield [ASSET_ONE]


class FakeAssets:
    def __init__(self) -> None:
        self.asset_tag_repairs: list[tuple[UUID, list[UUID]]] = []
        self.tag_repairs = 0

    async def replace_asset_tag_memberships(self, asset_id: UUID, tag_ids: list[UUID]):
        self.asset_tag_repairs.append((asset_id, tag_ids))

    async def upsert_tag_catalog(self, _tags, _generation):
        return 1, 0

    async def replace_tag_memberships(self, _tag_id: UUID, _asset_ids: list[UUID]):
        self.tag_repairs += 1
        return 1


class FakeSyncRepository:
    pass


def service() -> tuple[AssetSyncService, FakeImmich, FakeAssets]:
    immich = FakeImmich()
    assets = FakeAssets()
    instance = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSyncRepository(),  # type: ignore[arg-type]
        Settings(),
    )
    return instance, immich, assets


async def set_active_sync(
    instance: AssetSyncService,
    phase: str,
    cursor: str | None,
    *,
    mode: str = "full",
) -> None:
    async def status():
        return SimpleNamespace(active=SimpleNamespace(phase=phase, cursor=cursor, mode=mode))

    instance.status = status  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_small_tag_change_uses_asset_detail_payloads_without_relation_scan() -> None:
    instance, immich, assets = service()

    await instance.reconcile_targets(
        [ASSET_ONE, ASSET_TWO],
        relations=[("tag", TAG_ID)],
    )

    assert immich.detail_calls == [ASSET_ONE, ASSET_TWO]
    assert immich.tag_page_calls == 0
    assert assets.asset_tag_repairs == [
        (ASSET_ONE, [TAG_ID, OTHER_TAG_ID]),
        (ASSET_TWO, [TAG_ID, OTHER_TAG_ID]),
    ]
    assert assets.tag_repairs == 0


@pytest.mark.asyncio
async def test_missing_tags_payload_falls_back_to_authoritative_relation_scan() -> None:
    instance, immich, assets = service()
    immich.details[ASSET_ONE] = asset(ASSET_ONE, include_tags=False)

    await instance.reconcile_targets(
        [ASSET_ONE],
        relations=[("tag", TAG_ID)],
    )

    assert immich.detail_calls == [ASSET_ONE]
    assert immich.tag_page_calls == 1
    assert assets.asset_tag_repairs == []
    assert assets.tag_repairs == 1


@pytest.mark.asyncio
async def test_large_tag_change_does_not_launch_per_asset_detail_burst() -> None:
    instance, immich, assets = service()
    many_assets = [UUID(int=index + 1) for index in range(Settings().sync_full_batch_size + 1)]

    await instance.reconcile_targets(
        many_assets,
        relations=[("tag", TAG_ID)],
    )

    assert immich.detail_calls == []
    assert immich.tag_page_calls == 1
    assert assets.tag_repairs == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["catalogs", "assets", "stacks"])
async def test_full_tag_reconciliation_is_covered_before_relationship_stage(phase: str) -> None:
    instance, _, _ = service()
    await set_active_sync(instance, phase, None, mode="full")

    assert await instance.tag_reconciliation_will_cover([TAG_ID]) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["catalogs", "assets", "stacks"])
async def test_incremental_tag_sync_is_not_assumed_to_cover_new_mutation(phase: str) -> None:
    instance, _, _ = service()
    await set_active_sync(instance, phase, None, mode="incremental")

    assert await instance.tag_reconciliation_will_cover([TAG_ID]) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", [None, "albums:1:1", "tags:10:0"])
async def test_relationship_stage_is_not_assumed_to_cover_tag_change(cursor: str | None) -> None:
    instance, _, _ = service()
    await set_active_sync(instance, "relationships", cursor, mode="full")

    assert await instance.tag_reconciliation_will_cover([TAG_ID]) is False

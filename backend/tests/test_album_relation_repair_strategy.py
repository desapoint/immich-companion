"""Regression coverage for adaptive album relation repair selection."""

from uuid import UUID

import pytest

from companion.asset_service import ALBUM_MEMBERSHIP_PAGE_SIZE, AssetSyncService
from companion.config import Settings
from companion.immich import ImmichAlbum

ALBUM_ID = UUID("44444444-4444-4444-8444-444444444444")
ASSET_IDS = [
    UUID("11111111-1111-4111-8111-111111111111"),
    UUID("22222222-2222-4222-8222-222222222222"),
    UUID("33333333-3333-4333-8333-333333333333"),
]


def album(asset_count: int) -> ImmichAlbum:
    return ImmichAlbum(
        id=ALBUM_ID,
        albumName="Test album",
        assetCount=asset_count,
        createdAt="2026-09-09T12:00:00Z",
        updatedAt="2026-09-09T12:00:00Z",
    )


class FakeImmich:
    def __init__(self, asset_count: int) -> None:
        self.current_album = album(asset_count)
        self.catalog_calls = 0
        self.asset_album_calls: list[UUID] = []
        self.album_page_calls = 0

    async def list_album_catalog(self):
        self.catalog_calls += 1
        return [self.current_album]

    async def list_albums_for_asset(self, asset_id: UUID):
        self.asset_album_calls.append(asset_id)
        return [self.current_album]

    async def iter_album_asset_ids(self, _album_id: UUID, **_kwargs):
        page_count = max(
            1,
            (self.current_album.asset_count + ALBUM_MEMBERSHIP_PAGE_SIZE - 1)
            // ALBUM_MEMBERSHIP_PAGE_SIZE,
        )
        for _ in range(page_count):
            self.album_page_calls += 1
            yield []


class FakeAssets:
    def __init__(self) -> None:
        self.asset_repairs: list[UUID] = []
        self.album_repairs = 0
        self.catalog_upserts = 0

    async def upsert_album_catalog(self, albums, _generation):
        self.catalog_upserts += 1
        return len(albums), 0

    async def replace_asset_album_memberships(self, asset_id: UUID, _album_ids):
        self.asset_repairs.append(asset_id)

    async def replace_album_memberships(self, _album_id: UUID, _asset_ids):
        self.album_repairs += 1
        return 0


class FakeSyncRepository:
    pass


def service(asset_count: int) -> tuple[AssetSyncService, FakeImmich, FakeAssets]:
    immich = FakeImmich(asset_count)
    assets = FakeAssets()
    instance = AssetSyncService(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSyncRepository(),  # type: ignore[arg-type]
        Settings(),
    )
    return instance, immich, assets


@pytest.mark.asyncio
async def test_single_asset_uses_asset_oriented_repair_for_large_album() -> None:
    instance, immich, assets = service(16_569)

    await instance.reconcile_targets(
        [ASSET_IDS[0]],
        relations=[("album", ALBUM_ID)],
    )

    assert immich.asset_album_calls == [ASSET_IDS[0]]
    assert immich.album_page_calls == 0
    assert assets.asset_repairs == [ASSET_IDS[0]]
    assert assets.album_repairs == 0


@pytest.mark.asyncio
async def test_full_album_repair_wins_when_page_calls_are_strictly_lower() -> None:
    instance, immich, assets = service(1_500)

    await instance.reconcile_targets(
        ASSET_IDS,
        relations=[("album", ALBUM_ID)],
    )

    assert immich.asset_album_calls == []
    assert immich.album_page_calls == 2
    assert assets.asset_repairs == []
    assert assets.album_repairs == 1


@pytest.mark.asyncio
async def test_equal_call_count_favors_asset_oriented_repair() -> None:
    instance, immich, assets = service(2_000)

    await instance.reconcile_targets(
        ASSET_IDS[:2],
        relations=[("album", ALBUM_ID)],
    )

    assert immich.asset_album_calls == ASSET_IDS[:2]
    assert immich.album_page_calls == 0
    assert assets.asset_repairs == ASSET_IDS[:2]
    assert assets.album_repairs == 0

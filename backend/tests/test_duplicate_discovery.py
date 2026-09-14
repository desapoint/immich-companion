"""Tests for provider-neutral duplicate discovery snapshots."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion.discovery import ImmichDuplicateProvider
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset, ImmichDuplicateGroup

ASSET_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
LIBRARY_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
GROUP_1 = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
GROUP_2 = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime(2026, 8, 31, tzinfo=UTC)


def external_asset(*, size: int | None) -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(ASSET_ID),
            "libraryId": str(LIBRARY_ID),
            "type": "IMAGE",
            "originalFileName": "external.png",
            "originalPath": "library/external.png",
            "originalMimeType": "image/png",
            "fileCreatedAt": NOW.isoformat(),
            "fileModifiedAt": NOW.isoformat(),
            "exifInfo": {"fileSizeInByte": size} if size is not None else None,
        }
    )


class FakeImmich:
    def __init__(self) -> None:
        sparse = external_asset(size=None)
        self.groups = [
            ImmichDuplicateGroup(duplicate_id=GROUP_1, assets=[sparse]),
            ImmichDuplicateGroup(duplicate_id=GROUP_2, assets=[sparse]),
        ]
        self.detail = external_asset(size=123)
        self.detail_calls: list[UUID] = []

    async def list_duplicate_groups(self):
        return self.groups

    async def get_asset(self, asset_id: UUID):
        self.detail_calls.append(asset_id)
        return self.detail


@pytest.mark.asyncio
async def test_immich_provider_emits_stable_generic_groups_and_reuses_hydration() -> None:
    immich = FakeImmich()

    groups = await ImmichDuplicateProvider(immich).discover()  # type: ignore[arg-type]

    assert [group.group_id for group in groups] == [
        f"immich:{GROUP_1}",
        f"immich:{GROUP_2}",
    ]
    assert all(group.discovery_source is DiscoverySource.IMMICH_DUPLICATE for group in groups)
    assert [group.provider_group_id for group in groups] == [str(GROUP_1), str(GROUP_2)]
    assert all(group.provider_metadata == {"endpoint": "/api/duplicates"} for group in groups)
    assert all(group.assets[0].file_size_bytes == 123 for group in groups)
    assert immich.detail_calls == [ASSET_ID]


@pytest.mark.asyncio
async def test_immich_provider_uses_matching_synchronized_size_without_live_fetch() -> None:
    immich = FakeImmich()

    class Assets:
        requested = []

        async def get_immich_assets(self, asset_ids):
            self.requested.extend(asset_ids)
            return {ASSET_ID: external_asset(size=123)}

    assets = Assets()
    groups = await ImmichDuplicateProvider(immich, assets).discover()  # type: ignore[arg-type]

    assert assets.requested == [ASSET_ID]
    assert immich.detail_calls == []
    assert all(group.assets[0].file_size_bytes == 123 for group in groups)


@pytest.mark.asyncio
async def test_immich_provider_rechecks_asset_when_synchronized_source_is_stale() -> None:
    immich = FakeImmich()

    class Assets:
        async def get_immich_assets(self, _asset_ids):
            return {
                ASSET_ID: external_asset(size=999).model_copy(
                    update={"file_modified_at": datetime(2026, 9, 1, tzinfo=UTC)}
                )
            }

    groups = await ImmichDuplicateProvider(immich, Assets()).discover()  # type: ignore[arg-type]

    assert immich.detail_calls == [ASSET_ID]
    assert all(group.assets[0].file_size_bytes == 123 for group in groups)


@pytest.mark.asyncio
async def test_immich_provider_caps_missing_local_asset_fallbacks() -> None:
    class Immich:
        active = 0
        peak = 0
        calls = 0

        async def list_duplicate_groups(self):
            return [
                ImmichDuplicateGroup(
                    duplicate_id=UUID(int=100 + number),
                    assets=[external_asset(size=None).model_copy(update={"id": UUID(int=number)})],
                )
                for number in range(1, 41)
            ]

        async def get_asset(self, asset_id):
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.calls += 1
            try:
                await asyncio.sleep(0.001)
                return external_asset(size=123).model_copy(update={"id": asset_id})
            finally:
                self.active -= 1

    class Assets:
        async def get_immich_assets(self, _asset_ids):
            return {}

    immich = Immich()
    groups = await ImmichDuplicateProvider(immich, Assets()).discover()  # type: ignore[arg-type]

    assert len(groups) == 40
    assert immich.calls == 40
    assert immich.peak <= 2
    assert all(group.assets[0].file_size_bytes == 123 for group in groups)

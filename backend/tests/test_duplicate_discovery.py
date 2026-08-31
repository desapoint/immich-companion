"""Tests for provider-neutral duplicate discovery snapshots."""

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

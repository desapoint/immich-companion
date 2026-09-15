"""Tests for provider-neutral duplicate discovery snapshots."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion.discovery import ImmichDuplicateProvider
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.immich_duplicate_repository import ImmichDuplicateSnapshotGroup

ASSET_1 = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ASSET_2 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
LIBRARY_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
GROUP_1 = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime(2026, 9, 14, tzinfo=UTC)


def external_asset(asset_id: UUID, *, size: int = 123) -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(asset_id),
            "libraryId": str(LIBRARY_ID),
            "type": "IMAGE",
            "originalFileName": f"{asset_id}.png",
            "originalPath": f"library/{asset_id}.png",
            "originalMimeType": "image/png",
            "fileCreatedAt": NOW.isoformat(),
            "fileModifiedAt": NOW.isoformat(),
            "exifInfo": {"fileSizeInByte": size},
        }
    )


class Snapshots:
    async def groups(self):
        return [
            ImmichDuplicateSnapshotGroup(
                provider_group_id=str(GROUP_1),
                asset_ids=(ASSET_1, ASSET_2),
            )
        ]


class Assets:
    def __init__(self, *, missing: UUID | None = None) -> None:
        self.missing = missing
        self.requested: list[UUID] = []

    async def get_immich_assets(self, asset_ids):
        self.requested.extend(asset_ids)
        return {
            asset_id: external_asset(asset_id) for asset_id in asset_ids if asset_id != self.missing
        }


@pytest.mark.asyncio
async def test_immich_provider_reads_persisted_snapshot_and_local_assets() -> None:
    assets = Assets()

    groups = await ImmichDuplicateProvider(Snapshots(), assets).discover()

    assert assets.requested == [ASSET_1, ASSET_2]
    assert len(groups) == 1
    assert groups[0].group_id == f"immich:{GROUP_1}"
    assert groups[0].provider_group_id == str(GROUP_1)
    assert groups[0].discovery_source is DiscoverySource.IMMICH_DUPLICATE
    assert groups[0].provider_metadata == {
        "endpoint": "/api/duplicates",
        "source": "companion_database",
    }
    assert [asset.id for asset in groups[0].assets] == [ASSET_1, ASSET_2]


@pytest.mark.asyncio
async def test_immich_provider_skips_snapshot_group_with_missing_local_member() -> None:
    groups = await ImmichDuplicateProvider(Snapshots(), Assets(missing=ASSET_2)).discover()

    assert groups == []

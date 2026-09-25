"""Tests for provider-neutral duplicate discovery snapshots."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.discovery import ImmichDuplicateProvider
from companion.discovery.similarity_duplicates import _similarity_group_ids
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.immich_duplicate_repository import ImmichDuplicateSnapshotGroup
from companion.similarity_grouping import ValidatedSimilarityGroup

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
            asset_id: external_asset(asset_id)
            for asset_id in asset_ids
            if asset_id != self.missing
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



def _similarity_summary(scan_id: UUID = GROUP_1, *, config: str = "a" * 64):
    return SimpleNamespace(
        id=scan_id,
        parameters=SimpleNamespace(
            model_version="appearance-normalized-v1",
            feature_version=6,
            comparison_version=8,
            config_fingerprint=config,
            validation_mode="linked",
        ),
    )


def _validated_similarity(*asset_ids: UUID) -> ValidatedSimilarityGroup:
    return ValidatedSimilarityGroup(
        asset_ids=asset_ids,
        anchor_asset_id=asset_ids[0],
        validation_mode="linked",
        minimum_similarity_percent=96.0,
        maximum_similarity_percent=99.0,
        pair_count=max(1, len(asset_ids) - 1),
        admission_evidence=(),
    )


def test_similarity_group_ids_are_always_compact_and_do_not_embed_members() -> None:
    members = (
        ASSET_1,
        ASSET_2,
        UUID("11111111-1111-4111-8111-111111111111"),
        UUID("22222222-2222-4222-8222-222222222222"),
        UUID("33333333-3333-4333-8333-333333333333"),
        UUID("44444444-4444-4444-8444-444444444444"),
        UUID("55555555-5555-4555-8555-555555555555"),
    )

    pair_id, pair_provider_id = _similarity_group_ids(
        _similarity_summary(),
        _validated_similarity(*members[:2]),
    )
    group_id, provider_id = _similarity_group_ids(
        _similarity_summary(),
        _validated_similarity(*members),
    )

    for value in (pair_id, group_id):
        assert value.startswith("companion:sha256:")
        assert len(value) == len("companion:sha256:") + 64
        assert all(str(member) not in value for member in members)
    for value in (pair_provider_id, provider_id):
        assert len(value) < 160
        assert all(str(member) not in value for member in members)


def test_similarity_group_id_is_scan_independent_but_provider_id_tracks_scan() -> None:
    validated = _validated_similarity(ASSET_1, ASSET_2)
    first_group_id, first_provider_id = _similarity_group_ids(
        _similarity_summary(GROUP_1),
        validated,
    )
    second_scan = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    second_group_id, second_provider_id = _similarity_group_ids(
        _similarity_summary(second_scan),
        validated,
    )

    assert first_group_id == second_group_id
    assert first_provider_id != second_provider_id


def test_similarity_group_id_changes_when_identity_inputs_change() -> None:
    validated = _validated_similarity(ASSET_1, ASSET_2)
    first_group_id, _ = _similarity_group_ids(_similarity_summary(config="a" * 64), validated)
    second_group_id, _ = _similarity_group_ids(_similarity_summary(config="b" * 64), validated)

    assert first_group_id != second_group_id

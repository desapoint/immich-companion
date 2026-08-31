"""Companion similarity scan discovery publication regressions."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion.discovery import (
    CompositeGroupDiscoveryProvider,
    DiscoveredGroup,
    SimilarityDuplicateProvider,
)
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_repository import PairSimilarityEvidence
from companion.similarity_scan_repository import (
    SimilarityScanPair,
    SimilarityScanParameters,
    SimilarityScanSnapshot,
)

LOW = UUID("11111111-1111-4111-8111-111111111111")
HIGH = UUID("22222222-2222-4222-8222-222222222222")
THIRD = UUID("33333333-3333-4333-8333-333333333333")
SCAN_ONE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SCAN_TWO = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
NOW = datetime(2026, 8, 31, tzinfo=UTC)


def asset(identifier: UUID) -> ImmichAsset:
    return ImmichAsset(
        id=identifier,
        asset_type="IMAGE",
        original_file_name=f"{identifier}.jpg",
        original_mime_type="image/jpeg",
        file_created_at=NOW,
        file_modified_at=NOW,
        exif_info={"fileSizeInByte": 123},
    )


def scan_pair(
    low: UUID = LOW,
    high: UUID = HIGH,
    score: float = 98.5,
) -> SimilarityScanPair:
    return SimilarityScanPair(
        asset_id_low=low,
        asset_id_high=high,
        asset_low_source_sha256="a" * 64,
        asset_high_source_sha256="b" * 64,
        evidence=PairSimilarityEvidence(
            similarity_percent=score,
            structural_percent=98,
            perceptual_percent=99,
            color_percent=97,
            exact_thumbnail_match=False,
            exact_pixel_match=False,
            model_version="companion-image-v1",
            feature_version=1,
            comparison_version=1,
        ),
    )


def snapshot(
    scan_id: UUID,
    pairs: tuple[SimilarityScanPair, ...] | None = None,
) -> SimilarityScanSnapshot:
    current_pairs = pairs or (scan_pair(),)
    return SimilarityScanSnapshot(
        id=scan_id,
        parameters=SimilarityScanParameters(
            model_version="companion-image-v1",
            feature_version=1,
            comparison_version=1,
            scope="all_eligible_assets",
            similarity_threshold=95,
            maximum_perceptual_distance=12,
            maximum_aspect_difference=0.05,
            maximum_neighbors_per_asset=8,
            maximum_matches=5000,
        ),
        asset_count=len(
            {
                asset_id
                for pair in current_pairs
                for asset_id in (pair.asset_id_low, pair.asset_id_high)
            }
        ),
        candidate_count=len(current_pairs),
        completed_at=NOW,
        pairs=current_pairs,
    )


class FakeScans:
    def __init__(self, value: SimilarityScanSnapshot | None) -> None:
        self.value = value

    async def latest_completed(self) -> SimilarityScanSnapshot | None:
        return self.value


class FakeAssets:
    def __init__(self, values: dict[UUID, ImmichAsset]) -> None:
        self.values = values
        self.requested: list[UUID] = []

    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]:
        self.requested = asset_ids
        return self.values


@pytest.mark.asyncio
async def test_similarity_provider_publishes_latest_pair_with_scan_provenance() -> None:
    assets = FakeAssets({LOW: asset(LOW), HIGH: asset(HIGH)})
    provider = SimilarityDuplicateProvider(FakeScans(snapshot(SCAN_ONE)), assets)

    groups = await provider.discover()

    assert len(groups) == 1
    assert groups[0].discovery_source is DiscoverySource.COMPANION_SIMILARITY
    assert groups[0].assets[0].id == LOW
    assert groups[0].provider_metadata["scan_id"] == str(SCAN_ONE)
    assert groups[0].provider_metadata["similarity_percent"] == "98.5"
    assert assets.requested == [LOW, HIGH]


@pytest.mark.asyncio
async def test_similarity_group_id_remains_stable_across_equivalent_scans() -> None:
    assets = FakeAssets({LOW: asset(LOW), HIGH: asset(HIGH)})
    first = SimilarityDuplicateProvider(FakeScans(snapshot(SCAN_ONE)), assets)
    second = SimilarityDuplicateProvider(FakeScans(snapshot(SCAN_TWO)), assets)

    first_group = (await first.discover())[0]
    second_group = (await second.discover())[0]

    assert first_group.group_id == second_group.group_id
    assert first_group.provider_group_id != second_group.provider_group_id


@pytest.mark.asyncio
async def test_similarity_provider_skips_pairs_with_unsynchronized_members() -> None:
    provider = SimilarityDuplicateProvider(
        FakeScans(snapshot(SCAN_ONE)),
        FakeAssets({LOW: asset(LOW)}),
    )

    assert await provider.discover() == []


@pytest.mark.asyncio
async def test_similarity_provider_publishes_fully_cohesive_triangle() -> None:
    current = snapshot(
        SCAN_ONE,
        (
            scan_pair(LOW, HIGH, 99),
            scan_pair(LOW, THIRD, 97),
            scan_pair(HIGH, THIRD, 96),
        ),
    )
    provider = SimilarityDuplicateProvider(
        FakeScans(current),
        FakeAssets({LOW: asset(LOW), HIGH: asset(HIGH), THIRD: asset(THIRD)}),
    )

    groups = await provider.discover()

    assert len(groups) == 1
    assert tuple(member.id for member in groups[0].assets) == (LOW, HIGH, THIRD)
    assert groups[0].provider_metadata["minimum_similarity_percent"] == "96"
    assert groups[0].provider_metadata["maximum_similarity_percent"] == "99"
    assert groups[0].provider_metadata["cohesive_pair_count"] == "3"


@pytest.mark.asyncio
async def test_similarity_provider_does_not_collapse_non_transitive_chain() -> None:
    current = snapshot(
        SCAN_ONE,
        (scan_pair(LOW, HIGH, 98), scan_pair(HIGH, THIRD, 97)),
    )
    provider = SimilarityDuplicateProvider(
        FakeScans(current),
        FakeAssets({LOW: asset(LOW), HIGH: asset(HIGH), THIRD: asset(THIRD)}),
    )

    groups = await provider.discover()

    assert [tuple(member.id for member in group.assets) for group in groups] == [
        (LOW, HIGH),
        (HIGH, THIRD),
    ]


@pytest.mark.asyncio
async def test_composite_provider_keeps_registration_order_and_rejects_collisions() -> None:
    first_group = DiscoveredGroup(
        group_id="first",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="one",
        assets=(),
    )
    second_group = DiscoveredGroup(
        group_id="second",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id="two",
        assets=(),
    )

    class Provider:
        def __init__(self, groups: list[DiscoveredGroup]) -> None:
            self.groups = groups

        async def discover(self) -> list[DiscoveredGroup]:
            return self.groups

    composite = CompositeGroupDiscoveryProvider(Provider([first_group]), Provider([second_group]))
    assert [group.group_id for group in await composite.discover()] == ["first", "second"]

    collision = CompositeGroupDiscoveryProvider(Provider([first_group]), Provider([first_group]))
    with pytest.raises(ValueError, match="Duplicate discovery group ID"):
        await collision.discover()

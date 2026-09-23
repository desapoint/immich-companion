"""Companion similarity scan discovery publication regressions."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import pytest

from companion.discovery import (
    CompositeGroupDiscoveryProvider,
    DiscoveredGroup,
    SimilarityDuplicateProvider,
)
from companion.discovery.similarity_duplicates import _similarity_group_ids
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_grouping import SimilarityGroupingEdge, ValidatedSimilarityGroup
from companion.similarity_repository import PairSimilarityEvidence
from companion.similarity_scan_repository import (
    SimilarityScanPair,
    SimilarityScanParameters,
    SimilarityScanRunSummary,
    SimilarityScanSnapshot,
)

LOW = UUID("11111111-1111-4111-8111-111111111111")
HIGH = UUID("22222222-2222-4222-8222-222222222222")
THIRD = UUID("33333333-3333-4333-8333-333333333333")
FOURTH = UUID("44444444-4444-4444-8444-444444444444")
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
    *,
    validation_mode: Literal["reference", "linked", "strict"] = "strict",
    max_link_depth: int = 2,
    anchor_asset_id: UUID | None = None,
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
            validation_mode=validation_mode,
            max_link_depth=max_link_depth,
            anchor_asset_id=anchor_asset_id,
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
        self.edge_batches = 0

    async def latest_completed_summary(self) -> SimilarityScanRunSummary | None:
        if self.value is None:
            return None
        return SimilarityScanRunSummary(
            id=self.value.id,
            parameters=self.value.parameters,
            asset_count=self.value.asset_count,
            candidate_count=self.value.candidate_count,
            match_count=len(self.value.pairs),
            result_limit_reached=False,
            completed_at=self.value.completed_at,
        )

    async def iter_grouping_edges(self, scan_id: UUID, *, batch_size: int = 1_000):
        assert self.value is not None
        assert scan_id == self.value.id
        del batch_size
        for pair in self.value.pairs:
            self.edge_batches += 1
            yield [
                SimilarityGroupingEdge(
                    asset_id_low=pair.asset_id_low,
                    asset_id_high=pair.asset_id_high,
                    similarity_percent=pair.evidence.similarity_percent,
                )
            ]


class FakeAssets:
    def __init__(self, values: dict[UUID, ImmichAsset]) -> None:
        self.values = values
        self.requested: list[UUID] = []
        self.calls: list[list[UUID]] = []

    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]:
        self.requested = asset_ids
        self.calls.append(asset_ids)
        return {
            asset_id: self.values[asset_id]
            for asset_id in asset_ids
            if asset_id in self.values
        }


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
    assert groups[0].provider_metadata["max_link_depth"] == "2"
    assert assets.requested == [LOW, HIGH]


@pytest.mark.asyncio
async def test_similarity_provider_ignores_pruned_pair_generation() -> None:
    current = snapshot(SCAN_ONE)

    class PrunedScans(FakeScans):
        async def latest_completed_summary(self) -> SimilarityScanRunSummary | None:
            summary = await super().latest_completed_summary()
            assert summary is not None
            return SimilarityScanRunSummary(
                id=summary.id,
                parameters=summary.parameters,
                asset_count=summary.asset_count,
                candidate_count=summary.candidate_count,
                match_count=summary.match_count,
                result_limit_reached=summary.result_limit_reached,
                completed_at=summary.completed_at,
                pair_evidence_pruned_at=NOW,
            )

    scans = PrunedScans(current)
    groups = await SimilarityDuplicateProvider(
        scans,
        FakeAssets({LOW: asset(LOW), HIGH: asset(HIGH)}),
    ).discover()

    assert groups == []
    assert scans.edge_batches == 0


@pytest.mark.asyncio
async def test_similarity_group_id_remains_stable_across_equivalent_scans() -> None:
    assets = FakeAssets({LOW: asset(LOW), HIGH: asset(HIGH)})
    first = SimilarityDuplicateProvider(FakeScans(snapshot(SCAN_ONE)), assets)
    second = SimilarityDuplicateProvider(FakeScans(snapshot(SCAN_TWO)), assets)

    first_group = (await first.discover())[0]
    second_group = (await second.discover())[0]

    assert first_group.group_id == second_group.group_id
    assert first_group.provider_group_id != second_group.provider_group_id


def test_similarity_small_group_ids_keep_legacy_shape() -> None:
    current = snapshot(SCAN_ONE)
    summary = SimilarityScanRunSummary(
        id=current.id,
        parameters=current.parameters,
        asset_count=current.asset_count,
        candidate_count=current.candidate_count,
        match_count=len(current.pairs),
        result_limit_reached=False,
        completed_at=current.completed_at,
    )
    validated = ValidatedSimilarityGroup(
        asset_ids=(LOW, HIGH),
        anchor_asset_id=LOW,
        validation_mode="strict",
        minimum_similarity_percent=98.5,
        maximum_similarity_percent=98.5,
        pair_count=1,
        admission_evidence=(),
    )

    group_id, provider_group_id = _similarity_group_ids(summary, validated)

    member_key = f"{LOW}:{HIGH}"
    version_key = (
        "companion-image-v1:1:1:"
        f"{current.parameters.config_fingerprint[:12]}:strict:"
    )
    assert group_id == f"companion:{version_key}{member_key}"
    assert provider_group_id == f"{SCAN_ONE}:{member_key}"


def test_similarity_group_ids_stay_bounded_for_very_large_groups() -> None:
    current = snapshot(SCAN_ONE)
    summary = SimilarityScanRunSummary(
        id=current.id,
        parameters=current.parameters,
        asset_count=current.asset_count,
        candidate_count=current.candidate_count,
        match_count=len(current.pairs),
        result_limit_reached=False,
        completed_at=current.completed_at,
    )
    asset_ids = tuple(UUID(int=index + 1) for index in range(5_000))
    validated = ValidatedSimilarityGroup(
        asset_ids=asset_ids,
        anchor_asset_id=asset_ids[0],
        validation_mode="linked",
        minimum_similarity_percent=95,
        maximum_similarity_percent=100,
        pair_count=len(asset_ids) - 1,
        admission_evidence=(),
    )

    group_id, provider_group_id = _similarity_group_ids(summary, validated)

    assert len(group_id.encode()) < 128
    assert len(provider_group_id.encode()) < 160
    assert group_id == _similarity_group_ids(summary, validated)[0]

    reversed_group = ValidatedSimilarityGroup(
        asset_ids=tuple(reversed(asset_ids)),
        anchor_asset_id=asset_ids[0],
        validation_mode="linked",
        minimum_similarity_percent=95,
        maximum_similarity_percent=100,
        pair_count=len(asset_ids) - 1,
        admission_evidence=(),
    )
    assert _similarity_group_ids(summary, reversed_group)[0] == group_id


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
    assert groups[0].provider_metadata["validation_mode"] == "strict"
    assert groups[0].similarity_validation is not None
    assert groups[0].similarity_validation.anchor_asset_id == LOW
    assert groups[0].similarity_validation.admission_evidence[2].admitted_by_asset_id == LOW


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
async def test_similarity_provider_applies_persisted_link_depth_limit() -> None:
    current = snapshot(
        SCAN_ONE,
        (
            scan_pair(LOW, HIGH, 99),
            scan_pair(HIGH, THIRD, 98),
            scan_pair(THIRD, FOURTH, 97),
        ),
        validation_mode="linked",
        max_link_depth=1,
        anchor_asset_id=LOW,
    )
    provider = SimilarityDuplicateProvider(
        FakeScans(current),
        FakeAssets({
            LOW: asset(LOW),
            HIGH: asset(HIGH),
            THIRD: asset(THIRD),
            FOURTH: asset(FOURTH),
        }),
    )

    group = (await provider.discover())[0]

    assert tuple(member.id for member in group.assets) == (LOW, HIGH, THIRD)
    assert group.provider_metadata["max_link_depth"] == "1"
    assert group.similarity_validation is not None
    evidence = {
        item.asset_id: item
        for item in group.similarity_validation.admission_evidence
    }
    assert evidence[HIGH].link_depth == 0
    assert evidence[THIRD].link_depth == 1
    assert FOURTH not in evidence


@pytest.mark.asyncio
async def test_similarity_provider_hydrates_validated_groups_in_batches() -> None:
    current = snapshot(
        SCAN_ONE,
        (
            scan_pair(LOW, HIGH, 99),
            scan_pair(THIRD, FOURTH, 98),
        ),
    )
    assets = FakeAssets(
        {
            LOW: asset(LOW),
            HIGH: asset(HIGH),
            THIRD: asset(THIRD),
            FOURTH: asset(FOURTH),
        }
    )
    scans = FakeScans(current)
    provider = SimilarityDuplicateProvider(scans, assets)

    batches = [
        batch
        async for batch in provider.discover_batches(batch_size=1)
    ]

    assert [[member.id for member in batch[0].assets] for batch in batches] == [
        [LOW, HIGH],
        [THIRD, FOURTH],
    ]
    assert assets.calls == [[LOW, HIGH], [THIRD, FOURTH]]
    assert scans.edge_batches == 2


@pytest.mark.asyncio
async def test_similarity_provider_bounds_asset_hydration_by_unique_member_budget(
    monkeypatch,
) -> None:
    import companion.discovery.similarity_duplicates as similarity_duplicates

    monkeypatch.setattr(
        similarity_duplicates,
        "SIMILARITY_GROUP_HYDRATION_ASSET_BUDGET",
        2,
    )
    current = snapshot(
        SCAN_ONE,
        (
            scan_pair(LOW, HIGH, 99),
            scan_pair(THIRD, FOURTH, 98),
        ),
    )
    assets = FakeAssets(
        {
            LOW: asset(LOW),
            HIGH: asset(HIGH),
            THIRD: asset(THIRD),
            FOURTH: asset(FOURTH),
        }
    )
    provider = SimilarityDuplicateProvider(FakeScans(current), assets)

    batches = [
        batch
        async for batch in provider.discover_batches(batch_size=10)
    ]

    assert len(batches) == 2
    assert assets.calls == [[LOW, HIGH], [THIRD, FOURTH]]


@pytest.mark.asyncio
async def test_similarity_provider_places_explicit_revalidation_anchor_first() -> None:
    current = snapshot(
        SCAN_ONE,
        (scan_pair(LOW, HIGH, 98), scan_pair(HIGH, THIRD, 97)),
        validation_mode="linked",
        anchor_asset_id=THIRD,
    )
    provider = SimilarityDuplicateProvider(
        FakeScans(current),
        FakeAssets({LOW: asset(LOW), HIGH: asset(HIGH), THIRD: asset(THIRD)}),
    )

    group = (await provider.discover())[0]

    assert tuple(member.id for member in group.assets) == (THIRD, LOW, HIGH)
    assert group.similarity_validation is not None
    assert group.similarity_validation.anchor_asset_id == THIRD


@pytest.mark.asyncio
async def test_composite_provider_keeps_registration_order_and_rejects_collisions() -> None:
    first_group = DiscoveredGroup(
        group_id="first",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="one",
        assets=(asset(LOW), asset(HIGH)),
    )
    second_group = DiscoveredGroup(
        group_id="second",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id="two",
        assets=(asset(HIGH), asset(THIRD)),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_composite_provider_coalesces_only_exact_cross_provider_member_sets(
    reverse: bool,
) -> None:
    immich = DiscoveredGroup(
        group_id="immich-group",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id="immich-provider-id",
        assets=(asset(HIGH), asset(LOW)),
        provider_metadata={"endpoint": "/api/duplicates"},
    )
    similar = DiscoveredGroup(
        group_id="similar-group",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id="scan-id:pair",
        assets=(asset(LOW), asset(HIGH)),
        provider_metadata={"similarity_percent": "98.5"},
    )

    class Provider:
        def __init__(self, group: DiscoveredGroup) -> None:
            self.group = group

        async def discover(self) -> list[DiscoveredGroup]:
            return [self.group]

    providers = [Provider(immich), Provider(similar)]
    if reverse:
        providers.reverse()
    groups = await CompositeGroupDiscoveryProvider(*providers).discover()

    assert len(groups) == 1
    assert groups[0].group_id == "immich-group"
    assert groups[0].provider_group_id == "immich-provider-id"
    assert groups[0].discovery_source is DiscoverySource.IMMICH_DUPLICATE
    assert [item.discovery_source for item in groups[0].evidence] == [
        DiscoverySource.IMMICH_DUPLICATE,
        DiscoverySource.COMPANION_SIMILARITY,
    ]
    assert groups[0].evidence[1].metadata["similarity_percent"] == "98.5"


@pytest.mark.asyncio
async def test_composite_provider_does_not_merge_partial_or_transitive_overlap() -> None:
    groups = [
        DiscoveredGroup(
            group_id="immich-ab",
            discovery_source=DiscoverySource.IMMICH_DUPLICATE,
            provider_group_id="one",
            assets=(asset(LOW), asset(HIGH)),
        ),
        DiscoveredGroup(
            group_id="similar-abc",
            discovery_source=DiscoverySource.COMPANION_SIMILARITY,
            provider_group_id="two",
            assets=(asset(LOW), asset(HIGH), asset(THIRD)),
        ),
        DiscoveredGroup(
            group_id="similar-bc",
            discovery_source=DiscoverySource.COMPANION_SIMILARITY,
            provider_group_id="three",
            assets=(asset(HIGH), asset(THIRD)),
        ),
    ]

    class Provider:
        def __init__(self, group: DiscoveredGroup) -> None:
            self.group = group

        async def discover(self) -> list[DiscoveredGroup]:
            return [self.group]

    discovered = await CompositeGroupDiscoveryProvider(
        *(Provider(group) for group in groups)
    ).discover()

    assert [group.group_id for group in discovered] == [
        "immich-ab",
        "similar-abc",
        "similar-bc",
    ]

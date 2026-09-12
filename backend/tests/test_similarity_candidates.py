"""Bounded perceptual-neighbor candidate discovery tests."""

from dataclasses import dataclass
from uuid import UUID

import pytest

from companion.discovery import (
    BoundedSimilarityCandidateIndex,
    SimilarityCandidateStats,
    bounded_similarity_candidates,
)


@dataclass(frozen=True)
class Feature:
    asset_id: UUID
    perceptual_hash: str
    width: int = 100
    height: int = 100
    model_version: str = "appearance-v1"
    feature_version: int = 2


def feature(number: int, perceptual_hash: int, **values: object) -> Feature:
    return Feature(
        asset_id=UUID(int=number),
        perceptual_hash=f"{perceptual_hash:016x}",
        **values,
    )


def test_returns_unique_canonical_pairs_at_the_distance_boundary() -> None:
    features = [
        feature(3, 0b1111),
        feature(1, 0),
        feature(2, 0b0011),
    ]

    pairs = bounded_similarity_candidates(
        features,
        maximum_perceptual_distance=2,
    )

    assert [(pair.asset_id_low.int, pair.asset_id_high.int) for pair in pairs] == [
        (1, 2),
        (2, 3),
    ]
    assert [pair.perceptual_distance for pair in pairs] == [2, 2]


def test_filters_incompatible_versions_and_aspect_ratios() -> None:
    pairs = bounded_similarity_candidates(
        [
            feature(1, 0),
            feature(2, 0, width=200, height=100),
            feature(3, 0, model_version="appearance-v2"),
            feature(4, 0, feature_version=3),
        ],
        maximum_aspect_difference=0.05,
    )

    assert pairs == []


def test_bounds_total_neighbor_degree_and_is_deterministic() -> None:
    features = [feature(number, 0) for number in range(1, 12)]

    first = bounded_similarity_candidates(features, maximum_neighbors_per_asset=2)
    second = bounded_similarity_candidates(
        list(reversed(features)),
        maximum_neighbors_per_asset=2,
    )

    assert first == second
    counts = {feature.asset_id: 0 for feature in features}
    for pair in first:
        counts[pair.asset_id_low] += 1
        counts[pair.asset_id_high] += 1
    assert max(counts.values()) <= 2


def test_incremental_batches_match_single_pass_output() -> None:
    features = [feature(number, number // 4) for number in range(1, 28)]
    expected = bounded_similarity_candidates(features, maximum_neighbors_per_asset=3)
    index = BoundedSimilarityCandidateIndex(features, maximum_neighbors_per_asset=3)

    while index.processed < len(index.ordered_features):
        index.process_next(5)

    assert index.pairs == expected


def test_identical_hash_capacity_stays_degree_bounded() -> None:
    asset_count = 10_000
    maximum_neighbors = 8
    stats = SimilarityCandidateStats()

    pairs = bounded_similarity_candidates(
        [feature(number, 0) for number in range(1, asset_count + 1)],
        maximum_perceptual_distance=0,
        maximum_neighbors_per_asset=maximum_neighbors,
        stats=stats,
    )

    assert len(pairs) <= asset_count * maximum_neighbors // 2
    assert stats.pairs_emitted == len(pairs)
    assert stats.raw_neighbor_matches == len(pairs)
    assert stats.peak_query_matches <= maximum_neighbors
    assert stats.peak_active_index_assets <= maximum_neighbors


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("maximum_perceptual_distance", 65),
        ("maximum_aspect_difference", 1.1),
        ("maximum_neighbors_per_asset", 0),
    ],
)
def test_rejects_unsafe_limits(argument: str, value: int | float) -> None:
    with pytest.raises(ValueError):
        bounded_similarity_candidates([feature(1, 0)], **{argument: value})

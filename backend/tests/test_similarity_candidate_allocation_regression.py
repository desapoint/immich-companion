"""Regression coverage for allocation-conscious similarity candidate staging."""

from dataclasses import dataclass
from uuid import UUID

from companion.discovery import BoundedSimilarityCandidateIndex, SimilarityCandidateStats


@dataclass(frozen=True)
class Feature:
    asset_id: UUID
    perceptual_hash: str
    width: int = 100
    height: int = 100
    model_version: str = "appearance-v1"
    feature_version: int = 2


def feature(number: int, perceptual_hash: int = 0) -> Feature:
    return Feature(asset_id=UUID(int=number), perceptual_hash=f"{perceptual_hash:016x}")


def test_index_consumes_single_pass_iterable_and_preserves_received_count() -> None:
    stats = SimilarityCandidateStats()
    inputs = (item for item in [feature(2), feature(1), feature(2, 1)])

    index = BoundedSimilarityCandidateIndex(inputs, stats=stats)

    assert stats.assets_received == 3
    assert [item.asset_id.int for item in index.ordered_features] == [1, 2]
    assert index.ordered_features[1].perceptual_hash == f"{1:016x}"


def test_incremental_processing_keeps_existing_batch_semantics() -> None:
    index = BoundedSimilarityCandidateIndex(
        (feature(number, number // 3) for number in range(1, 10)),
        maximum_neighbors_per_asset=3,
    )

    first = index.process_next(2)
    second = index.process_next(2)

    assert index.processed == 4
    assert first == index.pairs[: len(first)]
    assert second == index.pairs[len(first) :]


def test_candidate_pairs_remain_canonical_after_allocation_optimization() -> None:
    index = BoundedSimilarityCandidateIndex(
        (feature(number, perceptual_hash=0) for number in (3, 1, 2)),
        maximum_neighbors_per_asset=3,
    )

    pairs = index.process_next(3)

    assert pairs
    assert all(pair.asset_id_low.int < pair.asset_id_high.int for pair in pairs)

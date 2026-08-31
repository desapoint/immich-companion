"""Similarity scan persistence contract tests."""

from uuid import UUID

import pytest

from companion.similarity_repository import PairSimilarityEvidence
from companion.similarity_scan_repository import (
    SimilarityScanPair,
    SimilarityScanParameters,
    normalize_scan_pairs,
)

LEFT = UUID("11111111-1111-4111-8111-111111111111")
RIGHT = UUID("22222222-2222-4222-8222-222222222222")


def evidence() -> PairSimilarityEvidence:
    return PairSimilarityEvidence(
        similarity_percent=98.5,
        structural_percent=99.0,
        perceptual_percent=96.0,
        color_percent=97.0,
        exact_thumbnail_match=False,
        exact_pixel_match=False,
        model_version="appearance-v1",
        feature_version=2,
        comparison_version=2,
    )


def pair(left: UUID = LEFT, right: UUID = RIGHT) -> SimilarityScanPair:
    return SimilarityScanPair(
        asset_id_low=left,
        asset_id_high=right,
        asset_low_source_sha256="left-source",
        asset_high_source_sha256="right-source",
        evidence=evidence(),
    )


def test_normalizes_pair_direction_and_source_fingerprints() -> None:
    normalized = normalize_scan_pairs([pair(RIGHT, LEFT)])

    assert normalized[0].asset_id_low == LEFT
    assert normalized[0].asset_id_high == RIGHT
    assert normalized[0].asset_low_source_sha256 == "right-source"
    assert normalized[0].asset_high_source_sha256 == "left-source"


def test_rejects_duplicate_and_self_pairs() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        normalize_scan_pairs([pair(), pair(RIGHT, LEFT)])
    with pytest.raises(ValueError, match="distinct"):
        normalize_scan_pairs([pair(LEFT, LEFT)])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("similarity_threshold", 101),
        ("maximum_perceptual_distance", 65),
        ("maximum_aspect_difference", 1.1),
        ("maximum_neighbors_per_asset", 0),
        ("maximum_matches", 50_001),
    ],
)
def test_rejects_unsafe_scan_parameters(field: str, value: int | float) -> None:
    values = {
        "model_version": "appearance-v1",
        "feature_version": 2,
        "comparison_version": 2,
        "similarity_threshold": 95.0,
        "maximum_perceptual_distance": 12,
        "maximum_aspect_difference": 0.05,
        "maximum_neighbors_per_asset": 8,
        "maximum_matches": 5000,
        field: value,
    }
    with pytest.raises(ValueError):
        SimilarityScanParameters(**values)

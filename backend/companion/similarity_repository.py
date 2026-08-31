"""Sparse persistence for explainable pairwise visual evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.models import AssetSimilarityEdgeRecord, AssetSimilarityFeatureRecord
from companion.similarity_features import (
    SIMILARITY_FEATURE_VERSION,
    SIMILARITY_MODEL_VERSION,
    VisualFeatureResult,
    compare_visual_features,
)

SIMILARITY_COMPARISON_VERSION = 2


@dataclass(frozen=True, slots=True)
class PairSimilarityEvidence:
    similarity_percent: float
    structural_percent: float
    perceptual_percent: float
    color_percent: float
    exact_thumbnail_match: bool
    exact_pixel_match: bool
    model_version: str
    feature_version: int
    comparison_version: int


def canonical_pair(left: UUID, right: UUID) -> tuple[UUID, UUID]:
    if left == right:
        raise ValueError("A similarity edge requires two distinct assets.")
    return (left, right) if left.int < right.int else (right, left)


def requested_reference_pairs(
    groups: list[list[UUID]],
    available_asset_ids: set[UUID],
) -> dict[tuple[UUID, UUID], tuple[UUID, UUID]]:
    """Plan at most N-1 available edges per group, preserving reference direction."""

    return {
        (reference, member): canonical_pair(reference, member)
        for group in groups
        if len(group) > 1
        for reference in group[:1]
        for member in group[1:]
        if reference in available_asset_ids and member in available_asset_ids
    }


def _feature(record: AssetSimilarityFeatureRecord) -> VisualFeatureResult:
    return VisualFeatureResult(
        model_version=record.model_version,
        feature_version=record.feature_version,
        width=record.width,
        height=record.height,
        luminance_vector=record.luminance_vector,
        perceptual_hash=record.perceptual_hash,
        color_histogram=record.color_histogram,
        thumbnail_sha256=record.thumbnail_sha256,
        pixel_normalization_version=record.pixel_normalization_version,
        pixel_sha256=record.pixel_sha256,
        bit_depth=record.bit_depth,
        channel_count=record.channel_count,
        has_alpha=record.has_alpha,
        color_space=record.color_space,
        orientation=record.orientation,
        icc_profile_present=record.icc_profile_present,
        has_exif=record.has_exif,
        has_capture_time=record.has_capture_time,
        has_camera_info=record.has_camera_info,
        has_gps=record.has_gps,
        has_orientation_metadata=record.has_orientation_metadata,
        metadata_richness=record.metadata_richness,
    )


def _public(record: AssetSimilarityEdgeRecord) -> PairSimilarityEvidence:
    return PairSimilarityEvidence(
        similarity_percent=record.similarity_percent,
        structural_percent=record.structural_percent,
        perceptual_percent=record.perceptual_percent,
        color_percent=record.color_percent,
        exact_thumbnail_match=record.exact_thumbnail_match,
        exact_pixel_match=record.exact_pixel_match,
        model_version=record.model_version,
        feature_version=record.feature_version,
        comparison_version=record.comparison_version,
    )


class SimilarityRepository:
    """Read or calculate only requested pair edges, never a dense pair matrix."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def reference_edges(
        self,
        groups: list[list[UUID]],
        features: dict[UUID, AssetSimilarityFeatureRecord],
    ) -> dict[tuple[UUID, UUID], PairSimilarityEvidence]:
        requested = requested_reference_pairs(groups, set(features))
        canonical = list(dict.fromkeys(requested.values()))
        if not canonical:
            return {}

        statement = select(AssetSimilarityEdgeRecord).where(
            tuple_(
                AssetSimilarityEdgeRecord.asset_id_low,
                AssetSimilarityEdgeRecord.asset_id_high,
            ).in_(canonical),
            AssetSimilarityEdgeRecord.model_version == SIMILARITY_MODEL_VERSION,
            AssetSimilarityEdgeRecord.feature_version == SIMILARITY_FEATURE_VERSION,
            AssetSimilarityEdgeRecord.comparison_version == SIMILARITY_COMPARISON_VERSION,
        )
        async with self._database.sessions() as session:
            cached = list((await session.scalars(statement)).all())
        records = {(record.asset_id_low, record.asset_id_high): record for record in cached}

        values: list[dict[str, object]] = []
        current: dict[tuple[UUID, UUID], PairSimilarityEvidence] = {}
        for low, high in canonical:
            low_feature = features[low]
            high_feature = features[high]
            record = records.get((low, high))
            if (
                record is not None
                and record.asset_low_source_sha256 == low_feature.source_sha256
                and record.asset_high_source_sha256 == high_feature.source_sha256
            ):
                current[(low, high)] = _public(record)
                continue
            comparison = compare_visual_features(_feature(low_feature), _feature(high_feature))
            evidence = PairSimilarityEvidence(
                similarity_percent=comparison.similarity_percent,
                structural_percent=comparison.structural_percent,
                perceptual_percent=comparison.perceptual_percent,
                color_percent=comparison.color_percent,
                exact_thumbnail_match=(
                    low_feature.thumbnail_sha256 == high_feature.thumbnail_sha256
                ),
                exact_pixel_match=(
                    low_feature.pixel_normalization_version
                    == high_feature.pixel_normalization_version
                    and low_feature.pixel_sha256 == high_feature.pixel_sha256
                ),
                model_version=SIMILARITY_MODEL_VERSION,
                feature_version=SIMILARITY_FEATURE_VERSION,
                comparison_version=SIMILARITY_COMPARISON_VERSION,
            )
            current[(low, high)] = evidence
            values.append(
                {
                    "asset_id_low": low,
                    "asset_id_high": high,
                    "asset_low_source_sha256": low_feature.source_sha256,
                    "asset_high_source_sha256": high_feature.source_sha256,
                    "similarity_percent": evidence.similarity_percent,
                    "structural_percent": evidence.structural_percent,
                    "perceptual_percent": evidence.perceptual_percent,
                    "color_percent": evidence.color_percent,
                    "exact_thumbnail_match": evidence.exact_thumbnail_match,
                    "exact_pixel_match": evidence.exact_pixel_match,
                    "model_version": evidence.model_version,
                    "feature_version": evidence.feature_version,
                    "comparison_version": evidence.comparison_version,
                    "calculated_at": datetime.now(UTC),
                }
            )

        if values:
            statement = insert(AssetSimilarityEdgeRecord).values(values)
            update_keys = set(values[0]) - {
                "asset_id_low",
                "asset_id_high",
                "model_version",
                "feature_version",
                "comparison_version",
            }
            async with self._database.sessions() as session, session.begin():
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[
                            AssetSimilarityEdgeRecord.asset_id_low,
                            AssetSimilarityEdgeRecord.asset_id_high,
                            AssetSimilarityEdgeRecord.model_version,
                            AssetSimilarityEdgeRecord.feature_version,
                            AssetSimilarityEdgeRecord.comparison_version,
                        ],
                        set_={key: getattr(statement.excluded, key) for key in update_keys},
                    )
                )
        return {original: current[pair] for original, pair in requested.items() if pair in current}

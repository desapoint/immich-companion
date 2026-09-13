"""Sparse persistence for explainable pairwise visual evidence."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.models import (
    AssetSimilarityEdgeRecord,
    AssetSimilarityFeatureRecord,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_detail import (
    DETAIL_FEATURE_VERSION,
    DetailFeature,
    compare_detail_features,
)
from companion.similarity_detail_service import SimilarityDetailRepository
from companion.similarity_features import (
    PIXEL_NORMALIZATION_VERSION,
    SIMILARITY_CONFIG_FINGERPRINT,
    VisualFeatureResult,
    compare_visual_features,
)

SIMILARITY_COMPARISON_VERSION = 5
PAIR_DETAIL_BATCH_SIZE = 500
PAIR_CACHE_ENTRY_ESTIMATE_BYTES = 512
HOT_CACHE_ENTRY_ESTIMATE_BYTES = 1024


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
    normalized_luminance_mae: float | None = None
    normalized_luminance_rmse: float | None = None
    normalized_luminance_ssim: float | None = None
    aspect_ratio_difference: float | None = None
    dimensions_equal: bool | None = None
    detail_changed_percent: float | None = None
    detail_source: str | None = None


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


SimilarityFeatureRecord = AssetSimilarityFeatureRecord | AssetSimilaritySearchFeatureRecord


def _source_key(record: SimilarityFeatureRecord) -> str:
    # Legacy pair-cache columns are named source_sha256. Search records carry
    # a versioned source/preview identity, not an original-file SHA.
    return (
        record.source_identity
        if isinstance(record, AssetSimilaritySearchFeatureRecord)
        else record.source_sha256
    )


def _feature(record: SimilarityFeatureRecord) -> VisualFeatureResult:
    return VisualFeatureResult(
        model_version=record.model_version,
        feature_version=record.feature_version,
        width=record.width,
        height=record.height,
        luminance_vector=record.luminance_vector,
        perceptual_hash=record.perceptual_hash,
        color_histogram=record.color_histogram,
        thumbnail_sha256=record.thumbnail_sha256,
        pixel_normalization_version=getattr(record, "pixel_normalization_version", 0),
        pixel_sha256=getattr(record, "pixel_sha256", None),
        bit_depth=getattr(record, "bit_depth", 8),
        channel_count=getattr(record, "channel_count", 3),
        has_alpha=getattr(record, "has_alpha", False),
        color_space=getattr(record, "color_space", "preview"),
        orientation=getattr(record, "orientation", None),
        icc_profile_present=getattr(record, "icc_profile_present", False),
        has_exif=getattr(record, "has_exif", False),
        has_capture_time=getattr(record, "has_capture_time", False),
        has_camera_info=getattr(record, "has_camera_info", False),
        has_gps=getattr(record, "has_gps", False),
        has_orientation_metadata=getattr(record, "has_orientation_metadata", False),
        metadata_richness=getattr(record, "metadata_richness", 0),
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
        normalized_luminance_mae=record.normalized_luminance_mae,
        normalized_luminance_rmse=record.normalized_luminance_rmse,
        normalized_luminance_ssim=record.normalized_luminance_ssim,
        aspect_ratio_difference=record.aspect_ratio_difference,
        dimensions_equal=record.dimensions_equal,
        detail_changed_percent=record.detail_changed_percent,
        detail_source=record.detail_source,
    )


class SimilarityRepository:
    """Read or calculate only requested pair edges, never a dense pair matrix."""

    def __init__(
        self,
        database: DatabaseManager,
        *,
        pair_max_bytes: int = 256 * 1024 * 1024,
        hot_max_bytes: int = 96 * 1024 * 1024,
        details: SimilarityDetailRepository | None = None,
    ) -> None:
        self._database = database
        self._details = details
        self._pair_max_entries = max(1, pair_max_bytes // PAIR_CACHE_ENTRY_ESTIMATE_BYTES)
        self._pair_max_bytes = pair_max_bytes
        self._hot_max_entries = max(1, hot_max_bytes // HOT_CACHE_ENTRY_ESTIMATE_BYTES)
        self._hot_max_bytes = hot_max_bytes
        self._hot: OrderedDict[tuple[object, ...], PairSimilarityEvidence] = OrderedDict()
        self._pair_hits = 0
        self._pair_misses = 0
        self._hot_hits = 0
        self._hot_misses = 0
        self._pair_evictions = 0
        self._hot_evictions = 0
        self._reference_latencies_ms: deque[float] = deque(maxlen=512)

    @staticmethod
    def _hot_key(
        low: UUID,
        high: UUID,
        low_feature: SimilarityFeatureRecord,
        high_feature: SimilarityFeatureRecord,
        detail_version: int = 0,
    ) -> tuple[object, ...]:
        return (
            low,
            high,
            _source_key(low_feature),
            _source_key(high_feature),
            low_feature.config_fingerprint,
            SIMILARITY_COMPARISON_VERSION,
            detail_version,
        )

    def _hot_get(self, key: tuple[object, ...]) -> PairSimilarityEvidence | None:
        evidence = self._hot.get(key)
        if evidence is None:
            self._hot_misses += 1
            return None
        self._hot.move_to_end(key)
        self._hot_hits += 1
        return evidence

    def _hot_put(self, key: tuple[object, ...], evidence: PairSimilarityEvidence) -> None:
        self._hot[key] = evidence
        self._hot.move_to_end(key)
        while len(self._hot) > self._hot_max_entries:
            self._hot.popitem(last=False)
            self._hot_evictions += 1

    async def reference_edges(
        self,
        groups: list[list[UUID]],
        features: dict[UUID, SimilarityFeatureRecord],
    ) -> dict[tuple[UUID, UUID], PairSimilarityEvidence]:
        started = perf_counter()
        requested = requested_reference_pairs(groups, set(features))
        if len(requested) > PAIR_DETAIL_BATCH_SIZE:
            ordered = list(requested)
            combined: dict[tuple[UUID, UUID], PairSimilarityEvidence] = {}
            for offset in range(0, len(ordered), PAIR_DETAIL_BATCH_SIZE):
                batch = ordered[offset : offset + PAIR_DETAIL_BATCH_SIZE]
                combined.update(
                    await self.reference_edges(
                        [[left, right] for left, right in batch], features
                    )
                )
            return combined
        canonical = list(dict.fromkeys(requested.values()))
        if not canonical:
            return {}

        generation = {
            (feature.model_version, feature.feature_version, feature.config_fingerprint)
            for feature in features.values()
        }
        if len(generation) != 1:
            raise ValueError("Similarity comparison requires one compatible feature generation")
        model_version, feature_version, config_fingerprint = generation.pop()

        detail_records = (
            await self._details.get_current_many(
                list({asset_id for pair in canonical for asset_id in pair})
            )
            if self._details is not None else {}
        )

        def detail_version(low: UUID, high: UUID) -> int:
            return (
                DETAIL_FEATURE_VERSION
                if low in detail_records and high in detail_records
                and isinstance(features[low], AssetSimilaritySearchFeatureRecord)
                and isinstance(features[high], AssetSimilaritySearchFeatureRecord)
                else 0
            )

        current: dict[tuple[UUID, UUID], PairSimilarityEvidence] = {}
        uncached: list[tuple[UUID, UUID]] = []
        for low, high in canonical:
            hot = self._hot_get(
                self._hot_key(
                    low, high, features[low], features[high], detail_version(low, high)
                )
            )
            if hot is None:
                uncached.append((low, high))
            else:
                current[(low, high)] = hot

        statement = select(AssetSimilarityEdgeRecord).where(
            tuple_(
                AssetSimilarityEdgeRecord.asset_id_low,
                AssetSimilarityEdgeRecord.asset_id_high,
            ).in_(uncached),
            AssetSimilarityEdgeRecord.model_version == model_version,
            AssetSimilarityEdgeRecord.feature_version == feature_version,
            AssetSimilarityEdgeRecord.comparison_version == SIMILARITY_COMPARISON_VERSION,
            AssetSimilarityEdgeRecord.config_fingerprint == config_fingerprint,
        )
        if uncached:
            async with self._database.sessions() as session:
                cached = list((await session.scalars(statement)).all())
        else:
            cached = []
        records = {(record.asset_id_low, record.asset_id_high): record for record in cached}

        values: list[dict[str, object]] = []
        for low, high in uncached:
            low_feature = features[low]
            high_feature = features[high]
            pair_detail_version = detail_version(low, high)
            record = records.get((low, high))
            if (
                record is not None
                and record.asset_low_source_sha256 == _source_key(low_feature)
                and record.asset_high_source_sha256 == _source_key(high_feature)
                and record.detail_version == pair_detail_version
            ):
                evidence = _public(record)
                current[(low, high)] = evidence
                self._hot_put(
                    self._hot_key(
                        low, high, low_feature, high_feature, pair_detail_version
                    ), evidence
                )
                self._pair_hits += 1
                continue
            self._pair_misses += 1
            comparison = compare_visual_features(_feature(low_feature), _feature(high_feature))
            detail_comparison = None
            detail_source = None
            if pair_detail_version:
                low_detail = detail_records[low]
                high_detail = detail_records[high]
                detail_comparison = await asyncio.to_thread(
                    compare_detail_features,
                    DetailFeature(low_detail.width, low_detail.height, low_detail.sample),
                    DetailFeature(high_detail.width, high_detail.height, high_detail.sample),
                )
                detail_source = (
                    "preview" if "preview_fallback" in {low_detail.origin, high_detail.origin}
                    else "transcoded" if "transcoded_fullsize" in {
                        low_detail.origin, high_detail.origin
                    }
                    else "original"
                )
            evidence = PairSimilarityEvidence(
                similarity_percent=(
                    min(comparison.similarity_percent, detail_comparison.similarity_percent)
                    if detail_comparison is not None else comparison.similarity_percent
                ),
                structural_percent=comparison.structural_percent,
                perceptual_percent=comparison.perceptual_percent,
                color_percent=comparison.color_percent,
                exact_thumbnail_match=(
                    low_feature.thumbnail_sha256 == high_feature.thumbnail_sha256
                ),
                exact_pixel_match=(
                    not isinstance(low_feature, AssetSimilaritySearchFeatureRecord)
                    and not isinstance(high_feature, AssetSimilaritySearchFeatureRecord)
                    and low_feature.pixel_normalization_version == PIXEL_NORMALIZATION_VERSION
                    and high_feature.pixel_normalization_version == PIXEL_NORMALIZATION_VERSION
                    and bool(low_feature.pixel_sha256)
                    and low_feature.pixel_sha256 == high_feature.pixel_sha256
                ),
                model_version=model_version,
                feature_version=feature_version,
                comparison_version=SIMILARITY_COMPARISON_VERSION,
                normalized_luminance_mae=comparison.normalized_luminance_mae,
                normalized_luminance_rmse=comparison.normalized_luminance_rmse,
                normalized_luminance_ssim=comparison.normalized_luminance_ssim,
                aspect_ratio_difference=comparison.aspect_ratio_difference,
                dimensions_equal=comparison.dimensions_equal,
                detail_changed_percent=(
                    detail_comparison.changed_percent if detail_comparison else None
                ),
                detail_source=detail_source,
            )
            current[(low, high)] = evidence
            self._hot_put(
                self._hot_key(
                    low, high, low_feature, high_feature, pair_detail_version
                ), evidence
            )
            values.append(
                {
                    "asset_id_low": low,
                    "asset_id_high": high,
                    "asset_low_source_sha256": _source_key(low_feature),
                    "asset_high_source_sha256": _source_key(high_feature),
                    "similarity_percent": evidence.similarity_percent,
                    "structural_percent": evidence.structural_percent,
                    "perceptual_percent": evidence.perceptual_percent,
                    "color_percent": evidence.color_percent,
                    "normalized_luminance_mae": evidence.normalized_luminance_mae,
                    "normalized_luminance_rmse": evidence.normalized_luminance_rmse,
                    "normalized_luminance_ssim": evidence.normalized_luminance_ssim,
                    "aspect_ratio_difference": evidence.aspect_ratio_difference,
                    "dimensions_equal": evidence.dimensions_equal,
                    "exact_thumbnail_match": evidence.exact_thumbnail_match,
                    "exact_pixel_match": evidence.exact_pixel_match,
                    "detail_version": pair_detail_version,
                    "detail_changed_percent": evidence.detail_changed_percent,
                    "detail_source": evidence.detail_source,
                    "model_version": evidence.model_version,
                    "feature_version": evidence.feature_version,
                    "comparison_version": evidence.comparison_version,
                    "config_fingerprint": config_fingerprint,
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
            await self._trim_pair_cache()
        self._reference_latencies_ms.append((perf_counter() - started) * 1000)
        return {original: current[pair] for original, pair in requested.items() if pair in current}

    async def _trim_pair_cache(self) -> None:
        async with self._database.sessions() as session, session.begin():
            count = int(
                await session.scalar(select(func.count()).select_from(AssetSimilarityEdgeRecord))
                or 0
            )
            overflow = count - self._pair_max_entries
            if overflow <= 0:
                return
            doomed = (
                select(
                    AssetSimilarityEdgeRecord.asset_id_low,
                    AssetSimilarityEdgeRecord.asset_id_high,
                    AssetSimilarityEdgeRecord.model_version,
                    AssetSimilarityEdgeRecord.feature_version,
                    AssetSimilarityEdgeRecord.comparison_version,
                )
                .order_by(AssetSimilarityEdgeRecord.calculated_at)
                .limit(overflow)
            )
            await session.execute(
                delete(AssetSimilarityEdgeRecord).where(
                    tuple_(
                        AssetSimilarityEdgeRecord.asset_id_low,
                        AssetSimilarityEdgeRecord.asset_id_high,
                        AssetSimilarityEdgeRecord.model_version,
                        AssetSimilarityEdgeRecord.feature_version,
                        AssetSimilarityEdgeRecord.comparison_version,
                    ).in_(doomed)
                )
            )
            self._pair_evictions += overflow

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
        return round(ordered[index], 2)

    async def cache_status(self) -> dict[str, object]:
        async with self._database.sessions() as session:
            feature_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(AssetSimilarityFeatureRecord)
                    .where(
                        AssetSimilarityFeatureRecord.config_fingerprint
                        == SIMILARITY_CONFIG_FINGERPRINT
                    )
                )
                or 0
            )
            pair_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(AssetSimilarityEdgeRecord)
                    .where(
                        AssetSimilarityEdgeRecord.config_fingerprint
                        == SIMILARITY_CONFIG_FINGERPRINT
                    )
                )
                or 0
            )
        latencies = list(self._reference_latencies_ms)
        return {
            "config_fingerprint": SIMILARITY_CONFIG_FINGERPRINT,
            "feature_count": feature_count,
            "feature_estimated_bytes": feature_count * HOT_CACHE_ENTRY_ESTIMATE_BYTES,
            "pair_count": pair_count,
            "pair_estimated_bytes": pair_count * PAIR_CACHE_ENTRY_ESTIMATE_BYTES,
            "pair_max_bytes": self._pair_max_bytes,
            "pair_hits": self._pair_hits,
            "pair_misses": self._pair_misses,
            "pair_evictions": self._pair_evictions,
            "hot_count": len(self._hot),
            "hot_estimated_bytes": len(self._hot) * HOT_CACHE_ENTRY_ESTIMATE_BYTES,
            "hot_max_bytes": self._hot_max_bytes,
            "hot_hits": self._hot_hits,
            "hot_misses": self._hot_misses,
            "hot_evictions": self._hot_evictions,
            "reference_latency_p50_ms": self._percentile(latencies, 0.5),
            "reference_latency_p95_ms": self._percentile(latencies, 0.95),
        }

    async def clear_cache(self, cache: Literal["pairs", "hot"]) -> int:
        if cache == "hot":
            count = len(self._hot)
            self._hot.clear()
            return count
        async with self._database.sessions() as session, session.begin():
            count = int(
                await session.scalar(select(func.count()).select_from(AssetSimilarityEdgeRecord))
                or 0
            )
            await session.execute(delete(AssetSimilarityEdgeRecord))
        self._hot.clear()
        return count

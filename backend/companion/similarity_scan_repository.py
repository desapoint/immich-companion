"""Atomic persistence for versioned Companion similarity scan snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import insert, select, update

from companion.database import DatabaseManager
from companion.models import SimilarityScanPairRecord, SimilarityScanRecord
from companion.similarity_repository import PairSimilarityEvidence


@dataclass(frozen=True, slots=True)
class SimilarityScanParameters:
    model_version: str
    feature_version: int
    comparison_version: int
    scope: str
    similarity_threshold: float
    maximum_perceptual_distance: int
    maximum_aspect_difference: float
    maximum_neighbors_per_asset: int
    maximum_matches: int

    def __post_init__(self) -> None:
        if not 50 <= self.similarity_threshold <= 100:
            raise ValueError("similarity_threshold must be between 50 and 100")
        if not 0 <= self.maximum_perceptual_distance <= 64:
            raise ValueError("maximum_perceptual_distance must be between 0 and 64")
        if not 0 <= self.maximum_aspect_difference <= 1:
            raise ValueError("maximum_aspect_difference must be between 0 and 1")
        if self.maximum_neighbors_per_asset < 1:
            raise ValueError("maximum_neighbors_per_asset must be positive")
        if not 1 <= self.maximum_matches <= 50_000:
            raise ValueError("maximum_matches must be between 1 and 50000")
        if self.scope != "all_eligible_assets":
            raise ValueError("Unsupported similarity scan scope")


@dataclass(frozen=True, slots=True)
class SimilarityScanPair:
    asset_id_low: UUID
    asset_id_high: UUID
    asset_low_source_sha256: str
    asset_high_source_sha256: str
    evidence: PairSimilarityEvidence


@dataclass(frozen=True, slots=True)
class SimilarityScanSnapshot:
    id: UUID
    parameters: SimilarityScanParameters
    asset_count: int
    candidate_count: int
    completed_at: datetime
    pairs: tuple[SimilarityScanPair, ...]


@dataclass(frozen=True, slots=True)
class SimilarityScanRunSummary:
    id: UUID
    parameters: SimilarityScanParameters
    asset_count: int
    candidate_count: int
    match_count: int
    completed_at: datetime


def normalize_scan_pairs(pairs: list[SimilarityScanPair]) -> list[SimilarityScanPair]:
    """Canonicalize pair direction and reject duplicate relationships."""

    normalized: list[SimilarityScanPair] = []
    seen: set[tuple[UUID, UUID]] = set()
    for pair in pairs:
        if pair.asset_id_low == pair.asset_id_high:
            raise ValueError("A similarity scan pair requires two distinct assets")
        if pair.asset_id_low.int < pair.asset_id_high.int:
            item = pair
        else:
            item = SimilarityScanPair(
                asset_id_low=pair.asset_id_high,
                asset_id_high=pair.asset_id_low,
                asset_low_source_sha256=pair.asset_high_source_sha256,
                asset_high_source_sha256=pair.asset_low_source_sha256,
                evidence=pair.evidence,
            )
        key = (item.asset_id_low, item.asset_id_high)
        if key in seen:
            raise ValueError("A similarity scan cannot contain duplicate pairs")
        seen.add(key)
        normalized.append(item)
    return sorted(normalized, key=lambda item: (item.asset_id_low.int, item.asset_id_high.int))


class SimilarityScanRepository:
    """Publish completed scans atomically while retaining failed-run provenance."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def create(self, parameters: SimilarityScanParameters) -> UUID:
        record = SimilarityScanRecord(
            status="running",
            model_version=parameters.model_version,
            feature_version=parameters.feature_version,
            comparison_version=parameters.comparison_version,
            scope=parameters.scope,
            similarity_threshold=parameters.similarity_threshold,
            maximum_perceptual_distance=parameters.maximum_perceptual_distance,
            maximum_aspect_difference=parameters.maximum_aspect_difference,
            maximum_neighbors_per_asset=parameters.maximum_neighbors_per_asset,
            maximum_matches=parameters.maximum_matches,
            asset_count=0,
            candidate_count=0,
            match_count=0,
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)
            await session.flush()
        return record.id

    async def complete(
        self,
        scan_id: UUID,
        *,
        asset_count: int,
        candidate_count: int,
        pairs: list[SimilarityScanPair],
    ) -> None:
        normalized = normalize_scan_pairs(pairs)
        if asset_count < 0 or candidate_count < len(normalized):
            raise ValueError("Similarity scan counts are inconsistent")
        completed_at = datetime.now(UTC)
        values = [
            {
                "scan_id": scan_id,
                "asset_id_low": pair.asset_id_low,
                "asset_id_high": pair.asset_id_high,
                "asset_low_source_sha256": pair.asset_low_source_sha256,
                "asset_high_source_sha256": pair.asset_high_source_sha256,
                "similarity_percent": pair.evidence.similarity_percent,
                "structural_percent": pair.evidence.structural_percent,
                "perceptual_percent": pair.evidence.perceptual_percent,
                "color_percent": pair.evidence.color_percent,
                "normalized_luminance_mae": pair.evidence.normalized_luminance_mae,
                "normalized_luminance_rmse": pair.evidence.normalized_luminance_rmse,
                "normalized_luminance_ssim": pair.evidence.normalized_luminance_ssim,
                "aspect_ratio_difference": pair.evidence.aspect_ratio_difference,
                "dimensions_equal": pair.evidence.dimensions_equal,
                "exact_thumbnail_match": pair.evidence.exact_thumbnail_match,
                "exact_pixel_match": pair.evidence.exact_pixel_match,
            }
            for pair in normalized
        ]
        async with self._database.sessions() as session, session.begin():
            record = await session.get(SimilarityScanRecord, scan_id, with_for_update=True)
            if record is None or record.status != "running":
                raise ValueError("Similarity scan is not running")
            if any(
                pair.evidence.model_version != record.model_version
                or pair.evidence.feature_version != record.feature_version
                or pair.evidence.comparison_version != record.comparison_version
                for pair in normalized
            ):
                raise ValueError("Similarity pair evidence versions do not match the scan")
            if values:
                await session.execute(insert(SimilarityScanPairRecord), values)
            record.status = "completed"
            record.asset_count = asset_count
            record.candidate_count = candidate_count
            record.match_count = len(normalized)
            record.completed_at = completed_at
            record.error = None

    async def fail(self, scan_id: UUID, error: str) -> None:
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                update(SimilarityScanRecord)
                .where(
                    SimilarityScanRecord.id == scan_id,
                    SimilarityScanRecord.status == "running",
                )
                .values(status="failed", error=error[:4000], completed_at=datetime.now(UTC))
            )

    async def cancel(self, scan_id: UUID) -> None:
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                update(SimilarityScanRecord)
                .where(
                    SimilarityScanRecord.id == scan_id,
                    SimilarityScanRecord.status == "running",
                )
                .values(status="cancelled", error=None, completed_at=datetime.now(UTC))
            )

    @staticmethod
    def _parameters(record: SimilarityScanRecord) -> SimilarityScanParameters:
        return SimilarityScanParameters(
            model_version=record.model_version,
            feature_version=record.feature_version,
            comparison_version=record.comparison_version,
            scope=record.scope,
            similarity_threshold=record.similarity_threshold,
            maximum_perceptual_distance=record.maximum_perceptual_distance,
            maximum_aspect_difference=record.maximum_aspect_difference,
            maximum_neighbors_per_asset=record.maximum_neighbors_per_asset,
            maximum_matches=record.maximum_matches,
        )

    async def latest_completed_summary(self) -> SimilarityScanRunSummary | None:
        statement = (
            select(SimilarityScanRecord)
            .where(SimilarityScanRecord.status == "completed")
            .order_by(SimilarityScanRecord.completed_at.desc(), SimilarityScanRecord.id.desc())
            .limit(1)
        )
        async with self._database.sessions() as session:
            record = await session.scalar(statement)
        if record is None or record.completed_at is None:
            return None
        return SimilarityScanRunSummary(
            id=record.id,
            parameters=self._parameters(record),
            asset_count=record.asset_count,
            candidate_count=record.candidate_count,
            match_count=record.match_count,
            completed_at=record.completed_at,
        )

    async def latest_completed(self) -> SimilarityScanSnapshot | None:
        statement = (
            select(SimilarityScanRecord)
            .where(SimilarityScanRecord.status == "completed")
            .order_by(SimilarityScanRecord.completed_at.desc(), SimilarityScanRecord.id.desc())
            .limit(1)
        )
        async with self._database.sessions() as session:
            record = await session.scalar(statement)
            if record is None or record.completed_at is None:
                return None
            pair_statement = (
                select(SimilarityScanPairRecord)
                .where(SimilarityScanPairRecord.scan_id == record.id)
                .order_by(
                    SimilarityScanPairRecord.asset_id_low,
                    SimilarityScanPairRecord.asset_id_high,
                )
            )
            pair_records = list((await session.scalars(pair_statement)).all())
        return SimilarityScanSnapshot(
            id=record.id,
            parameters=self._parameters(record),
            asset_count=record.asset_count,
            candidate_count=record.candidate_count,
            completed_at=record.completed_at,
            pairs=tuple(
                SimilarityScanPair(
                    asset_id_low=pair.asset_id_low,
                    asset_id_high=pair.asset_id_high,
                    asset_low_source_sha256=pair.asset_low_source_sha256,
                    asset_high_source_sha256=pair.asset_high_source_sha256,
                    evidence=PairSimilarityEvidence(
                        similarity_percent=pair.similarity_percent,
                        structural_percent=pair.structural_percent,
                        perceptual_percent=pair.perceptual_percent,
                        color_percent=pair.color_percent,
                        exact_thumbnail_match=pair.exact_thumbnail_match,
                        exact_pixel_match=pair.exact_pixel_match,
                        model_version=record.model_version,
                        feature_version=record.feature_version,
                        comparison_version=record.comparison_version,
                        normalized_luminance_mae=pair.normalized_luminance_mae,
                        normalized_luminance_rmse=pair.normalized_luminance_rmse,
                        normalized_luminance_ssim=pair.normalized_luminance_ssim,
                        aspect_ratio_difference=pair.aspect_ratio_difference,
                        dimensions_equal=pair.dimensions_equal,
                    ),
                )
                for pair in pair_records
            ),
        )

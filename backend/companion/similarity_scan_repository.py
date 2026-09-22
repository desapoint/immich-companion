"""Atomic persistence for versioned Companion similarity scan snapshots."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, delete, func, insert, or_, select, update

from companion.database import DatabaseManager
from companion.models import SimilarityScanPairRecord, SimilarityScanRecord
from companion.similarity_generation import SimilarityEvidenceEpochRepository
from companion.similarity_grouping import (
    SIMILARITY_GROUPING_VERSION,
    SimilarityGroupingEdge,
    SimilarityValidationMode,
)
from companion.similarity_repository import SIMILARITY_COMPARISON_VERSION, PairSimilarityEvidence
from companion.similarity_search_features import SEARCH_CONFIG_FINGERPRINT

SIMILARITY_SCAN_WRITE_BATCH_SIZE = 1_000
SIMILARITY_SCAN_READ_BATCH_SIZE = 1_000
SIMILARITY_SCAN_PAIR_RETENTION_GENERATIONS = 3


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
    grouping_version: int = SIMILARITY_GROUPING_VERSION
    validation_mode: SimilarityValidationMode = "strict"
    max_link_depth: int = 2
    anchor_asset_id: UUID | None = None
    config_fingerprint: str = SEARCH_CONFIG_FINGERPRINT

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
        if self.validation_mode not in {"reference", "linked", "strict"}:
            raise ValueError("Unsupported similarity validation mode")
        if not 0 <= self.max_link_depth <= 64:
            raise ValueError("max_link_depth must be between 0 and 64")


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
    result_limit_reached: bool | None
    completed_at: datetime
    pair_evidence_pruned_at: datetime | None = None


def _pair_values(scan_id: UUID, pairs: list[SimilarityScanPair]) -> list[dict[str, object]]:
    return [
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
            "detail_changed_percent": pair.evidence.detail_changed_percent,
            "detail_source": pair.evidence.detail_source,
        }
        for pair in pairs
    ]


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
        self._evidence_epoch = SimilarityEvidenceEpochRepository(database)

    async def current_evidence_epoch(self) -> int:
        return await self._evidence_epoch.capture_epoch()

    async def prepare(
        self,
        parameters: SimilarityScanParameters,
        *,
        scan_id: UUID | None = None,
    ) -> UUID:
        """Create a scan or reopen its deterministic task-owned run after recovery."""

        if scan_id is not None:
            async with self._database.sessions() as session, session.begin():
                existing = await session.get(SimilarityScanRecord, scan_id, with_for_update=True)
                if existing is not None:
                    if self._parameters(existing) != parameters:
                        raise ValueError("Recovered similarity scan parameters changed")
                    if existing.status == "completed":
                        return existing.id
                    if existing.status == "cancelled":
                        raise ValueError("Similarity scan is already cancelled")
                    existing.status = "running"
                    existing.error = None
                    existing.completed_at = None
                    return existing.id

        record = SimilarityScanRecord(
            id=scan_id,
            status="running",
            model_version=parameters.model_version,
            feature_version=parameters.feature_version,
            comparison_version=parameters.comparison_version,
            config_fingerprint=parameters.config_fingerprint,
            grouping_version=parameters.grouping_version,
            validation_mode=parameters.validation_mode,
            max_link_depth=parameters.max_link_depth,
            anchor_asset_id=parameters.anchor_asset_id,
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

    async def create(self, parameters: SimilarityScanParameters) -> UUID:
        """Compatibility wrapper for callers that do not own a durable task ID."""

        return await self.prepare(parameters)

    async def complete(
        self,
        scan_id: UUID,
        *,
        asset_count: int,
        candidate_count: int,
        pairs: list[SimilarityScanPair],
        result_limit_reached: bool = False,
        evidence_epoch: int | None = None,
    ) -> None:
        normalized = normalize_scan_pairs(pairs)
        if asset_count < 0 or candidate_count < len(normalized):
            raise ValueError("Similarity scan counts are inconsistent")
        expected_epoch = (
            evidence_epoch
            if evidence_epoch is not None
            else await self.current_evidence_epoch()
        )
        completed_at = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            await self._evidence_epoch.assert_current(session, expected_epoch)
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
            for offset in range(0, len(normalized), SIMILARITY_SCAN_WRITE_BATCH_SIZE):
                batch = normalized[offset : offset + SIMILARITY_SCAN_WRITE_BATCH_SIZE]
                await session.execute(
                    insert(SimilarityScanPairRecord),
                    _pair_values(scan_id, batch),
                )
            record.status = "completed"
            record.asset_count = asset_count
            record.candidate_count = candidate_count
            record.match_count = len(normalized)
            record.result_limit_reached = result_limit_reached
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
            config_fingerprint=record.config_fingerprint,
            grouping_version=record.grouping_version,
            validation_mode=record.validation_mode,
            max_link_depth=record.max_link_depth,
            anchor_asset_id=record.anchor_asset_id,
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
            .where(
                SimilarityScanRecord.status == "completed",
                SimilarityScanRecord.config_fingerprint == SEARCH_CONFIG_FINGERPRINT,
                SimilarityScanRecord.comparison_version == SIMILARITY_COMPARISON_VERSION,
                SimilarityScanRecord.grouping_version == SIMILARITY_GROUPING_VERSION,
            )
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
            result_limit_reached=record.result_limit_reached,
            completed_at=record.completed_at,
            pair_evidence_pruned_at=getattr(record, "pair_evidence_pruned_at", None),
        )

    async def latest_completed_parameters(
        self,
    ) -> tuple[UUID, SimilarityScanParameters] | None:
        """Return the active Appearance generation without loading its pair snapshot."""

        statement = (
            select(SimilarityScanRecord)
            .where(
                SimilarityScanRecord.status == "completed",
                SimilarityScanRecord.config_fingerprint == SEARCH_CONFIG_FINGERPRINT,
                SimilarityScanRecord.comparison_version == SIMILARITY_COMPARISON_VERSION,
                SimilarityScanRecord.grouping_version == SIMILARITY_GROUPING_VERSION,
            )
            .order_by(SimilarityScanRecord.completed_at.desc(), SimilarityScanRecord.id.desc())
            .limit(1)
        )
        async with self._database.sessions() as session:
            record = await session.scalar(statement)
        if record is None:
            return None
        return record.id, self._parameters(record)

    async def iter_grouping_edges(
        self,
        scan_id: UUID,
        *,
        batch_size: int = SIMILARITY_SCAN_READ_BATCH_SIZE,
    ) -> AsyncIterator[list[SimilarityGroupingEdge]]:
        """Stream only the compact fields required to rebuild similarity groups."""

        if batch_size < 1:
            raise ValueError("batch_size must be positive")

        async with self._database.sessions() as session:
            record = await session.get(SimilarityScanRecord, scan_id)
            if (
                record is None
                or record.status != "completed"
                or getattr(record, "pair_evidence_pruned_at", None) is not None
            ):
                return

        last_low: UUID | None = None
        last_high: UUID | None = None
        while True:
            filters = [SimilarityScanPairRecord.scan_id == scan_id]
            if last_low is not None and last_high is not None:
                filters.append(
                    or_(
                        SimilarityScanPairRecord.asset_id_low > last_low,
                        and_(
                            SimilarityScanPairRecord.asset_id_low == last_low,
                            SimilarityScanPairRecord.asset_id_high > last_high,
                        ),
                    )
                )
            statement = (
                select(
                    SimilarityScanPairRecord.asset_id_low,
                    SimilarityScanPairRecord.asset_id_high,
                    SimilarityScanPairRecord.similarity_percent,
                )
                .where(*filters)
                .order_by(
                    SimilarityScanPairRecord.asset_id_low,
                    SimilarityScanPairRecord.asset_id_high,
                )
                .limit(batch_size)
            )
            async with self._database.sessions() as session:
                rows = list((await session.execute(statement)).all())
            if not rows:
                return
            yield [
                SimilarityGroupingEdge(
                    asset_id_low=row.asset_id_low,
                    asset_id_high=row.asset_id_high,
                    similarity_percent=row.similarity_percent,
                )
                for row in rows
            ]
            last_low = rows[-1].asset_id_low
            last_high = rows[-1].asset_id_high

    async def prune_completed_pair_evidence(
        self,
        *,
        keep_completed_generations: int = SIMILARITY_SCAN_PAIR_RETENTION_GENERATIONS,
    ) -> int:
        """Prune heavy pair payloads while preserving immutable scan metadata rows."""

        if keep_completed_generations < 1:
            raise ValueError("keep_completed_generations must be positive")

        statement = (
            select(SimilarityScanRecord.id)
            .where(SimilarityScanRecord.status == "completed")
            .order_by(
                SimilarityScanRecord.completed_at.desc(),
                SimilarityScanRecord.id.desc(),
            )
        )
        async with self._database.sessions() as session:
            completed_ids = list((await session.scalars(statement)).all())

        pruned = 0
        pruned_at = datetime.now(UTC)
        for old_scan_id in completed_ids[keep_completed_generations:]:
            async with self._database.sessions() as session, session.begin():
                record = await session.get(
                    SimilarityScanRecord,
                    old_scan_id,
                    with_for_update=True,
                )
                if (
                    record is None
                    or record.status != "completed"
                    or getattr(record, "pair_evidence_pruned_at", None) is not None
                ):
                    continue
                await session.execute(
                    delete(SimilarityScanPairRecord).where(
                        SimilarityScanPairRecord.scan_id == old_scan_id
                    )
                )
                record.pair_evidence_pruned_at = pruned_at
                pruned += 1
        return pruned

    async def replace_asset_pairs(
        self,
        scan_id: UUID,
        asset_id: UUID,
        pairs: list[SimilarityScanPair],
        *,
        asset_count: int,
    ) -> None:
        """Replace only pairs incident to one changed asset in the active generation."""

        expected_epoch = await self.current_evidence_epoch()
        normalized = normalize_scan_pairs(pairs)
        async with self._database.sessions() as session, session.begin():
            await self._evidence_epoch.assert_current(session, expected_epoch)
            record = await session.get(SimilarityScanRecord, scan_id, with_for_update=True)
            if record is None or record.status != "completed":
                return
            await session.execute(
                delete(SimilarityScanPairRecord).where(
                    SimilarityScanPairRecord.scan_id == scan_id,
                    or_(
                        SimilarityScanPairRecord.asset_id_low == asset_id,
                        SimilarityScanPairRecord.asset_id_high == asset_id,
                    ),
                )
            )
            for offset in range(0, len(normalized), SIMILARITY_SCAN_WRITE_BATCH_SIZE):
                batch = normalized[offset : offset + SIMILARITY_SCAN_WRITE_BATCH_SIZE]
                await session.execute(
                    insert(SimilarityScanPairRecord),
                    _pair_values(scan_id, batch),
                )
            match_count = await session.scalar(
                select(func.count())
                .select_from(SimilarityScanPairRecord)
                .where(SimilarityScanPairRecord.scan_id == scan_id)
            )
            record.asset_count = asset_count
            record.match_count = int(match_count or 0)
            # Incremental pair replacement does not replay the whole candidate set,
            # so the original full-scan cap verdict is no longer definitive.
            record.result_limit_reached = None

    async def pair_evidence(
        self,
        scan_id: UUID,
        asset_ids: list[UUID],
        *,
        source_identities: dict[UUID, str] | None = None,
    ) -> dict[tuple[UUID, UUID], PairSimilarityEvidence]:
        """Return persisted pair evidence from one completed scan for the requested assets.

        When current search source identities are supplied, stale scan edges are omitted
        instead of being presented as current comparison evidence.
        """

        unique_ids = list(dict.fromkeys(asset_ids))
        if len(unique_ids) < 2:
            return {}
        async with self._database.sessions() as session:
            record = await session.get(SimilarityScanRecord, scan_id)
            if (
                record is None
                or record.status != "completed"
                or getattr(record, "pair_evidence_pruned_at", None) is not None
            ):
                return {}
            pair_statement = (
                select(SimilarityScanPairRecord)
                .where(
                    SimilarityScanPairRecord.scan_id == scan_id,
                    SimilarityScanPairRecord.asset_id_low.in_(unique_ids),
                    SimilarityScanPairRecord.asset_id_high.in_(unique_ids),
                )
                .order_by(
                    SimilarityScanPairRecord.asset_id_low,
                    SimilarityScanPairRecord.asset_id_high,
                )
            )
            pair_records = list((await session.scalars(pair_statement)).all())

        evidence: dict[tuple[UUID, UUID], PairSimilarityEvidence] = {}
        for pair in pair_records:
            if source_identities is not None and (
                source_identities.get(pair.asset_id_low) != pair.asset_low_source_sha256
                or source_identities.get(pair.asset_id_high) != pair.asset_high_source_sha256
            ):
                continue
            evidence[(pair.asset_id_low, pair.asset_id_high)] = PairSimilarityEvidence(
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
                detail_changed_percent=pair.detail_changed_percent,
                detail_source=pair.detail_source,
            )
        return evidence

    async def completed_summary(self, scan_id: UUID) -> SimilarityScanRunSummary | None:
        async with self._database.sessions() as session:
            record = await session.get(SimilarityScanRecord, scan_id)
        if record is None or record.status != "completed" or record.completed_at is None:
            return None
        return SimilarityScanRunSummary(
            id=record.id,
            parameters=self._parameters(record),
            asset_count=record.asset_count,
            candidate_count=record.candidate_count,
            match_count=record.match_count,
            result_limit_reached=record.result_limit_reached,
            completed_at=record.completed_at,
            pair_evidence_pruned_at=getattr(record, "pair_evidence_pruned_at", None),
        )

    async def latest_completed(self) -> SimilarityScanSnapshot | None:
        statement = (
            select(SimilarityScanRecord)
            .where(
                SimilarityScanRecord.status == "completed",
                SimilarityScanRecord.config_fingerprint == SEARCH_CONFIG_FINGERPRINT,
                SimilarityScanRecord.comparison_version == SIMILARITY_COMPARISON_VERSION,
                SimilarityScanRecord.grouping_version == SIMILARITY_GROUPING_VERSION,
            )
            .order_by(SimilarityScanRecord.completed_at.desc(), SimilarityScanRecord.id.desc())
            .limit(1)
        )
        async with self._database.sessions() as session:
            record = await session.scalar(statement)
            if (
                record is None
                or record.completed_at is None
                or getattr(record, "pair_evidence_pruned_at", None) is not None
            ):
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
                        detail_changed_percent=pair.detail_changed_percent,
                        detail_source=pair.detail_source,
                    ),
                )
                for pair in pair_records
            ),
        )

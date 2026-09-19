"""Companion-owned persistence for complete normalized visual evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.immich import ImmichAsset
from companion.models import (
    AssetRecord,
    AssetSimilarityDetailFeatureRecord,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_bounded_state import (
    BOUNDED_CAPABILITY_VERSION,
    BOUNDED_POLICY_FINGERPRINT,
    AssetSimilarityBoundedStateRecord,
    SourceAlphaState,
    synchronized_source_identity,
)
from companion.similarity_detail import DETAIL_FEATURE_VERSION
from companion.similarity_features import VisualFeatureResult
from companion.similarity_generation import SimilarityEvidenceEpochRepository
from companion.similarity_search_features import (
    SEARCH_CONFIG_FINGERPRINT,
    SEARCH_FEATURE_VERSION,
    SEARCH_MODEL_VERSION,
    search_source_identity,
)


class SimilaritySearchRepository:
    """Keep search fingerprints separate from original-integrity evidence."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database
        self._evidence_epoch = SimilarityEvidenceEpochRepository(database)

    async def current_evidence_epoch(self) -> int:
        return await self._evidence_epoch.capture_epoch()

    @staticmethod
    def _current():
        feature = AssetSimilaritySearchFeatureRecord
        asset = AssetRecord
        return and_(
            feature.asset_id.is_not(None),
            feature.model_version == SEARCH_MODEL_VERSION,
            feature.feature_version == SEARCH_FEATURE_VERSION,
            feature.config_fingerprint == SEARCH_CONFIG_FINGERPRINT,
            feature.source_file_modified_at == asset.file_modified_at,
            feature.source_file_size_bytes.is_not_distinct_from(asset.file_size_bytes),
            feature.source_checksum.is_not_distinct_from(asset.checksum),
        )

    @staticmethod
    def _complete_current():
        detail = AssetSimilarityDetailFeatureRecord
        search = AssetSimilaritySearchFeatureRecord
        return and_(
            SimilaritySearchRepository._current(),
            detail.asset_id == search.asset_id,
            detail.source_identity == search.source_identity,
            detail.feature_version == DETAIL_FEATURE_VERSION,
        )

    @staticmethod
    def _state_current():
        state = AssetSimilarityBoundedStateRecord
        asset = AssetRecord
        return and_(
            state.asset_id.is_not(None),
            state.model_version == SEARCH_MODEL_VERSION,
            state.feature_version == SEARCH_FEATURE_VERSION,
            state.config_fingerprint == SEARCH_CONFIG_FINGERPRINT,
            state.capability_version == BOUNDED_CAPABILITY_VERSION,
            state.policy_fingerprint == BOUNDED_POLICY_FINGERPRINT,
            state.source_file_modified_at == asset.file_modified_at,
            state.source_file_size_bytes.is_not_distinct_from(asset.file_size_bytes),
            state.source_checksum.is_not_distinct_from(asset.checksum),
            state.source_width.is_not_distinct_from(asset.width),
            state.source_height.is_not_distinct_from(asset.height),
        )

    @staticmethod
    def _eligible():
        return (
            AssetRecord.asset_type == "IMAGE",
            AssetRecord.is_trashed.is_(False),
            AssetRecord.is_offline.is_(False),
        )

    async def coverage(self) -> tuple[int, int, int, int, int, int]:
        current = self._complete_current()
        state_current = self._state_current()
        unavailable = and_(
            state_current,
            AssetSimilarityBoundedStateRecord.search_status == "unavailable",
        )
        missing = and_(
            AssetSimilaritySearchFeatureRecord.asset_id.is_(None),
            AssetSimilarityBoundedStateRecord.asset_id.is_(None),
        )
        statement = (
            select(
                func.count(),
                func.count().filter(current),
                func.count().filter(
                    and_(
                        current,
                        AssetSimilaritySearchFeatureRecord.fingerprint_origin == "bounded",
                    )
                ),
                func.count().filter(unavailable),
                func.count().filter(missing),
            )
            .select_from(AssetRecord)
            .outerjoin(
                AssetSimilaritySearchFeatureRecord,
                AssetSimilaritySearchFeatureRecord.asset_id == AssetRecord.id,
            )
            .outerjoin(
                AssetSimilarityBoundedStateRecord,
                AssetSimilarityBoundedStateRecord.asset_id == AssetRecord.id,
            )
            .outerjoin(
                AssetSimilarityDetailFeatureRecord,
                AssetSimilarityDetailFeatureRecord.asset_id == AssetRecord.id,
            )
            .where(*self._eligible())
        )
        async with self._database.sessions() as session:
            eligible, current_count, bounded, unavailable_count, missing_count = (
                await session.execute(statement)
            ).one()
        stale = eligible - current_count - unavailable_count - missing_count
        return (
            int(eligible),
            int(current_count),
            int(bounded),
            int(unavailable_count),
            int(missing_count),
            int(max(0, stale)),
        )

    async def list_work(
        self, *, after_asset_id: UUID | None = None, limit: int = 100
    ) -> list[UUID]:
        if limit < 1:
            raise ValueError("limit must be positive")
        current_unavailable = and_(
            self._state_current(),
            AssetSimilarityBoundedStateRecord.search_status == "unavailable",
        )
        statement = (
            select(AssetRecord.id)
            .outerjoin(
                AssetSimilaritySearchFeatureRecord,
                AssetSimilaritySearchFeatureRecord.asset_id == AssetRecord.id,
            )
            .outerjoin(
                AssetSimilarityBoundedStateRecord,
                AssetSimilarityBoundedStateRecord.asset_id == AssetRecord.id,
            )
            .outerjoin(
                AssetSimilarityDetailFeatureRecord,
                AssetSimilarityDetailFeatureRecord.asset_id == AssetRecord.id,
            )
            .where(
                *self._eligible(),
                *([AssetRecord.id > after_asset_id] if after_asset_id is not None else []),
                ~or_(self._complete_current(), current_unavailable),
            )
            .order_by(AssetRecord.id)
            .limit(limit)
        )
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

    @staticmethod
    def _state_values(
        asset: ImmichAsset,
        *,
        source_identity: str,
        alpha_state: SourceAlphaState,
        search_status: str,
        search_reason: str | None,
    ) -> dict[str, object]:
        return {
            "asset_id": asset.id,
            "model_version": SEARCH_MODEL_VERSION,
            "feature_version": SEARCH_FEATURE_VERSION,
            "config_fingerprint": SEARCH_CONFIG_FINGERPRINT,
            "capability_version": BOUNDED_CAPABILITY_VERSION,
            "policy_fingerprint": BOUNDED_POLICY_FINGERPRINT,
            "source_file_modified_at": asset.file_modified_at,
            "source_file_size_bytes": asset.file_size_bytes,
            "source_checksum": asset.checksum,
            "source_width": asset.width,
            "source_height": asset.height,
            "source_identity": source_identity,
            "alpha_state": alpha_state,
            "search_status": search_status,
            "search_reason": search_reason,
            "detail_status": None,
            "detail_reason": None,
            "detail_source_identity": None,
            "detail_feature_version": None,
            "updated_at": datetime.now(UTC),
        }

    @staticmethod
    def _source_matches(current: AssetRecord | None, asset: ImmichAsset) -> bool:
        return bool(
            current is not None
            and current.asset_type == "IMAGE"
            and not current.is_trashed
            and not current.is_offline
            and current.file_modified_at == asset.file_modified_at
            and current.file_size_bytes == asset.file_size_bytes
            and current.checksum == asset.checksum
            and current.width == asset.width
            and current.height == asset.height
        )

    async def save(
        self,
        asset: ImmichAsset,
        media_sha256: str,
        feature: VisualFeatureResult,
        *,
        origin: str = "preview",
        source_alpha_state: SourceAlphaState = "unknown_alpha",
        evidence_epoch: int | None = None,
    ) -> bool:
        """Commit only if the source and runtime evidence epoch are still current."""

        if feature.pixel_sha256 is not None:
            raise ValueError("Search evidence must not contain an exact-pixel hash")
        if origin not in {"preview", "bounded", "original"}:
            raise ValueError("Unsupported search fingerprint origin")
        expected_epoch = (
            evidence_epoch if evidence_epoch is not None else await self.current_evidence_epoch()
        )
        source_identity = search_source_identity(asset, media_sha256, origin=origin)
        values = {
            "asset_id": asset.id,
            "model_version": SEARCH_MODEL_VERSION,
            "feature_version": SEARCH_FEATURE_VERSION,
            "config_fingerprint": SEARCH_CONFIG_FINGERPRINT,
            "source_file_modified_at": asset.file_modified_at,
            "source_file_size_bytes": asset.file_size_bytes,
            "source_checksum": asset.checksum,
            "source_identity": source_identity,
            "media_sha256": media_sha256,
            "fingerprint_origin": origin,
            "width": asset.width or feature.width,
            "height": asset.height or feature.height,
            "luminance_vector": feature.luminance_vector,
            "perceptual_hash": feature.perceptual_hash,
            "color_histogram": feature.color_histogram,
            "thumbnail_sha256": feature.thumbnail_sha256,
            "analyzed_at": datetime.now(UTC),
        }
        state_values = self._state_values(
            asset,
            source_identity=source_identity,
            alpha_state=source_alpha_state,
            search_status="available",
            search_reason=None,
        )
        async with self._database.sessions() as session, session.begin():
            await self._evidence_epoch.assert_current(session, expected_epoch)
            current = await session.get(AssetRecord, asset.id, with_for_update=True)
            if not self._source_matches(current, asset):
                return False
            statement = insert(AssetSimilaritySearchFeatureRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AssetSimilaritySearchFeatureRecord.asset_id],
                    set_={
                        key: getattr(statement.excluded, key)
                        for key in values
                        if key != "asset_id"
                    },
                )
            )
            state_statement = insert(AssetSimilarityBoundedStateRecord).values(state_values)
            await session.execute(
                state_statement.on_conflict_do_update(
                    index_elements=[AssetSimilarityBoundedStateRecord.asset_id],
                    set_={
                        key: getattr(state_statement.excluded, key)
                        for key in state_values
                        if key != "asset_id"
                    },
                )
            )
        return True

    async def mark_unavailable(
        self,
        asset: ImmichAsset,
        reason: str,
        *,
        source_alpha_state: SourceAlphaState = "unknown_alpha",
        evidence_epoch: int | None = None,
    ) -> bool:
        """Persist a deterministic failure only inside the captured runtime epoch."""

        expected_epoch = (
            evidence_epoch if evidence_epoch is not None else await self.current_evidence_epoch()
        )
        values = self._state_values(
            asset,
            source_identity=synchronized_source_identity(asset),
            alpha_state=source_alpha_state,
            search_status="unavailable",
            search_reason=reason,
        )
        async with self._database.sessions() as session, session.begin():
            await self._evidence_epoch.assert_current(session, expected_epoch)
            current = await session.get(AssetRecord, asset.id, with_for_update=True)
            if not self._source_matches(current, asset):
                return False
            statement = insert(AssetSimilarityBoundedStateRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AssetSimilarityBoundedStateRecord.asset_id],
                    set_={
                        key: getattr(statement.excluded, key)
                        for key in values
                        if key != "asset_id"
                    },
                )
            )
        return True

    async def unavailable_reason(self, asset_id: UUID) -> str | None:
        statement = (
            select(AssetSimilarityBoundedStateRecord.search_reason)
            .join(AssetRecord, AssetRecord.id == AssetSimilarityBoundedStateRecord.asset_id)
            .where(
                AssetRecord.id == asset_id,
                *self._eligible(),
                self._state_current(),
                AssetSimilarityBoundedStateRecord.search_status == "unavailable",
            )
        )
        async with self._database.sessions() as session:
            return await session.scalar(statement)

    async def get(self, asset_id: UUID) -> AssetSimilaritySearchFeatureRecord | None:
        async with self._database.sessions() as session:
            return await session.get(AssetSimilaritySearchFeatureRecord, asset_id)

    async def get_many(
        self, asset_ids: list[UUID]
    ) -> dict[UUID, AssetSimilaritySearchFeatureRecord]:
        if not asset_ids:
            return {}
        statement = select(AssetSimilaritySearchFeatureRecord).where(
            AssetSimilaritySearchFeatureRecord.asset_id.in_(list(dict.fromkeys(asset_ids)))
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.asset_id: record for record in records}

    async def get_current_many(
        self, asset_ids: list[UUID]
    ) -> dict[UUID, AssetSimilaritySearchFeatureRecord]:
        """Return only current active search fingerprints for the requested assets."""

        if not asset_ids:
            return {}
        statement = (
            select(AssetSimilaritySearchFeatureRecord)
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .join(
                AssetSimilarityDetailFeatureRecord,
                AssetSimilarityDetailFeatureRecord.asset_id
                == AssetSimilaritySearchFeatureRecord.asset_id,
            )
            .where(
                AssetSimilaritySearchFeatureRecord.asset_id.in_(
                    list(dict.fromkeys(asset_ids))
                ),
                *self._eligible(),
                self._complete_current(),
            )
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.asset_id: record for record in records}

    async def has_current(self, asset_id: UUID) -> bool:
        statement = (
            select(AssetSimilaritySearchFeatureRecord.asset_id)
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .join(
                AssetSimilarityDetailFeatureRecord,
                AssetSimilarityDetailFeatureRecord.asset_id
                == AssetSimilaritySearchFeatureRecord.asset_id,
            )
            .where(AssetRecord.id == asset_id, *self._eligible(), self._complete_current())
        )
        async with self._database.sessions() as session:
            return await session.scalar(statement) is not None

    async def count_current(self) -> int:
        statement = (
            select(func.count())
            .select_from(AssetSimilaritySearchFeatureRecord)
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .join(
                AssetSimilarityDetailFeatureRecord,
                AssetSimilarityDetailFeatureRecord.asset_id
                == AssetSimilaritySearchFeatureRecord.asset_id,
            )
            .where(*self._eligible(), self._complete_current())
        )
        async with self._database.sessions() as session:
            return int(await session.scalar(statement) or 0)

    async def list_current(self) -> list[AssetSimilaritySearchFeatureRecord]:
        statement = (
            select(AssetSimilaritySearchFeatureRecord)
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .join(
                AssetSimilarityDetailFeatureRecord,
                AssetSimilarityDetailFeatureRecord.asset_id
                == AssetSimilaritySearchFeatureRecord.asset_id,
            )
            .where(*self._eligible(), self._complete_current())
            .order_by(AssetSimilaritySearchFeatureRecord.asset_id)
        )
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

"""Companion-owned persistence for preview search evidence only."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.immich import ImmichAsset
from companion.models import AssetRecord, AssetSimilaritySearchFeatureRecord
from companion.similarity_features import VisualFeatureResult
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
    def _eligible():
        return (
            AssetRecord.asset_type == "IMAGE",
            AssetRecord.is_trashed.is_(False),
            AssetRecord.is_offline.is_(False),
        )

    async def coverage(self) -> tuple[int, int, int, int]:
        statement = (
            select(
                func.count(),
                func.count().filter(self._current()),
                func.count().filter(AssetSimilaritySearchFeatureRecord.asset_id.is_(None)),
            )
            .select_from(AssetRecord)
            .outerjoin(
                AssetSimilaritySearchFeatureRecord,
                AssetSimilaritySearchFeatureRecord.asset_id == AssetRecord.id,
            )
            .where(*self._eligible())
        )
        async with self._database.sessions() as session:
            eligible, current, missing = (await session.execute(statement)).one()
        return int(eligible), int(current), int(missing), int(eligible - current - missing)

    async def list_work(
        self, *, after_asset_id: UUID | None = None, limit: int = 100
    ) -> list[UUID]:
        if limit < 1:
            raise ValueError("limit must be positive")
        statement = (
            select(AssetRecord.id)
            .outerjoin(
                AssetSimilaritySearchFeatureRecord,
                AssetSimilaritySearchFeatureRecord.asset_id == AssetRecord.id,
            )
            .where(
                *self._eligible(),
                *([AssetRecord.id > after_asset_id] if after_asset_id is not None else []),
                or_(
                    AssetSimilaritySearchFeatureRecord.asset_id.is_(None),
                    ~self._current(),
                ),
            )
            .order_by(AssetRecord.id)
            .limit(limit)
        )
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

    async def save(
        self,
        asset: ImmichAsset,
        preview_sha256: str,
        feature: VisualFeatureResult,
    ) -> bool:
        """Commit only if the synchronized source still matches the fetched source."""

        if feature.pixel_sha256 is not None:
            raise ValueError("Search evidence must not contain an exact-pixel hash")
        values = {
            "asset_id": asset.id,
            "model_version": SEARCH_MODEL_VERSION,
            "feature_version": SEARCH_FEATURE_VERSION,
            "config_fingerprint": SEARCH_CONFIG_FINGERPRINT,
            "source_file_modified_at": asset.file_modified_at,
            "source_file_size_bytes": asset.file_size_bytes,
            "source_checksum": asset.checksum,
            "source_identity": search_source_identity(asset, preview_sha256),
            "preview_sha256": preview_sha256,
            "width": asset.width or feature.width,
            "height": asset.height or feature.height,
            "luminance_vector": feature.luminance_vector,
            "perceptual_hash": feature.perceptual_hash,
            "color_histogram": feature.color_histogram,
            "thumbnail_sha256": feature.thumbnail_sha256,
            "analyzed_at": datetime.now(UTC),
        }
        async with self._database.sessions() as session, session.begin():
            current = await session.get(AssetRecord, asset.id, with_for_update=True)
            if (
                current is None
                or current.asset_type != "IMAGE"
                or current.is_trashed
                or current.is_offline
                or current.file_modified_at != asset.file_modified_at
                or current.file_size_bytes != asset.file_size_bytes
                or current.checksum != asset.checksum
            ):
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
        return True

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

    async def has_current(self, asset_id: UUID) -> bool:
        statement = (
            select(AssetSimilaritySearchFeatureRecord.asset_id)
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .where(AssetRecord.id == asset_id, *self._eligible(), self._current())
        )
        async with self._database.sessions() as session:
            return await session.scalar(statement) is not None

    async def count_current(self) -> int:
        statement = (
            select(func.count())
            .select_from(AssetSimilaritySearchFeatureRecord)
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .where(*self._eligible(), self._current())
        )
        async with self._database.sessions() as session:
            return int(await session.scalar(statement) or 0)

    async def list_current(self) -> list[AssetSimilaritySearchFeatureRecord]:
        statement = (
            select(AssetSimilaritySearchFeatureRecord)
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .where(*self._eligible(), self._current())
            .order_by(AssetSimilaritySearchFeatureRecord.asset_id)
        )
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

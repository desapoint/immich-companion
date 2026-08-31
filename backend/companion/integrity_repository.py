"""Persistence boundary for the latest successful asset-integrity reports."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.immich import ImmichAsset
from companion.integrity import ANALYZER_VERSION, FileIntegrityResult
from companion.integrity_schema import AssetIntegrityReport, IntegrityFreshness
from companion.models import AssetIntegrityReportRecord, AssetRecord, AssetSimilarityFeatureRecord
from companion.similarity_features import (
    SIMILARITY_FEATURE_VERSION,
    SIMILARITY_MODEL_VERSION,
    VisualFeatureResult,
)


def source_file_size(asset: ImmichAsset) -> int | None:
    return asset.file_size_bytes


def report_freshness(
    record: AssetIntegrityReportRecord | None,
    asset: ImmichAsset,
) -> IntegrityFreshness:
    if record is None:
        return "missing"
    if record.analyzer_version != ANALYZER_VERSION:
        return "stale"
    if asset.library_id is None and record.source_checksum != asset.checksum:
        return "stale"
    if record.source_file_modified_at != asset.file_modified_at:
        return "stale"
    live_size = source_file_size(asset)
    if live_size is None:
        return "stale"
    if record.source_file_size_bytes != live_size:
        return "stale"
    return "current"


def similarity_feature_freshness(
    record: AssetSimilarityFeatureRecord | None,
    asset: ImmichAsset,
) -> IntegrityFreshness:
    if record is None:
        return "missing"
    if (
        record.model_version != SIMILARITY_MODEL_VERSION
        or record.feature_version != SIMILARITY_FEATURE_VERSION
    ):
        return "stale"
    live_size = source_file_size(asset)
    if live_size is None or record.source_file_size_bytes != live_size:
        return "stale"
    if record.source_file_modified_at != asset.file_modified_at:
        return "stale"
    return "current"


def public_report(record: AssetIntegrityReportRecord) -> AssetIntegrityReport:
    detected_format = "unknown" if record.detected_format == "other" else record.detected_format
    return AssetIntegrityReport(
        asset_id=record.asset_id,
        analyzer_version=record.analyzer_version,
        byte_size=record.byte_size,
        sha1_hex=record.sha1_hex,
        sha256_hex=record.sha256_hex,
        detected_format=detected_format,  # type: ignore[arg-type]
        format_matches_declared=record.format_matches_declared,
        classification=record.classification,  # type: ignore[arg-type]
        structurally_valid=record.structurally_valid,
        container_valid=record.container_valid,
        decode_supported=record.decode_supported,
        decode_valid=record.decode_valid,
        decoded_width=record.decoded_width,
        decoded_height=record.decoded_height,
        dimensions_match_immich=record.dimensions_match_immich,
        jpeg_eoi_offset=record.jpeg_eoi_offset,
        trailing_byte_count=record.trailing_byte_count,
        immich_checksum_match=record.immich_checksum_match,
        issues=list(record.issues or []),
        analyzed_at=record.analyzed_at,
    )


class IntegrityRepository:
    """Read and atomically replace companion-owned integrity facts."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def get(self, asset_id: UUID) -> AssetIntegrityReportRecord | None:
        async with self._database.sessions() as session:
            return await session.get(AssetIntegrityReportRecord, asset_id)

    async def get_many(self, asset_ids: list[UUID]) -> dict[UUID, AssetIntegrityReportRecord]:
        if not asset_ids:
            return {}
        statement = select(AssetIntegrityReportRecord).where(
            AssetIntegrityReportRecord.asset_id.in_(list(dict.fromkeys(asset_ids)))
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.asset_id: record for record in records}

    async def get_similarity_feature(
        self,
        asset_id: UUID,
    ) -> AssetSimilarityFeatureRecord | None:
        async with self._database.sessions() as session:
            return await session.get(AssetSimilarityFeatureRecord, asset_id)

    async def get_similarity_features(
        self,
        asset_ids: list[UUID],
    ) -> dict[UUID, AssetSimilarityFeatureRecord]:
        if not asset_ids:
            return {}
        statement = select(AssetSimilarityFeatureRecord).where(
            AssetSimilarityFeatureRecord.asset_id.in_(list(dict.fromkeys(asset_ids)))
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.asset_id: record for record in records}

    async def list_current_similarity_features(self) -> list[AssetSimilarityFeatureRecord]:
        """Return current cached image features in stable order for bounded discovery."""

        statement = (
            select(AssetSimilarityFeatureRecord)
            .join(AssetRecord, AssetRecord.id == AssetSimilarityFeatureRecord.asset_id)
            .where(
                AssetRecord.asset_type == "IMAGE",
                AssetRecord.is_trashed.is_(False),
                AssetRecord.is_offline.is_(False),
                AssetRecord.file_size_bytes.is_not(None),
                AssetSimilarityFeatureRecord.model_version == SIMILARITY_MODEL_VERSION,
                AssetSimilarityFeatureRecord.feature_version == SIMILARITY_FEATURE_VERSION,
                AssetSimilarityFeatureRecord.source_file_modified_at
                == AssetRecord.file_modified_at,
                AssetSimilarityFeatureRecord.source_file_size_bytes
                == AssetRecord.file_size_bytes,
            )
            .order_by(AssetSimilarityFeatureRecord.asset_id)
        )
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

    async def save(
        self,
        asset: ImmichAsset,
        result: FileIntegrityResult,
        visual_feature: VisualFeatureResult | None = None,
    ) -> AssetIntegrityReport:
        values = {
            "asset_id": asset.id,
            "analyzer_version": result.analyzer_version,
            "source_checksum": asset.checksum,
            "source_file_modified_at": asset.file_modified_at,
            "source_file_size_bytes": result.byte_size,
            "source_mime_type": asset.original_mime_type,
            "byte_size": result.byte_size,
            "sha1_hex": result.sha1_hex,
            "sha256_hex": result.sha256_hex,
            "detected_format": result.detected_format,
            "format_matches_declared": result.format_matches_declared,
            "classification": result.classification,
            "structurally_valid": result.structurally_valid,
            "container_valid": result.container_valid,
            "decode_supported": result.decode_supported,
            "decode_valid": result.decode_valid,
            "decoded_width": result.decoded_width,
            "decoded_height": result.decoded_height,
            "dimensions_match_immich": result.dimensions_match_immich,
            "jpeg_eoi_offset": result.jpeg_eoi_offset,
            "trailing_byte_count": result.trailing_byte_count,
            "immich_checksum_match": result.immich_checksum_match,
            "issues": list(result.issues),
            "analyzed_at": datetime.now(UTC),
        }
        async with self._database.sessions() as session, session.begin():
            statement = insert(AssetIntegrityReportRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AssetIntegrityReportRecord.asset_id],
                    set_={
                        key: getattr(statement.excluded, key) for key in values if key != "asset_id"
                    },
                )
            )
            if visual_feature is None:
                await session.execute(
                    delete(AssetSimilarityFeatureRecord).where(
                        AssetSimilarityFeatureRecord.asset_id == asset.id
                    )
                )
            else:
                feature_values = {
                    "asset_id": asset.id,
                    "model_version": visual_feature.model_version,
                    "feature_version": visual_feature.feature_version,
                    "source_file_modified_at": asset.file_modified_at,
                    "source_file_size_bytes": result.byte_size,
                    "source_sha256": result.sha256_hex,
                    "width": visual_feature.width,
                    "height": visual_feature.height,
                    "luminance_vector": visual_feature.luminance_vector,
                    "perceptual_hash": visual_feature.perceptual_hash,
                    "color_histogram": visual_feature.color_histogram,
                    "thumbnail_sha256": visual_feature.thumbnail_sha256,
                    "pixel_normalization_version": visual_feature.pixel_normalization_version,
                    "pixel_sha256": visual_feature.pixel_sha256,
                    "bit_depth": visual_feature.bit_depth,
                    "channel_count": visual_feature.channel_count,
                    "has_alpha": visual_feature.has_alpha,
                    "color_space": visual_feature.color_space,
                    "orientation": visual_feature.orientation,
                    "icc_profile_present": visual_feature.icc_profile_present,
                    "has_exif": visual_feature.has_exif,
                    "has_capture_time": visual_feature.has_capture_time,
                    "has_camera_info": visual_feature.has_camera_info,
                    "has_gps": visual_feature.has_gps,
                    "has_orientation_metadata": visual_feature.has_orientation_metadata,
                    "metadata_richness": visual_feature.metadata_richness,
                    "analyzed_at": datetime.now(UTC),
                }
                feature_statement = insert(AssetSimilarityFeatureRecord).values(feature_values)
                await session.execute(
                    feature_statement.on_conflict_do_update(
                        index_elements=[AssetSimilarityFeatureRecord.asset_id],
                        set_={
                            key: getattr(feature_statement.excluded, key)
                            for key in feature_values
                            if key != "asset_id"
                        },
                    )
                )
        record = await self.get(asset.id)
        assert record is not None
        return public_report(record)

    async def exact_hash_matches(
        self,
        byte_size: int,
        sha256_hex: str,
    ) -> list[UUID]:
        """Return stable exact-hash candidates for the later dedupe workflow."""

        statement = (
            select(AssetIntegrityReportRecord.asset_id)
            .where(
                AssetIntegrityReportRecord.byte_size == byte_size,
                AssetIntegrityReportRecord.sha256_hex == sha256_hex,
            )
            .order_by(AssetIntegrityReportRecord.asset_id)
        )
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

"""Persistence boundary for the latest successful asset-integrity reports."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.immich import ImmichAsset
from companion.integrity import ANALYZER_VERSION, FileIntegrityResult
from companion.integrity_schema import AssetIntegrityReport, IntegrityFreshness
from companion.models import AssetIntegrityReportRecord


def source_file_size(asset: ImmichAsset) -> int | None:
    value = (asset.exif_info or {}).get("fileSizeInByte")
    return value if isinstance(value, int) and value >= 0 else None


def report_freshness(
    record: AssetIntegrityReportRecord | None,
    asset: ImmichAsset,
) -> IntegrityFreshness:
    if record is None:
        return "missing"
    if record.analyzer_version != ANALYZER_VERSION:
        return "stale"
    if asset.checksum is not None:
        return "current" if record.source_checksum == asset.checksum else "stale"
    if record.source_file_modified_at != asset.file_modified_at:
        return "stale"
    live_size = source_file_size(asset)
    if live_size is not None and record.source_file_size_bytes != live_size:
        return "stale"
    return "current"


def public_report(record: AssetIntegrityReportRecord) -> AssetIntegrityReport:
    return AssetIntegrityReport(
        asset_id=record.asset_id,
        analyzer_version=record.analyzer_version,
        byte_size=record.byte_size,
        sha1_hex=record.sha1_hex,
        sha256_hex=record.sha256_hex,
        detected_format=record.detected_format,  # type: ignore[arg-type]
        classification=record.classification,  # type: ignore[arg-type]
        structurally_valid=record.structurally_valid,
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

    async def save(
        self,
        asset: ImmichAsset,
        result: FileIntegrityResult,
    ) -> AssetIntegrityReport:
        values = {
            "asset_id": asset.id,
            "analyzer_version": result.analyzer_version,
            "source_checksum": asset.checksum,
            "source_file_modified_at": asset.file_modified_at,
            "source_file_size_bytes": source_file_size(asset),
            "source_mime_type": asset.original_mime_type,
            "byte_size": result.byte_size,
            "sha1_hex": result.sha1_hex,
            "sha256_hex": result.sha256_hex,
            "detected_format": result.detected_format,
            "classification": result.classification,
            "structurally_valid": result.structurally_valid,
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
                        key: getattr(statement.excluded, key)
                        for key in values
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

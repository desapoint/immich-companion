"""Database-side candidate discovery for cross-source duplicate analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, bindparam, func, select, update

from companion.database import DatabaseManager
from companion.immich import ImmichAsset
from companion.models import AssetRecord


@dataclass(frozen=True, slots=True)
class CrossSourceCandidateAsset:
    id: UUID
    library_id: UUID | None
    asset_type: str
    original_file_name: str
    original_mime_type: str | None
    immich_checksum: str | None
    file_size_bytes: int
    file_modified_at: datetime
    width: int | None
    height: int | None
    duration: int | None
    is_offline: bool


@dataclass(frozen=True, slots=True)
class ExternalFingerprintTarget:
    id: UUID
    is_offline: bool
    file_size_bytes: int | None
    file_modified_at: datetime


class DuplicateRepository:
    """Persist cheap size facts and return only cross-source candidate groups."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def update_file_sizes(self, assets: list[ImmichAsset]) -> int:
        values = [
            {
                "candidate_id": asset.id,
                "candidate_size": asset.file_size_bytes,
                "candidate_modified_at": asset.file_modified_at,
                "candidate_offline": asset.is_offline,
            }
            for asset in assets
            if not asset.is_trashed
        ]
        if not values:
            return 0
        statement = (
            update(AssetRecord.__table__)
            .where(AssetRecord.__table__.c.id == bindparam("candidate_id"))
            .values(
                file_size_bytes=func.coalesce(
                    bindparam("candidate_size"),
                    AssetRecord.__table__.c.file_size_bytes,
                ),
                file_modified_at=bindparam("candidate_modified_at"),
                is_offline=bindparam("candidate_offline"),
            )
        )
        async with self._database.sessions() as session, session.begin():
            await session.execute(statement, values)
        return len(values)

    async def update_file_size(self, asset_id: UUID, file_size_bytes: int) -> None:
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                update(AssetRecord)
                .where(AssetRecord.id == asset_id)
                .values(file_size_bytes=file_size_bytes)
            )

    @staticmethod
    def candidate_statement():
        candidate_keys = (
            select(AssetRecord.file_size_bytes, AssetRecord.asset_type)
            .where(
                AssetRecord.is_trashed.is_(False),
                AssetRecord.file_size_bytes.is_not(None),
            )
            .group_by(AssetRecord.file_size_bytes, AssetRecord.asset_type)
            .having(
                func.bool_or(AssetRecord.library_id.is_(None)),
                func.bool_or(AssetRecord.library_id.is_not(None)),
            )
            .cte("cross_source_candidate_keys")
        )
        return (
            select(
                AssetRecord.id,
                AssetRecord.library_id,
                AssetRecord.asset_type,
                AssetRecord.original_file_name,
                AssetRecord.original_mime_type,
                AssetRecord.checksum,
                AssetRecord.file_size_bytes,
                AssetRecord.file_modified_at,
                AssetRecord.width,
                AssetRecord.height,
                AssetRecord.duration,
                AssetRecord.is_offline,
            )
            .join(
                candidate_keys,
                and_(
                    candidate_keys.c.file_size_bytes == AssetRecord.file_size_bytes,
                    candidate_keys.c.asset_type == AssetRecord.asset_type,
                ),
            )
            .where(AssetRecord.is_trashed.is_(False))
            .order_by(AssetRecord.file_size_bytes, AssetRecord.asset_type, AssetRecord.id)
        )

    async def cross_source_candidates(self) -> list[CrossSourceCandidateAsset]:
        async with self._database.sessions() as session:
            rows = (await session.execute(self.candidate_statement())).all()
        return [
            CrossSourceCandidateAsset(
                id=row.id,
                library_id=row.library_id,
                asset_type=row.asset_type,
                original_file_name=row.original_file_name,
                original_mime_type=row.original_mime_type,
                immich_checksum=row.checksum,
                file_size_bytes=row.file_size_bytes,
                file_modified_at=row.file_modified_at,
                width=row.width,
                height=row.height,
                duration=row.duration,
                is_offline=row.is_offline,
            )
            for row in rows
        ]

    async def external_fingerprint_targets(self) -> list[ExternalFingerprintTarget]:
        statement = (
            select(
                AssetRecord.id,
                AssetRecord.is_offline,
                AssetRecord.file_size_bytes,
                AssetRecord.file_modified_at,
            )
            .where(
                AssetRecord.is_trashed.is_(False),
                AssetRecord.library_id.is_not(None),
            )
            .order_by(AssetRecord.id)
        )
        async with self._database.sessions() as session:
            rows = (await session.execute(statement)).all()
        return [
            ExternalFingerprintTarget(
                id=row.id,
                is_offline=row.is_offline,
                file_size_bytes=row.file_size_bytes,
                file_modified_at=row.file_modified_at,
            )
            for row in rows
        ]

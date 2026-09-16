"""Persist authoritative Immich duplicate-group snapshots for fast local reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Text, Uuid, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from companion.database import DatabaseManager
from companion.immich import ImmichDuplicateGroup
from companion.models import AssetRecord, Base

SNAPSHOT_STATE_ID = 1
WRITE_BATCH_SIZE = 1_000


class ImmichDuplicateSnapshotAssetMissingError(RuntimeError):
    """Raised when a fetched duplicate snapshot references unsynchronized assets."""


class ImmichDuplicateSyncStateRecord(Base):
    """Singleton metadata describing the last published Immich duplicate snapshot."""

    __tablename__ = "immich_duplicate_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    authoritative_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    group_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImmichDuplicateGroupRecord(Base):
    """One group in the last successfully published Immich duplicate snapshot."""

    __tablename__ = "immich_duplicate_groups"

    provider_group_id: Mapped[str] = mapped_column(Text, primary_key=True)
    sync_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ImmichDuplicateGroupMemberRecord(Base):
    """Ordered local asset membership for one persisted Immich duplicate group."""

    __tablename__ = "immich_duplicate_group_members"

    provider_group_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("immich_duplicate_groups.provider_group_id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    __table_args__ = (
        Index("ix_immich_duplicate_group_members_asset_id", asset_id),
        Index("ix_immich_duplicate_group_members_group_position", provider_group_id, position),
    )


@dataclass(frozen=True, slots=True)
class ImmichDuplicateSnapshotGroup:
    provider_group_id: str
    asset_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ImmichDuplicateSnapshotMetadata:
    authoritative_generation: int
    group_count: int
    member_count: int
    last_success_at: datetime | None


class ImmichDuplicateRepository:
    """Read and atomically replace the local projection of Immich duplicate groups."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def metadata(self) -> ImmichDuplicateSnapshotMetadata:
        async with self._database.sessions() as session:
            state = await session.get(ImmichDuplicateSyncStateRecord, SNAPSHOT_STATE_ID)
            if state is None:
                return ImmichDuplicateSnapshotMetadata(0, 0, 0, None)
            return ImmichDuplicateSnapshotMetadata(
                authoritative_generation=state.authoritative_generation,
                group_count=state.group_count,
                member_count=state.member_count,
                last_success_at=state.last_success_at,
            )

    async def groups(self) -> list[ImmichDuplicateSnapshotGroup]:
        async with self._database.sessions() as session:
            rows = list(
                (
                    await session.execute(
                        select(
                            ImmichDuplicateGroupMemberRecord.provider_group_id,
                            ImmichDuplicateGroupMemberRecord.asset_id,
                        ).order_by(
                            ImmichDuplicateGroupMemberRecord.provider_group_id,
                            ImmichDuplicateGroupMemberRecord.position,
                        )
                    )
                ).all()
            )
        grouped: dict[str, list[UUID]] = {}
        for provider_group_id, asset_id in rows:
            grouped.setdefault(provider_group_id, []).append(asset_id)
        return [
            ImmichDuplicateSnapshotGroup(provider_group_id, tuple(asset_ids))
            for provider_group_id, asset_ids in grouped.items()
            if len(asset_ids) >= 2
        ]

    async def replace_snapshot(
        self,
        groups: list[ImmichDuplicateGroup],
    ) -> ImmichDuplicateSnapshotMetadata:
        """Publish a complete fetched snapshot in one transaction or leave the old one intact."""

        normalized: dict[str, list[UUID]] = {}
        for group in groups:
            provider_group_id = str(group.duplicate_id)
            members = list(dict.fromkeys(asset.id for asset in group.assets))
            if len(members) >= 2:
                normalized[provider_group_id] = members

        asset_ids = {asset_id for members in normalized.values() for asset_id in members}
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(ImmichDuplicateSyncStateRecord)
                .where(ImmichDuplicateSyncStateRecord.id == SNAPSHOT_STATE_ID)
                .with_for_update()
            )
            if state is None:
                state = ImmichDuplicateSyncStateRecord(id=SNAPSHOT_STATE_ID)
                session.add(state)
                await session.flush()

            if asset_ids:
                available = set(
                    (
                        await session.scalars(
                            select(AssetRecord.id).where(
                                AssetRecord.id.in_(asset_ids),
                                AssetRecord.is_trashed.is_(False),
                            )
                        )
                    ).all()
                )
                missing = asset_ids - available
                if missing:
                    raise ImmichDuplicateSnapshotAssetMissingError(
                        "Immich duplicate synchronization references "
                        f"{len(missing)} asset(s) that are not in the synchronized local catalog. "
                        "Run asset synchronization first."
                    )

            generation = state.authoritative_generation + 1
            group_rows = [
                {
                    "provider_group_id": provider_group_id,
                    "sync_generation": generation,
                    "synced_at": now,
                }
                for provider_group_id in normalized
            ]
            member_rows = [
                {
                    "provider_group_id": provider_group_id,
                    "asset_id": asset_id,
                    "position": position,
                    "sync_generation": generation,
                }
                for provider_group_id, members in normalized.items()
                for position, asset_id in enumerate(members)
            ]

            for offset in range(0, len(group_rows), WRITE_BATCH_SIZE):
                values = group_rows[offset : offset + WRITE_BATCH_SIZE]
                statement = insert(ImmichDuplicateGroupRecord).values(values)
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[ImmichDuplicateGroupRecord.provider_group_id],
                        set_={
                            "sync_generation": statement.excluded.sync_generation,
                            "synced_at": statement.excluded.synced_at,
                        },
                    )
                )

            for offset in range(0, len(member_rows), WRITE_BATCH_SIZE):
                values = member_rows[offset : offset + WRITE_BATCH_SIZE]
                statement = insert(ImmichDuplicateGroupMemberRecord).values(values)
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[
                            ImmichDuplicateGroupMemberRecord.provider_group_id,
                            ImmichDuplicateGroupMemberRecord.asset_id,
                        ],
                        set_={
                            "position": statement.excluded.position,
                            "sync_generation": statement.excluded.sync_generation,
                        },
                    )
                )

            await session.execute(
                delete(ImmichDuplicateGroupMemberRecord).where(
                    ImmichDuplicateGroupMemberRecord.sync_generation != generation
                )
            )
            await session.execute(
                delete(ImmichDuplicateGroupRecord).where(
                    ImmichDuplicateGroupRecord.sync_generation != generation
                )
            )

            state.authoritative_generation = generation
            state.group_count = len(group_rows)
            state.member_count = len(member_rows)
            state.last_success_at = now

        return ImmichDuplicateSnapshotMetadata(
            authoritative_generation=generation,
            group_count=len(group_rows),
            member_count=len(member_rows),
            last_success_at=now,
        )

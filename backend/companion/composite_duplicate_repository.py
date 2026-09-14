"""Persist the provider-neutral composite duplicate projection for fast local reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    delete,
    exists,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from companion.database import DatabaseManager
from companion.discovery.base import DiscoveredGroup, DiscoveryEvidence
from companion.duplicate_identity import member_set_key, stable_group_key
from companion.group_decision import DiscoverySource
from companion.models import AssetRecord, Base
from companion.similarity_grouping import SimilarityAdmissionEvidence, ValidatedSimilarityGroup

SNAPSHOT_STATE_ID = 1
WRITE_BATCH_SIZE = 1_000


class CompositeDuplicateSnapshotAssetMissingError(RuntimeError):
    """Raised when a composite snapshot references assets missing from the local catalog."""


class CompositeDuplicateSyncStateRecord(Base):
    """Singleton metadata for the last published composite duplicate snapshot."""

    __tablename__ = "composite_duplicate_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    authoritative_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    group_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompositeDuplicateGroupRecord(Base):
    """One provider-neutral duplicate group in the published projection."""

    __tablename__ = "composite_duplicate_groups"

    group_id: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    discovery_source: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    provider_group_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stable_group_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    member_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    reclaimable_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    oldest_taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    newest_taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    similarity_validation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sync_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class CompositeDuplicateGroupMemberRecord(Base):
    """Ordered local asset membership for one composite group."""

    __tablename__ = "composite_duplicate_group_members"

    group_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("composite_duplicate_groups.group_id", ondelete="CASCADE"),
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
        Index("ix_composite_duplicate_group_members_asset_id", asset_id),
        Index("ix_composite_duplicate_group_members_group_position", group_id, position),
    )


class CompositeDuplicateGroupEvidenceRecord(Base):
    """Provider provenance retained when exact member sets coalesce."""

    __tablename__ = "composite_duplicate_group_evidence"

    group_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("composite_duplicate_groups.group_id", ondelete="CASCADE"),
        primary_key=True,
    )
    discovery_source: Mapped[str] = mapped_column(String(48), primary_key=True)
    provider_group_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    sync_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


@dataclass(frozen=True, slots=True)
class CompositeDuplicateSnapshotMetadata:
    authoritative_generation: int
    group_count: int
    member_count: int
    evidence_count: int
    last_success_at: datetime | None


@dataclass(frozen=True, slots=True)
class CompositeDuplicateGroupIdentity:
    group_id: str
    discovery_source: DiscoverySource
    provider_group_id: str | None
    stable_group_key: str
    member_set_key: str
    member_fingerprint: str


@dataclass(frozen=True, slots=True)
class CompositeDuplicateSnapshotGroup:
    group_id: str
    discovery_source: DiscoverySource
    provider_group_id: str | None
    asset_ids: tuple[UUID, ...]
    provider_metadata: dict[str, str]
    evidence: tuple[DiscoveryEvidence, ...]
    similarity_validation: ValidatedSimilarityGroup | None


@dataclass(frozen=True, slots=True)
class CompositeDuplicateSnapshotPage:
    groups: list[CompositeDuplicateSnapshotGroup]
    total: int
    page: int
    page_size: int
    pages: int


def _group_projection_summary(group: DiscoveredGroup) -> dict[str, Any]:
    """Return small SQL-sortable values without retaining duplicate group objects."""

    sizes = [asset.file_size_bytes for asset in group.assets]
    reclaimable_bytes = (
        sum(size for size in sizes if size is not None)
        - max(size for size in sizes if size is not None)
        if sizes and all(size is not None for size in sizes)
        else None
    )
    capture_times = [asset.file_created_at for asset in group.assets]
    return {
        "member_count": len(group.assets),
        "reclaimable_bytes": reclaimable_bytes,
        "similarity_score": (
            group.similarity_validation.minimum_similarity_percent
            if group.similarity_validation is not None
            else None
        ),
        "oldest_taken_at": min(capture_times) if capture_times else None,
        "newest_taken_at": max(capture_times) if capture_times else None,
    }


def _validation_payload(validation: ValidatedSimilarityGroup | None) -> dict[str, Any] | None:
    if validation is None:
        return None
    return {
        "asset_ids": [str(asset_id) for asset_id in validation.asset_ids],
        "anchor_asset_id": str(validation.anchor_asset_id),
        "validation_mode": validation.validation_mode,
        "minimum_similarity_percent": validation.minimum_similarity_percent,
        "maximum_similarity_percent": validation.maximum_similarity_percent,
        "pair_count": validation.pair_count,
        "admission_evidence": [
            {
                "asset_id": str(item.asset_id),
                "admitted_by_asset_id": (
                    str(item.admitted_by_asset_id) if item.admitted_by_asset_id else None
                ),
                "admission_similarity_percent": item.admission_similarity_percent,
                "best_group_match_asset_id": (
                    str(item.best_group_match_asset_id) if item.best_group_match_asset_id else None
                ),
                "best_group_match_similarity_percent": item.best_group_match_similarity_percent,
                "link_depth": item.link_depth,
            }
            for item in validation.admission_evidence
        ],
    }


def _validation_from_payload(payload: dict[str, Any] | None) -> ValidatedSimilarityGroup | None:
    if payload is None:
        return None
    return ValidatedSimilarityGroup(
        asset_ids=tuple(UUID(value) for value in payload["asset_ids"]),
        anchor_asset_id=UUID(payload["anchor_asset_id"]),
        validation_mode=payload["validation_mode"],
        minimum_similarity_percent=float(payload["minimum_similarity_percent"]),
        maximum_similarity_percent=float(payload["maximum_similarity_percent"]),
        pair_count=int(payload["pair_count"]),
        admission_evidence=tuple(
            SimilarityAdmissionEvidence(
                asset_id=UUID(item["asset_id"]),
                admitted_by_asset_id=(
                    UUID(item["admitted_by_asset_id"]) if item.get("admitted_by_asset_id") else None
                ),
                admission_similarity_percent=(
                    float(item["admission_similarity_percent"])
                    if item.get("admission_similarity_percent") is not None
                    else None
                ),
                best_group_match_asset_id=(
                    UUID(item["best_group_match_asset_id"])
                    if item.get("best_group_match_asset_id")
                    else None
                ),
                best_group_match_similarity_percent=(
                    float(item["best_group_match_similarity_percent"])
                    if item.get("best_group_match_similarity_percent") is not None
                    else None
                ),
                link_depth=int(item["link_depth"]),
            )
            for item in payload.get("admission_evidence", [])
        ),
    )


class CompositeDuplicateRepository:
    """Read and atomically replace the local composite duplicate projection."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def metadata(self) -> CompositeDuplicateSnapshotMetadata:
        async with self._database.sessions() as session:
            state = await session.get(CompositeDuplicateSyncStateRecord, SNAPSHOT_STATE_ID)
            if state is None:
                return CompositeDuplicateSnapshotMetadata(0, 0, 0, 0, None)
            return CompositeDuplicateSnapshotMetadata(
                authoritative_generation=state.authoritative_generation,
                group_count=state.group_count,
                member_count=state.member_count,
                evidence_count=state.evidence_count,
                last_success_at=state.last_success_at,
            )

    async def identities(
        self,
        *,
        group_ids: list[str] | None = None,
        stable_group_keys: list[str] | None = None,
    ) -> list[CompositeDuplicateGroupIdentity]:
        """Resolve persisted group identity without hydrating members or evidence."""

        ids = list(dict.fromkeys(group_ids or []))
        keys = list(dict.fromkeys(stable_group_keys or []))
        if not ids and not keys:
            return []
        resolved: dict[str, CompositeDuplicateGroupRecord] = {}
        async with self._database.sessions() as session:
            for values, column in (
                (ids, CompositeDuplicateGroupRecord.group_id),
                (keys, CompositeDuplicateGroupRecord.stable_group_key),
            ):
                for offset in range(0, len(values), WRITE_BATCH_SIZE):
                    rows = list(
                        (
                            await session.execute(
                                select(CompositeDuplicateGroupRecord).where(
                                    column.in_(values[offset : offset + WRITE_BATCH_SIZE])
                                )
                            )
                        ).scalars()
                    )
                    resolved.update((row.group_id, row) for row in rows)
        return [
            CompositeDuplicateGroupIdentity(
                group_id=row.group_id,
                discovery_source=DiscoverySource(row.discovery_source),
                provider_group_id=row.provider_group_id,
                stable_group_key=row.stable_group_key,
                member_set_key=row.member_fingerprint,
                member_fingerprint=row.member_fingerprint,
            )
            for row in resolved.values()
        ]

    async def groups_by_ids(self, group_ids: list[str]) -> list[CompositeDuplicateSnapshotGroup]:
        """Load complete snapshots only for explicitly requested group IDs."""

        unique_ids = list(dict.fromkeys(group_ids))
        if not unique_ids:
            return []
        async with self._database.sessions() as session:
            group_rows = list(
                (
                    await session.execute(
                        select(CompositeDuplicateGroupRecord)
                        .where(CompositeDuplicateGroupRecord.group_id.in_(unique_ids))
                        .order_by(CompositeDuplicateGroupRecord.position)
                    )
                ).scalars()
            )
            found_ids = [row.group_id for row in group_rows]
            if found_ids:
                member_rows = list(
                    (
                        await session.execute(
                            select(
                                CompositeDuplicateGroupMemberRecord.group_id,
                                CompositeDuplicateGroupMemberRecord.asset_id,
                            )
                            .where(CompositeDuplicateGroupMemberRecord.group_id.in_(found_ids))
                            .order_by(
                                CompositeDuplicateGroupMemberRecord.group_id,
                                CompositeDuplicateGroupMemberRecord.position,
                            )
                        )
                    ).all()
                )
                evidence_rows = list(
                    (
                        await session.execute(
                            select(CompositeDuplicateGroupEvidenceRecord)
                            .where(CompositeDuplicateGroupEvidenceRecord.group_id.in_(found_ids))
                            .order_by(
                                CompositeDuplicateGroupEvidenceRecord.group_id,
                                CompositeDuplicateGroupEvidenceRecord.discovery_source,
                            )
                        )
                    ).scalars()
                )
            else:
                member_rows = []
                evidence_rows = []

        members: dict[str, list[UUID]] = {}
        for group_id, asset_id in member_rows:
            members.setdefault(group_id, []).append(asset_id)
        evidence: dict[str, list[DiscoveryEvidence]] = {}
        for row in evidence_rows:
            evidence.setdefault(row.group_id, []).append(
                DiscoveryEvidence(
                    discovery_source=DiscoverySource(row.discovery_source),
                    provider_group_id=row.provider_group_id,
                    metadata=dict(row.evidence_metadata or {}),
                )
            )
        return [
            CompositeDuplicateSnapshotGroup(
                group_id=row.group_id,
                discovery_source=DiscoverySource(row.discovery_source),
                provider_group_id=row.provider_group_id,
                asset_ids=tuple(members.get(row.group_id, [])),
                provider_metadata=dict(row.provider_metadata or {}),
                evidence=tuple(evidence.get(row.group_id, [])),
                similarity_validation=_validation_from_payload(row.similarity_validation),
            )
            for row in group_rows
            if len(members.get(row.group_id, [])) >= 2
        ]

    async def groups(self) -> list[CompositeDuplicateSnapshotGroup]:
        async with self._database.sessions() as session:
            group_rows = list(
                (
                    await session.execute(
                        select(CompositeDuplicateGroupRecord).order_by(
                            CompositeDuplicateGroupRecord.position
                        )
                    )
                ).scalars()
            )
            member_rows = list(
                (
                    await session.execute(
                        select(
                            CompositeDuplicateGroupMemberRecord.group_id,
                            CompositeDuplicateGroupMemberRecord.asset_id,
                        ).order_by(
                            CompositeDuplicateGroupMemberRecord.group_id,
                            CompositeDuplicateGroupMemberRecord.position,
                        )
                    )
                ).all()
            )
            evidence_rows = list(
                (
                    await session.execute(
                        select(CompositeDuplicateGroupEvidenceRecord).order_by(
                            CompositeDuplicateGroupEvidenceRecord.group_id,
                            CompositeDuplicateGroupEvidenceRecord.discovery_source,
                        )
                    )
                ).scalars()
            )

        members: dict[str, list[UUID]] = {}
        for group_id, asset_id in member_rows:
            members.setdefault(group_id, []).append(asset_id)
        evidence: dict[str, list[DiscoveryEvidence]] = {}
        for row in evidence_rows:
            evidence.setdefault(row.group_id, []).append(
                DiscoveryEvidence(
                    discovery_source=DiscoverySource(row.discovery_source),
                    provider_group_id=row.provider_group_id,
                    metadata=dict(row.evidence_metadata or {}),
                )
            )
        return [
            CompositeDuplicateSnapshotGroup(
                group_id=row.group_id,
                discovery_source=DiscoverySource(row.discovery_source),
                provider_group_id=row.provider_group_id,
                asset_ids=tuple(members.get(row.group_id, [])),
                provider_metadata=dict(row.provider_metadata or {}),
                evidence=tuple(evidence.get(row.group_id, [])),
                similarity_validation=_validation_from_payload(row.similarity_validation),
            )
            for row in group_rows
            if len(members.get(row.group_id, [])) >= 2
        ]

    async def page(
        self,
        *,
        page: int,
        page_size: int,
        source: DiscoverySource | None = None,
        sort: str = "reclaimable",
        direction: str = "desc",
    ) -> CompositeDuplicateSnapshotPage:
        """Read one ordered page without hydrating the full duplicate universe."""

        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size
        source_filter = (
            exists(
                select(1).where(
                    CompositeDuplicateGroupEvidenceRecord.group_id
                    == CompositeDuplicateGroupRecord.group_id,
                    CompositeDuplicateGroupEvidenceRecord.discovery_source == source.value,
                )
            )
            if source is not None
            else None
        )

        async with self._database.sessions() as session:
            count_statement = select(func.count()).select_from(CompositeDuplicateGroupRecord)
            sort_column = {
                "reclaimable": CompositeDuplicateGroupRecord.reclaimable_bytes,
                "members": CompositeDuplicateGroupRecord.member_count,
                "similarity": CompositeDuplicateGroupRecord.similarity_score,
                "newest": CompositeDuplicateGroupRecord.newest_taken_at,
                "oldest": CompositeDuplicateGroupRecord.oldest_taken_at,
                "discovered": CompositeDuplicateGroupRecord.first_discovered_at,
            }.get(sort, CompositeDuplicateGroupRecord.reclaimable_bytes)
            order = sort_column.desc() if direction == "desc" else sort_column.asc()
            group_statement = (
                select(CompositeDuplicateGroupRecord)
                .order_by(
                    order.nulls_last(),
                    CompositeDuplicateGroupRecord.group_id.asc(),
                )
                .offset(offset)
                .limit(page_size)
            )
            if source_filter is not None:
                count_statement = count_statement.where(source_filter)
                group_statement = group_statement.where(source_filter)

            total = int((await session.scalar(count_statement)) or 0)
            group_rows = list((await session.execute(group_statement)).scalars())
            group_ids = [row.group_id for row in group_rows]
            if group_ids:
                member_rows = list(
                    (
                        await session.execute(
                            select(
                                CompositeDuplicateGroupMemberRecord.group_id,
                                CompositeDuplicateGroupMemberRecord.asset_id,
                            )
                            .where(CompositeDuplicateGroupMemberRecord.group_id.in_(group_ids))
                            .order_by(
                                CompositeDuplicateGroupMemberRecord.group_id,
                                CompositeDuplicateGroupMemberRecord.position,
                            )
                        )
                    ).all()
                )
                evidence_rows = list(
                    (
                        await session.execute(
                            select(CompositeDuplicateGroupEvidenceRecord)
                            .where(CompositeDuplicateGroupEvidenceRecord.group_id.in_(group_ids))
                            .order_by(
                                CompositeDuplicateGroupEvidenceRecord.group_id,
                                CompositeDuplicateGroupEvidenceRecord.discovery_source,
                            )
                        )
                    ).scalars()
                )
            else:
                member_rows = []
                evidence_rows = []

        members: dict[str, list[UUID]] = {}
        for group_id, asset_id in member_rows:
            members.setdefault(group_id, []).append(asset_id)
        evidence: dict[str, list[DiscoveryEvidence]] = {}
        for row in evidence_rows:
            evidence.setdefault(row.group_id, []).append(
                DiscoveryEvidence(
                    discovery_source=DiscoverySource(row.discovery_source),
                    provider_group_id=row.provider_group_id,
                    metadata=dict(row.evidence_metadata or {}),
                )
            )
        groups = [
            CompositeDuplicateSnapshotGroup(
                group_id=row.group_id,
                discovery_source=DiscoverySource(row.discovery_source),
                provider_group_id=row.provider_group_id,
                asset_ids=tuple(members.get(row.group_id, [])),
                provider_metadata=dict(row.provider_metadata or {}),
                evidence=tuple(evidence.get(row.group_id, [])),
                similarity_validation=_validation_from_payload(row.similarity_validation),
            )
            for row in group_rows
            if len(members.get(row.group_id, [])) >= 2
        ]
        return CompositeDuplicateSnapshotPage(
            groups=groups,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def replace_snapshot(
        self,
        groups: list[DiscoveredGroup],
    ) -> CompositeDuplicateSnapshotMetadata:
        """Publish one complete composite snapshot or leave the previous one intact."""

        group_ids = [group.group_id for group in groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("Composite duplicate snapshot contains duplicate group IDs")
        asset_ids = {asset.id for group in groups for asset in group.assets}
        now = datetime.now(UTC)

        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(CompositeDuplicateSyncStateRecord)
                .where(CompositeDuplicateSyncStateRecord.id == SNAPSHOT_STATE_ID)
                .with_for_update()
            )
            if state is None:
                state = CompositeDuplicateSyncStateRecord(id=SNAPSHOT_STATE_ID)
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
                    raise CompositeDuplicateSnapshotAssetMissingError(
                        "Composite duplicate rebuild references "
                        f"{len(missing)} asset(s) missing from the synchronized local catalog."
                    )

            generation = state.authoritative_generation + 1
            group_rows = []
            for position, group in enumerate(groups):
                fingerprint = member_set_key(asset.id for asset in group.assets)
                summary = _group_projection_summary(group)
                group_rows.append(
                    {
                        "group_id": group.group_id,
                        "position": position,
                        "discovery_source": group.discovery_source.value,
                        "provider_group_id": group.provider_group_id,
                        "stable_group_key": stable_group_key(
                            group.discovery_source.value, fingerprint
                        ),
                        "member_fingerprint": fingerprint,
                        **summary,
                        "first_discovered_at": now,
                        "provider_metadata": dict(group.provider_metadata),
                        "similarity_validation": _validation_payload(group.similarity_validation),
                        "sync_generation": generation,
                        "synced_at": now,
                    }
                )
            member_rows = [
                {
                    "group_id": group.group_id,
                    "asset_id": asset.id,
                    "position": position,
                    "sync_generation": generation,
                }
                for group in groups
                for position, asset in enumerate(group.assets)
            ]
            evidence_rows = [
                {
                    "group_id": group.group_id,
                    "discovery_source": item.discovery_source.value,
                    "provider_group_id": item.provider_group_id,
                    "evidence_metadata": dict(item.metadata),
                    "sync_generation": generation,
                }
                for group in groups
                for item in group.evidence
            ]

            for offset in range(0, len(group_rows), WRITE_BATCH_SIZE):
                values = group_rows[offset : offset + WRITE_BATCH_SIZE]
                statement = insert(CompositeDuplicateGroupRecord).values(values)
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[CompositeDuplicateGroupRecord.group_id],
                        set_={
                            "position": statement.excluded.position,
                            "discovery_source": statement.excluded.discovery_source,
                            "provider_group_id": statement.excluded.provider_group_id,
                            "stable_group_key": statement.excluded.stable_group_key,
                            "member_fingerprint": statement.excluded.member_fingerprint,
                            "member_count": statement.excluded.member_count,
                            "reclaimable_bytes": statement.excluded.reclaimable_bytes,
                            "similarity_score": statement.excluded.similarity_score,
                            "oldest_taken_at": statement.excluded.oldest_taken_at,
                            "newest_taken_at": statement.excluded.newest_taken_at,
                            "provider_metadata": statement.excluded.provider_metadata,
                            "similarity_validation": statement.excluded.similarity_validation,
                            "sync_generation": statement.excluded.sync_generation,
                            "synced_at": statement.excluded.synced_at,
                        },
                    )
                )

            for offset in range(0, len(member_rows), WRITE_BATCH_SIZE):
                values = member_rows[offset : offset + WRITE_BATCH_SIZE]
                statement = insert(CompositeDuplicateGroupMemberRecord).values(values)
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[
                            CompositeDuplicateGroupMemberRecord.group_id,
                            CompositeDuplicateGroupMemberRecord.asset_id,
                        ],
                        set_={
                            "position": statement.excluded.position,
                            "sync_generation": statement.excluded.sync_generation,
                        },
                    )
                )

            for offset in range(0, len(evidence_rows), WRITE_BATCH_SIZE):
                values = evidence_rows[offset : offset + WRITE_BATCH_SIZE]
                statement = insert(CompositeDuplicateGroupEvidenceRecord).values(values)
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[
                            CompositeDuplicateGroupEvidenceRecord.group_id,
                            CompositeDuplicateGroupEvidenceRecord.discovery_source,
                        ],
                        set_={
                            "provider_group_id": statement.excluded.provider_group_id,
                            "evidence_metadata": statement.excluded.evidence_metadata,
                            "sync_generation": statement.excluded.sync_generation,
                        },
                    )
                )

            await session.execute(
                delete(CompositeDuplicateGroupEvidenceRecord).where(
                    CompositeDuplicateGroupEvidenceRecord.sync_generation != generation
                )
            )
            await session.execute(
                delete(CompositeDuplicateGroupMemberRecord).where(
                    CompositeDuplicateGroupMemberRecord.sync_generation != generation
                )
            )
            await session.execute(
                delete(CompositeDuplicateGroupRecord).where(
                    CompositeDuplicateGroupRecord.sync_generation != generation
                )
            )

            state.authoritative_generation = generation
            state.group_count = len(group_rows)
            state.member_count = len(member_rows)
            state.evidence_count = len(evidence_rows)
            state.last_success_at = now

        return CompositeDuplicateSnapshotMetadata(
            authoritative_generation=generation,
            group_count=len(group_rows),
            member_count=len(member_rows),
            evidence_count=len(evidence_rows),
            last_success_at=now,
        )

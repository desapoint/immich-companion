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
    and_,
    bindparam,
    case,
    delete,
    exists,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from companion.database import DatabaseManager
from companion.discovery.base import DiscoveredGroup, DiscoveryEvidence
from companion.duplicate_identity import member_set_key, stable_group_key
from companion.duplicate_schema import COMPLETED_DUPLICATE_REVIEW_STATUSES
from companion.group_decision import DiscoverySource
from companion.models import AssetRecord, Base, DuplicateGroupReviewRecord
from companion.similarity_grouping import SimilarityAdmissionEvidence, ValidatedSimilarityGroup

SNAPSHOT_STATE_ID = 1
WRITE_BATCH_SIZE = 1_000


def _unresolved_review_filter():
    return or_(
        DuplicateGroupReviewRecord.review_status.is_(None),
        ~DuplicateGroupReviewRecord.review_status.in_(COMPLETED_DUPLICATE_REVIEW_STATUSES),
    )


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
    v2_policy_state: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="blocked", index=True
    )
    v2_state_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    async def update_v2_policy_states(
        self,
        states: list[tuple[str, str, str]],
    ) -> int:
        """Publish bounded V2 policy summaries only for unchanged group memberships."""

        if not states:
            return 0
        now = datetime.now(UTC)
        table = CompositeDuplicateGroupRecord.__table__
        statement = (
            table.update()
            .where(
                table.c.group_id == bindparam("target_group_id"),
                table.c.member_fingerprint == bindparam("target_member_fingerprint"),
            )
            .values(
                v2_policy_state=bindparam("v2_policy_state_value"),
                v2_state_updated_at=bindparam("v2_state_updated_at_value"),
            )
        )
        values = [
            {
                "target_group_id": group_id,
                "target_member_fingerprint": member_fingerprint,
                "v2_policy_state_value": policy_state,
                "v2_state_updated_at_value": now,
            }
            for group_id, member_fingerprint, policy_state in states
        ]
        async with self._database.sessions() as session, session.begin():
            await session.execute(statement, values)
        return len(values)

    async def matching_group_ids(
        self,
        *,
        source: DiscoverySource | None = None,
        state: str = "all",
        limit: int = 5_001,
    ) -> list[str]:
        """Resolve only matching group IDs so bulk V2 actions avoid group hydration."""

        limit = max(1, min(limit, 50_001))
        review_join = and_(
            DuplicateGroupReviewRecord.stable_group_key
            == CompositeDuplicateGroupRecord.stable_group_key,
            DuplicateGroupReviewRecord.member_fingerprint
            == CompositeDuplicateGroupRecord.member_fingerprint,
        )
        statement = (
            select(CompositeDuplicateGroupRecord.group_id)
            .outerjoin(DuplicateGroupReviewRecord, review_join)
            .where(_unresolved_review_filter())
        )
        if state != "all":
            decision_count = func.coalesce(
                func.json_array_length(DuplicateGroupReviewRecord.member_decisions), 0
            )
            resolved_state = case(
                (
                    CompositeDuplicateGroupRecord.v2_policy_state == "blocked",
                    "Blocked",
                ),
                (
                    (decision_count > 0)
                    & (decision_count < CompositeDuplicateGroupRecord.member_count),
                    "Needs decisions",
                ),
                (
                    decision_count == CompositeDuplicateGroupRecord.member_count,
                    "Actionable",
                ),
                (
                    CompositeDuplicateGroupRecord.v2_policy_state == "auto_ready",
                    "Actionable",
                ),
                else_="Needs review",
            )
            if state == "auto_ready":
                statement = statement.where(
                    CompositeDuplicateGroupRecord.v2_policy_state == "auto_ready",
                    resolved_state == "Actionable",
                )
            else:
                expected = {
                    "needs_review": "Needs review",
                    "blocked": "Blocked",
                    "actionable": "Actionable",
                    "needs_decisions": "Needs decisions",
                }.get(state)
                if expected is not None:
                    statement = statement.where(resolved_state == expected)

        if source is not None:
            statement = statement.where(
                exists(
                    select(1).where(
                        CompositeDuplicateGroupEvidenceRecord.group_id
                        == CompositeDuplicateGroupRecord.group_id,
                        CompositeDuplicateGroupEvidenceRecord.discovery_source == source.value,
                    )
                )
            )

        statement = statement.order_by(CompositeDuplicateGroupRecord.group_id.asc()).limit(limit)
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())



    async def page(
        self,
        *,
        page: int,
        page_size: int,
        source: DiscoverySource | None = None,
        sort: str = "reclaimable",
        direction: str = "desc",
        state: str = "all",
    ) -> CompositeDuplicateSnapshotPage:
        """Read one ordered SQL-filtered page before hydrating its members."""

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
            sort_column = {
                "reclaimable": CompositeDuplicateGroupRecord.reclaimable_bytes,
                "members": CompositeDuplicateGroupRecord.member_count,
                "similarity": CompositeDuplicateGroupRecord.similarity_score,
                "date": CompositeDuplicateGroupRecord.newest_taken_at,
                "discovered": CompositeDuplicateGroupRecord.first_discovered_at,
            }.get(sort, CompositeDuplicateGroupRecord.reclaimable_bytes)
            order = sort_column.desc() if direction == "desc" else sort_column.asc()
            review_join = and_(
                DuplicateGroupReviewRecord.stable_group_key
                == CompositeDuplicateGroupRecord.stable_group_key,
                DuplicateGroupReviewRecord.member_fingerprint
                == CompositeDuplicateGroupRecord.member_fingerprint,
            )
            count_statement = (
                select(func.count())
                .select_from(CompositeDuplicateGroupRecord)
                .outerjoin(DuplicateGroupReviewRecord, review_join)
                .where(_unresolved_review_filter())
            )
            group_statement = (
                select(CompositeDuplicateGroupRecord)
                .outerjoin(DuplicateGroupReviewRecord, review_join)
                .where(_unresolved_review_filter())
            )

            if state != "all":
                decision_count = func.coalesce(
                    func.json_array_length(DuplicateGroupReviewRecord.member_decisions), 0
                )
                resolved_state = case(
                    (
                        CompositeDuplicateGroupRecord.v2_policy_state == "blocked",
                        "Blocked",
                    ),
                    (
                        (decision_count > 0)
                        & (decision_count < CompositeDuplicateGroupRecord.member_count),
                        "Needs decisions",
                    ),
                    (
                        decision_count == CompositeDuplicateGroupRecord.member_count,
                        "Actionable",
                    ),
                    (
                        CompositeDuplicateGroupRecord.v2_policy_state == "auto_ready",
                        "Actionable",
                    ),
                    else_="Needs review",
                )
                if state == "auto_ready":
                    state_filter = and_(
                        CompositeDuplicateGroupRecord.v2_policy_state == "auto_ready",
                        resolved_state == "Actionable",
                    )
                else:
                    expected = {
                        "needs_review": "Needs review",
                        "blocked": "Blocked",
                        "actionable": "Actionable",
                        "needs_decisions": "Needs decisions",
                    }.get(state)
                    state_filter = resolved_state == expected if expected is not None else None
                if state_filter is not None:
                    count_statement = count_statement.where(state_filter)
                    group_statement = group_statement.where(state_filter)

            if source_filter is not None:
                count_statement = count_statement.where(source_filter)
                group_statement = group_statement.where(source_filter)

            group_statement = (
                group_statement.order_by(
                    order.nulls_last(),
                    CompositeDuplicateGroupRecord.group_id.asc(),
                )
                .offset(offset)
                .limit(page_size)
            )
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

        group_ids = {group.group_id for group in groups}
        if len(group_ids) != len(groups):
            raise ValueError("Composite duplicate snapshot contains duplicate group IDs")
        asset_ids = {asset.id for group in groups for asset in group.assets}
        group_count = len(groups)
        member_count = sum(len(group.assets) for group in groups)
        evidence_count = sum(len(group.evidence) for group in groups)
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

            for offset in range(0, group_count, WRITE_BATCH_SIZE):
                values = []
                for position, group in enumerate(
                    groups[offset : offset + WRITE_BATCH_SIZE],
                    start=offset,
                ):
                    fingerprint = member_set_key(asset.id for asset in group.assets)
                    summary = _group_projection_summary(group)
                    values.append(
                        {
                            "group_id": group.group_id,
                            "position": position,
                            "discovery_source": group.discovery_source.value,
                            "provider_group_id": group.provider_group_id,
                            "stable_group_key": stable_group_key(
                                group.discovery_source.value,
                                fingerprint,
                            ),
                            "member_fingerprint": fingerprint,
                            **summary,
                            "first_discovered_at": now,
                            "v2_policy_state": "blocked",
                            "v2_state_updated_at": None,
                            "provider_metadata": dict(group.provider_metadata),
                            "similarity_validation": _validation_payload(
                                group.similarity_validation
                            ),
                            "sync_generation": generation,
                            "synced_at": now,
                        }
                    )
                if values:
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
                                "v2_policy_state": statement.excluded.v2_policy_state,
                                "v2_state_updated_at": statement.excluded.v2_state_updated_at,
                                "provider_metadata": statement.excluded.provider_metadata,
                                "similarity_validation": statement.excluded.similarity_validation,
                                "sync_generation": statement.excluded.sync_generation,
                                "synced_at": statement.excluded.synced_at,
                            },
                        )
                    )

            member_values: list[dict[str, object]] = []

            async def flush_members() -> None:
                if not member_values:
                    return
                statement = insert(CompositeDuplicateGroupMemberRecord).values(member_values)
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
                member_values.clear()

            for group in groups:
                for position, asset in enumerate(group.assets):
                    member_values.append(
                        {
                            "group_id": group.group_id,
                            "asset_id": asset.id,
                            "position": position,
                            "sync_generation": generation,
                        }
                    )
                    if len(member_values) >= WRITE_BATCH_SIZE:
                        await flush_members()
            await flush_members()

            evidence_values: list[dict[str, object]] = []

            async def flush_evidence() -> None:
                if not evidence_values:
                    return
                statement = insert(CompositeDuplicateGroupEvidenceRecord).values(evidence_values)
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
                evidence_values.clear()

            for group in groups:
                for item in group.evidence:
                    evidence_values.append(
                        {
                            "group_id": group.group_id,
                            "discovery_source": item.discovery_source.value,
                            "provider_group_id": item.provider_group_id,
                            "evidence_metadata": dict(item.metadata),
                            "sync_generation": generation,
                        }
                    )
                    if len(evidence_values) >= WRITE_BATCH_SIZE:
                        await flush_evidence()
            await flush_evidence()

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
            state.group_count = group_count
            state.member_count = member_count
            state.evidence_count = evidence_count
            state.last_success_at = now

        return CompositeDuplicateSnapshotMetadata(
            authoritative_generation=generation,
            group_count=group_count,
            member_count=member_count,
            evidence_count=evidence_count,
            last_success_at=now,
        )

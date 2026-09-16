"""Persistence boundary for fingerprint-bound duplicate review decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.duplicate_identity import member_set_key, stable_group_key
from companion.duplicate_schema import COMPLETED_DUPLICATE_REVIEW_STATUSES
from companion.models import DuplicateGroupReviewRecord, DuplicateReviewWorkspaceRecord

WORKSPACE_KEY = "default"
COVERAGE_PENDING_DRAFT_STATUS = "coverage_pending"
IMMICH_DUPLICATE_SOURCE = "immich_duplicate"
COMPANION_SIMILARITY_SOURCE = "companion_similarity"


def _review_member_ids(record: DuplicateGroupReviewRecord) -> set[str]:
    return {
        str(decision["asset_id"])
        for decision in list(record.member_decisions or [])
        if isinstance(decision, dict) and decision.get("asset_id")
    }


def _source_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _decision_member_uuids(decisions: Any) -> set[UUID]:
    member_ids: set[UUID] = set()
    if not isinstance(decisions, list):
        return member_ids
    for decision in decisions:
        if not isinstance(decision, dict) or not decision.get("asset_id"):
            continue
        try:
            member_ids.add(UUID(str(decision["asset_id"])))
        except (TypeError, ValueError):
            continue
    return member_ids


def _coverage_rows(
    groups: list[Any],
    members_by_group: dict[str, list[UUID]],
    parent_member_sets: list[set[UUID]],
    now: datetime,
) -> list[dict[str, object]]:
    """Build internal coverage rows only for groups fully contained by one parent."""

    parents = [set(member_ids) for member_ids in parent_member_sets if len(member_ids) >= 2]
    if not parents:
        return []
    rows: list[dict[str, object]] = []
    for group in groups:
        group_id = str(group.group_id)
        ordered_ids = list(members_by_group.get(group_id, []))
        member_ids = set(ordered_ids)
        if len(member_ids) < 2 or not any(member_ids.issubset(parent) for parent in parents):
            continue
        fingerprint = str(group.member_fingerprint)
        rows.append(
            {
                "discovery_source": IMMICH_DUPLICATE_SOURCE,
                "provider_group_id": str(group.provider_group_id or group.group_id),
                "stable_group_key": str(group.stable_group_key),
                "member_set_key": fingerprint,
                "member_fingerprint": fingerprint,
                "member_decisions": [
                    {
                        "asset_id": str(asset_id),
                        "disposition": "no_change",
                        "primary": False,
                        "status": "pending",
                    }
                    for asset_id in ordered_ids
                ],
                "stack_resolution": "move_selected",
                "draft_status": COVERAGE_PENDING_DRAFT_STATUS,
                "review_status": "pending",
                "last_seen_at": now,
                "last_reviewed_at": None,
                "updated_at": now,
            }
        )
    return rows


class DuplicateReviewRepository:
    """Persist manual decisions without treating discovery snapshots as authoritative."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def get_many(
        self,
        discovery_source: str,
        stable_group_keys: list[str],
    ) -> dict[str, DuplicateGroupReviewRecord]:
        if not stable_group_keys:
            return {}
        statement = select(DuplicateGroupReviewRecord).where(
            DuplicateGroupReviewRecord.discovery_source == discovery_source,
            DuplicateGroupReviewRecord.stable_group_key.in_(
                list(dict.fromkeys(stable_group_keys))
            ),
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.stable_group_key: record for record in records}

    async def list_drafts(self) -> list[DuplicateGroupReviewRecord]:
        """Return only review rows carrying member-level draft state."""

        statement = (
            select(DuplicateGroupReviewRecord)
            .where(
                ~DuplicateGroupReviewRecord.review_status.in_(
                    COMPLETED_DUPLICATE_REVIEW_STATUSES
                ),
                DuplicateGroupReviewRecord.draft_status != COVERAGE_PENDING_DRAFT_STATUS,
                or_(
                    func.coalesce(
                        func.json_array_length(DuplicateGroupReviewRecord.member_decisions), 0
                    )
                    > 0,
                    DuplicateGroupReviewRecord.stack_primary_asset_id.is_not(None),
                ),
            )
            .order_by(
                DuplicateGroupReviewRecord.discovery_source,
                DuplicateGroupReviewRecord.stable_group_key,
            )
        )
        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

    async def inherit_completed_groups(self, groups: list[Any]) -> int:
        """Suppress membership shrinkage without rewriting the original completed review.

        A current group is inherited only when its members are a subset of one completed
        review lineage. The comparison is provider-neutral because a durable user decision
        belongs to the reviewed assets, not to whichever discovery provider still reports
        them. Existing exact review rows always win, so a fresh draft is never hidden. The
        inherited row retains the original reviewed membership in ``member_decisions`` so
        another deletion remains covered, while ``draft_status`` keeps these projection
        rows out of resolution history. Internal coverage placeholders are the sole exception:
        they may be replaced by an actual completed lineage because they never represent a
        user-authored review.
        """

        if not groups:
            return 0
        statement = (
            select(DuplicateGroupReviewRecord)
            .where(
                DuplicateGroupReviewRecord.review_status.in_(
                    COMPLETED_DUPLICATE_REVIEW_STATUSES
                ),
                DuplicateGroupReviewRecord.draft_status == "completed",
                func.coalesce(
                    func.json_array_length(DuplicateGroupReviewRecord.member_decisions), 0
                )
                > 0,
            )
            .order_by(DuplicateGroupReviewRecord.last_reviewed_at.desc())
        )
        async with self._database.sessions() as session:
            completed = list((await session.scalars(statement)).all())
        if not completed:
            return 0

        completed_members = [(record, _review_member_ids(record)) for record in completed]
        now = datetime.now(UTC)
        candidates: list[dict[str, object]] = []
        current_keys_by_source: dict[str, list[str]] = {}
        normalized_groups: list[tuple[Any, str, str, str, set[str]]] = []
        for group in groups:
            source_value = getattr(group.discovery_source, "value", group.discovery_source)
            source = str(source_value)
            explicit_asset_ids = getattr(group, "asset_ids", None)
            asset_ids = tuple(
                explicit_asset_ids
                if explicit_asset_ids is not None
                else (asset.id for asset in getattr(group, "assets", ()))
            )
            if len(asset_ids) < 2:
                continue
            fingerprint = member_set_key(asset_ids)
            group_key = stable_group_key(source, fingerprint)
            current_ids = {str(asset_id) for asset_id in asset_ids}
            current_keys_by_source.setdefault(source, []).append(group_key)
            normalized_groups.append(
                (group, source, group_key, fingerprint, current_ids)
            )

        existing_by_source: dict[str, dict[str, DuplicateGroupReviewRecord]] = {}
        for source, keys in current_keys_by_source.items():
            existing_by_source[source] = await self.get_many(source, keys)

        for group, source, group_key, fingerprint, current_ids in normalized_groups:
            existing = existing_by_source.get(source, {}).get(group_key)
            if existing is not None and existing.draft_status != COVERAGE_PENDING_DRAFT_STATUS:
                continue
            matches = [
                (record, reviewed_ids)
                for record, reviewed_ids in completed_members
                if current_ids.issubset(reviewed_ids)
            ]
            if not matches:
                continue
            source_review, _ = min(
                matches,
                key=lambda item: (
                    len(item[1]),
                    -(item[0].last_reviewed_at or item[0].updated_at).timestamp(),
                ),
            )
            provider_group_id = getattr(group, "provider_group_id", None) or getattr(
                group, "group_id", group_key
            )
            candidates.append(
                {
                    "discovery_source": source,
                    "provider_group_id": str(provider_group_id),
                    "stable_group_key": group_key,
                    "member_set_key": fingerprint,
                    "member_fingerprint": fingerprint,
                    "manual_action": source_review.manual_action,
                    "manual_primary_asset_id": source_review.manual_primary_asset_id,
                    "member_decisions": list(source_review.member_decisions or []),
                    "stack_primary_asset_id": source_review.stack_primary_asset_id,
                    "stack_resolution": source_review.stack_resolution,
                    "metadata_keeper_asset_id": source_review.metadata_keeper_asset_id,
                    "draft_status": "inherited",
                    "review_status": source_review.review_status,
                    "last_seen_at": now,
                    "last_reviewed_at": source_review.last_reviewed_at,
                    "updated_at": now,
                }
            )

        if not candidates:
            return 0
        async with self._database.sessions() as session, session.begin():
            for offset in range(0, len(candidates), 500):
                values = candidates[offset : offset + 500]
                statement = insert(DuplicateGroupReviewRecord).values(values)
                await session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_duplicate_group_reviews_stable_key",
                        set_={
                            key: getattr(statement.excluded, key)
                            for key in values[0]
                            if key != "stable_group_key"
                        },
                        where=(
                            DuplicateGroupReviewRecord.draft_status
                            == COVERAGE_PENDING_DRAFT_STATUS
                        ),
                    )
                )
        return len(candidates)

    async def history(
        self,
        *,
        since: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[DuplicateGroupReviewRecord], int]:
        """Return original completed resolutions, excluding inherited suppression rows."""

        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        filters = [
            DuplicateGroupReviewRecord.review_status.in_(
                COMPLETED_DUPLICATE_REVIEW_STATUSES
            ),
            DuplicateGroupReviewRecord.draft_status == "completed",
        ]
        if since is not None:
            filters.append(DuplicateGroupReviewRecord.last_reviewed_at >= since)
        async with self._database.sessions() as session:
            total = int(
                (
                    await session.scalar(
                        select(func.count())
                        .select_from(DuplicateGroupReviewRecord)
                        .where(*filters)
                    )
                )
                or 0
            )
            records = list(
                (
                    await session.scalars(
                        select(DuplicateGroupReviewRecord)
                        .where(*filters)
                        .order_by(
                            DuplicateGroupReviewRecord.last_reviewed_at.desc(),
                            DuplicateGroupReviewRecord.id.desc(),
                        )
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                ).all()
            )
        return records, total

    async def save(
        self,
        *,
        discovery_source: str,
        provider_group_id: str,
        stable_group_key: str,
        member_set_key: str,
        member_fingerprint: str,
        manual_action: str | None,
        manual_primary_asset_id: UUID | None,
        review_status: str,
    ) -> DuplicateGroupReviewRecord:
        now = datetime.now(UTC)
        values = {
            "discovery_source": discovery_source,
            "provider_group_id": provider_group_id,
            "stable_group_key": stable_group_key,
            "member_set_key": member_set_key,
            "member_fingerprint": member_fingerprint,
            "manual_action": manual_action,
            "manual_primary_asset_id": manual_primary_asset_id,
            "review_status": review_status,
            "last_seen_at": now,
            "last_reviewed_at": now,
            "updated_at": now,
        }
        async with self._database.sessions() as session, session.begin():
            statement = insert(DuplicateGroupReviewRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_duplicate_group_reviews_stable_key",
                    set_={key: getattr(statement.excluded, key) for key in values},
                )
            )
        records = await self.get_many(discovery_source, [stable_group_key])
        return records[stable_group_key]

    async def _freeze_contained_immich_groups(
        self,
        session: Any,
        parent_member_sets: list[set[UUID]],
        now: datetime,
    ) -> int:
        """Freeze current Immich groups fully contained by one similarity draft."""

        parents = [set(member_ids) for member_ids in parent_member_sets if len(member_ids) >= 2]
        if not parents:
            return 0

        from companion.composite_duplicate_repository import (
            CompositeDuplicateGroupMemberRecord,
            CompositeDuplicateGroupRecord,
        )

        parent_union = set().union(*parents)
        max_parent_size = max(len(member_ids) for member_ids in parents)
        group_statement = (
            select(CompositeDuplicateGroupRecord)
            .join(
                CompositeDuplicateGroupMemberRecord,
                CompositeDuplicateGroupMemberRecord.group_id
                == CompositeDuplicateGroupRecord.group_id,
            )
            .where(
                CompositeDuplicateGroupRecord.discovery_source == IMMICH_DUPLICATE_SOURCE,
                CompositeDuplicateGroupRecord.member_count >= 2,
                CompositeDuplicateGroupRecord.member_count <= max_parent_size,
                CompositeDuplicateGroupMemberRecord.asset_id.in_(parent_union),
            )
            .distinct()
        )
        groups = list((await session.scalars(group_statement)).all())
        if not groups:
            return 0

        group_ids = [str(group.group_id) for group in groups]
        member_statement = (
            select(CompositeDuplicateGroupMemberRecord)
            .where(CompositeDuplicateGroupMemberRecord.group_id.in_(group_ids))
            .order_by(
                CompositeDuplicateGroupMemberRecord.group_id,
                CompositeDuplicateGroupMemberRecord.position,
            )
        )
        members = list((await session.scalars(member_statement)).all())
        members_by_group: dict[str, list[UUID]] = {}
        for member in members:
            members_by_group.setdefault(str(member.group_id), []).append(member.asset_id)

        rows = _coverage_rows(groups, members_by_group, parents, now)
        if not rows:
            return 0
        statement = insert(DuplicateGroupReviewRecord).values(rows)
        await session.execute(
            statement.on_conflict_do_nothing(
                constraint="uq_duplicate_group_reviews_stable_key"
            )
        )
        return len(rows)

    async def save_draft(
        self,
        *,
        discovery_source: str,
        provider_group_id: str,
        stable_group_key: str,
        member_set_key: str,
        member_fingerprint: str,
        member_decisions: list[dict[str, str]],
        stack_primary_asset_id: UUID | None,
        stack_resolution: str,
        metadata_keeper_asset_id: UUID | None,
        draft_status: str,
    ) -> DuplicateGroupReviewRecord:
        now = datetime.now(UTC)
        values = {
            "discovery_source": discovery_source,
            "provider_group_id": provider_group_id,
            "stable_group_key": stable_group_key,
            "member_set_key": member_set_key,
            "member_fingerprint": member_fingerprint,
            "member_decisions": member_decisions,
            "stack_primary_asset_id": stack_primary_asset_id,
            "stack_resolution": stack_resolution,
            "metadata_keeper_asset_id": metadata_keeper_asset_id,
            "draft_status": draft_status,
            "last_seen_at": now,
            "last_reviewed_at": now,
            "updated_at": now,
        }
        async with self._database.sessions() as session, session.begin():
            statement = insert(DuplicateGroupReviewRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_duplicate_group_reviews_stable_key",
                    set_={key: getattr(statement.excluded, key) for key in values},
                )
            )
            if _source_value(discovery_source) == COMPANION_SIMILARITY_SOURCE:
                await self._freeze_contained_immich_groups(
                    session,
                    [_decision_member_uuids(member_decisions)],
                    now,
                )
        records = await self.get_many(discovery_source, [stable_group_key])
        return records[stable_group_key]

    async def save_drafts(self, drafts: list[dict[str, object]]) -> None:
        """Persist many complete drafts in bounded upsert batches."""

        if not drafts:
            return
        now = datetime.now(UTC)
        rows = [
            {
                **draft,
                "last_seen_at": now,
                "last_reviewed_at": now,
                "updated_at": now,
            }
            for draft in drafts
        ]
        async with self._database.sessions() as session, session.begin():
            for offset in range(0, len(rows), 500):
                values = rows[offset : offset + 500]
                statement = insert(DuplicateGroupReviewRecord).values(values)
                await session.execute(
                    statement.on_conflict_do_update(
                        constraint="uq_duplicate_group_reviews_stable_key",
                        set_={
                            key: getattr(statement.excluded, key)
                            for key in values[0]
                            if key not in {"last_seen_at"}
                        }
                        | {"last_seen_at": statement.excluded.last_seen_at},
                    )
                )
            parent_sets = {
                frozenset(_decision_member_uuids(row.get("member_decisions")))
                for row in rows
                if _source_value(row.get("discovery_source")) == COMPANION_SIMILARITY_SOURCE
            }
            if parent_sets:
                await self._freeze_contained_immich_groups(
                    session,
                    [set(member_ids) for member_ids in parent_sets],
                    now,
                )

    async def clear_decisions(
        self,
        discovery_source: str,
        stable_group_keys: list[str],
    ) -> None:
        """Clear review choices while retaining the provider identity record."""

        if not stable_group_keys:
            return
        now = datetime.now(UTC)
        statement = (
            update(DuplicateGroupReviewRecord)
            .where(
                DuplicateGroupReviewRecord.discovery_source == discovery_source,
                DuplicateGroupReviewRecord.stable_group_key.in_(
                    list(dict.fromkeys(stable_group_keys))
                ),
            )
            .values(
                manual_action=None,
                manual_primary_asset_id=None,
                member_decisions=[],
                stack_primary_asset_id=None,
                stack_resolution="move_selected",
                metadata_keeper_asset_id=None,
                draft_status="pending",
                review_status="pending",
                last_reviewed_at=now,
                updated_at=now,
            )
        )
        async with self._database.sessions() as session, session.begin():
            await session.execute(statement)

    async def reset_all_decisions(self) -> int:
        """Atomically clear every active decision and discard workspace navigation state.

        Completed resolutions are historical records and remain untouched.  The update is
        deliberately restricted to non-completed rows that actually carry mutable review
        state, avoiding write amplification when there is nothing to clear.  Removing the
        singleton workspace in the same transaction also clears stale selections that can no
        longer be resolved by discovery.
        """

        now = datetime.now(UTC)
        resettable_state = or_(
            DuplicateGroupReviewRecord.manual_action.is_not(None),
            DuplicateGroupReviewRecord.manual_primary_asset_id.is_not(None),
            func.coalesce(
                func.json_array_length(DuplicateGroupReviewRecord.member_decisions), 0
            )
            > 0,
            DuplicateGroupReviewRecord.stack_primary_asset_id.is_not(None),
            DuplicateGroupReviewRecord.metadata_keeper_asset_id.is_not(None),
            DuplicateGroupReviewRecord.stack_resolution != "move_selected",
            DuplicateGroupReviewRecord.draft_status != "pending",
            DuplicateGroupReviewRecord.review_status != "pending",
        )
        statement = (
            update(DuplicateGroupReviewRecord)
            .where(
                ~DuplicateGroupReviewRecord.review_status.in_(
                    COMPLETED_DUPLICATE_REVIEW_STATUSES
                ),
                DuplicateGroupReviewRecord.draft_status != COVERAGE_PENDING_DRAFT_STATUS,
                resettable_state,
            )
            .values(
                manual_action=None,
                manual_primary_asset_id=None,
                member_decisions=[],
                stack_primary_asset_id=None,
                stack_resolution="move_selected",
                metadata_keeper_asset_id=None,
                draft_status="pending",
                review_status="pending",
                last_reviewed_at=now,
                updated_at=now,
            )
        )
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                delete(DuplicateGroupReviewRecord).where(
                    DuplicateGroupReviewRecord.draft_status == COVERAGE_PENDING_DRAFT_STATUS
                )
            )
            result = await session.execute(statement)
            await session.execute(
                delete(DuplicateReviewWorkspaceRecord).where(
                    DuplicateReviewWorkspaceRecord.workspace_key == WORKSPACE_KEY
                )
            )
        return max(0, int(getattr(result, "rowcount", 0) or 0))

    async def complete_draft(
        self,
        discovery_source: str,
        stable_group_key: str,
        member_fingerprint: str,
    ) -> None:
        """Consume only a successfully executed fingerprint-bound draft."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateGroupReviewRecord)
                .where(
                    DuplicateGroupReviewRecord.discovery_source == discovery_source,
                    DuplicateGroupReviewRecord.stable_group_key == stable_group_key,
                    DuplicateGroupReviewRecord.member_fingerprint == member_fingerprint,
                )
                .with_for_update()
            )
            if record is None:
                return
            now = datetime.now(UTC)
            record.member_decisions = [
                {**decision, "status": "completed"}
                for decision in list(record.member_decisions or [])
            ]
            if record.manual_action == "mixed" and record.review_status == "manually_configured":
                record.review_status = "reviewed_mixed"
            record.draft_status = "completed"
            record.updated_at = now

            if _source_value(discovery_source) != COMPANION_SIMILARITY_SOURCE:
                return
            parent_member_ids = _review_member_ids(record)
            if len(parent_member_ids) < 2:
                return
            coverage_statement = (
                select(DuplicateGroupReviewRecord)
                .where(
                    DuplicateGroupReviewRecord.discovery_source == IMMICH_DUPLICATE_SOURCE,
                    DuplicateGroupReviewRecord.draft_status == COVERAGE_PENDING_DRAFT_STATUS,
                )
                .with_for_update()
            )
            coverage_records = list((await session.scalars(coverage_statement)).all())
            for coverage in coverage_records:
                coverage_member_ids = _review_member_ids(coverage)
                if len(coverage_member_ids) < 2 or not coverage_member_ids.issubset(
                    parent_member_ids
                ):
                    continue
                coverage.member_decisions = [
                    {**decision, "status": "completed"}
                    for decision in list(coverage.member_decisions or [])
                ]
                coverage.draft_status = "inherited"
                coverage.review_status = record.review_status
                coverage.last_reviewed_at = now
                coverage.updated_at = now

    async def consume_workspace_groups(
        self,
        stable_group_keys: list[str],
        legacy_group_ids: list[str] | None = None,
    ) -> None:
        """Remove successful groups without discarding unrelated workspace state."""

        consumed_keys = set(stable_group_keys)
        consumed_legacy_ids = set(legacy_group_ids or [])
        if not consumed_keys and not consumed_legacy_ids:
            return
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateReviewWorkspaceRecord)
                .where(DuplicateReviewWorkspaceRecord.workspace_key == WORKSPACE_KEY)
                .with_for_update()
            )
            if record is None:
                return
            record.selected_groups = [
                item
                for item in list(record.selected_groups or [])
                if item.get("stable_group_key") not in consumed_keys
                and item.get("group_id") not in consumed_legacy_ids
            ]
            active_group = record.active_group or {}
            if (
                active_group.get("stable_group_key") in consumed_keys
                or active_group.get("group_id") in consumed_legacy_ids
            ):
                record.active_group = None
            record.revision += 1
            record.updated_at = datetime.now(UTC)

    async def get_workspace(self) -> DuplicateReviewWorkspaceRecord | None:
        async with self._database.sessions() as session:
            return await session.get(DuplicateReviewWorkspaceRecord, WORKSPACE_KEY)

    async def save_workspace(
        self,
        *,
        selected_groups: list[dict[str, str]],
        active_group: dict[str, str] | None,
        revision: int | None = None,
    ) -> DuplicateReviewWorkspaceRecord:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateReviewWorkspaceRecord)
                .where(DuplicateReviewWorkspaceRecord.workspace_key == WORKSPACE_KEY)
                .with_for_update()
            )
            if record is None:
                if revision not in {None, 0}:
                    raise ValueError("Duplicate workspace changed; reload its membership")
                record = DuplicateReviewWorkspaceRecord(
                    workspace_key=WORKSPACE_KEY,
                    revision=1,
                    selected_groups=selected_groups,
                    active_group=active_group,
                )
                session.add(record)
            else:
                if revision is not None and record.revision != revision:
                    raise ValueError("Duplicate workspace changed; reload its membership")
                record.selected_groups = selected_groups
                record.active_group = active_group
                record.revision += 1
                record.updated_at = datetime.now(UTC)
            await session.flush()
        return record

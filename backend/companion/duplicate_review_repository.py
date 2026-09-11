"""Persistence boundary for fingerprint-bound duplicate review decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.models import DuplicateGroupReviewRecord, DuplicateReviewWorkspaceRecord

WORKSPACE_KEY = "default"


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
        records = await self.get_many(discovery_source, [stable_group_key])
        return records[stable_group_key]

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
            record.member_decisions = [
                {**decision, "status": "completed"}
                for decision in list(record.member_decisions or [])
            ]
            record.draft_status = "completed"
            record.updated_at = datetime.now(UTC)

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

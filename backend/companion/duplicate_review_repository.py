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
        provider_group_ids: list[str],
    ) -> dict[str, DuplicateGroupReviewRecord]:
        if not provider_group_ids:
            return {}
        statement = select(DuplicateGroupReviewRecord).where(
            DuplicateGroupReviewRecord.discovery_source == discovery_source,
            DuplicateGroupReviewRecord.provider_group_id.in_(
                list(dict.fromkeys(provider_group_ids))
            ),
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.provider_group_id: record for record in records}

    async def save(
        self,
        *,
        discovery_source: str,
        provider_group_id: str,
        member_fingerprint: str,
        manual_action: str | None,
        manual_primary_asset_id: UUID | None,
        review_status: str,
    ) -> DuplicateGroupReviewRecord:
        now = datetime.now(UTC)
        values = {
            "discovery_source": discovery_source,
            "provider_group_id": provider_group_id,
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
                    constraint="uq_duplicate_group_reviews_provider",
                    set_={key: getattr(statement.excluded, key) for key in values},
                )
            )
        records = await self.get_many(discovery_source, [provider_group_id])
        return records[provider_group_id]

    async def save_draft(
        self,
        *,
        discovery_source: str,
        provider_group_id: str,
        member_fingerprint: str,
        member_decisions: list[dict[str, str]],
        stack_primary_asset_id: UUID | None,
        metadata_keeper_asset_id: UUID | None,
        draft_status: str,
    ) -> DuplicateGroupReviewRecord:
        now = datetime.now(UTC)
        values = {
            "discovery_source": discovery_source,
            "provider_group_id": provider_group_id,
            "member_fingerprint": member_fingerprint,
            "member_decisions": member_decisions,
            "stack_primary_asset_id": stack_primary_asset_id,
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
                    constraint="uq_duplicate_group_reviews_provider",
                    set_={key: getattr(statement.excluded, key) for key in values},
                )
            )
        records = await self.get_many(discovery_source, [provider_group_id])
        return records[provider_group_id]

    async def clear_decisions(
        self,
        discovery_source: str,
        provider_group_ids: list[str],
    ) -> None:
        """Clear review choices while retaining the provider identity record."""

        if not provider_group_ids:
            return
        now = datetime.now(UTC)
        statement = (
            update(DuplicateGroupReviewRecord)
            .where(
                DuplicateGroupReviewRecord.discovery_source == discovery_source,
                DuplicateGroupReviewRecord.provider_group_id.in_(
                    list(dict.fromkeys(provider_group_ids))
                ),
            )
            .values(
                manual_action=None,
                manual_primary_asset_id=None,
                member_decisions=[],
                stack_primary_asset_id=None,
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
        provider_group_id: str,
        member_fingerprint: str,
    ) -> None:
        """Consume only a successfully executed fingerprint-bound draft."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateGroupReviewRecord)
                .where(
                    DuplicateGroupReviewRecord.discovery_source == discovery_source,
                    DuplicateGroupReviewRecord.provider_group_id == provider_group_id,
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

    async def consume_workspace_groups(self, group_ids: list[str]) -> None:
        """Remove successful groups without discarding unrelated workspace state."""

        consumed = set(group_ids)
        if not consumed:
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
                if item.get("group_id") not in consumed
            ]
            if (record.active_group or {}).get("group_id") in consumed:
                record.active_group = None
            record.updated_at = datetime.now(UTC)

    async def get_workspace(self) -> DuplicateReviewWorkspaceRecord | None:
        async with self._database.sessions() as session:
            return await session.get(DuplicateReviewWorkspaceRecord, WORKSPACE_KEY)

    async def save_workspace(
        self,
        *,
        selected_groups: list[dict[str, str]],
        active_group: dict[str, str] | None,
    ) -> DuplicateReviewWorkspaceRecord:
        values = {
            "workspace_key": WORKSPACE_KEY,
            "selected_groups": selected_groups,
            "active_group": active_group,
            "updated_at": datetime.now(UTC),
        }
        async with self._database.sessions() as session, session.begin():
            statement = insert(DuplicateReviewWorkspaceRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[DuplicateReviewWorkspaceRecord.workspace_key],
                    set_={key: getattr(statement.excluded, key) for key in values},
                )
            )
        record = await self.get_workspace()
        assert record is not None
        return record

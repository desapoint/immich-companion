"""Persistence boundary for fingerprint-bound duplicate review decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
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

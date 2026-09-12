"""Typed selection persistence for non-asset Immich entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.models import SelectionSetKeyMemberRecord, SelectionSetRecord

RelationEntityKind = Literal["album", "tag"]


class RelationSelectionRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def create(self, kind: RelationEntityKind, ttl_seconds: int) -> SelectionSetRecord:
        now = datetime.now(UTC)
        record = SelectionSetRecord(
            entity_kind=kind, expires_at=now + timedelta(seconds=ttl_seconds)
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)
            await session.flush()
        return record

    async def get(self, selection_id: UUID, kind: RelationEntityKind) -> SelectionSetRecord | None:
        async with self._database.sessions() as session:
            record = await session.get(SelectionSetRecord, selection_id)
            return record if record is not None and record.entity_kind == kind else None

    async def ids(self, selection_id: UUID, kind: RelationEntityKind) -> list[UUID]:
        if await self.get(selection_id, kind) is None:
            raise ValueError("Selection set was not found")
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(SelectionSetKeyMemberRecord.entity_id)
                        .where(SelectionSetKeyMemberRecord.selection_id == selection_id)
                        .order_by(SelectionSetKeyMemberRecord.entity_id)
                    )
                ).all()
            )

    async def membership(
        self, selection_id: UUID, kind: RelationEntityKind, entity_ids: list[UUID]
    ) -> list[UUID]:
        if await self.get(selection_id, kind) is None:
            raise ValueError("Selection set was not found")
        if not entity_ids:
            return []
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(SelectionSetKeyMemberRecord.entity_id).where(
                            SelectionSetKeyMemberRecord.selection_id == selection_id,
                            SelectionSetKeyMemberRecord.entity_id.in_(entity_ids),
                        )
                    )
                ).all()
            )

    async def matching_count(
        self, selection_id: UUID, kind: RelationEntityKind, entity_ids: list[UUID]
    ) -> int:
        self._validate(await self.get(selection_id, kind))
        unique_ids = list(dict.fromkeys(entity_ids))
        count = 0
        async with self._database.sessions() as session:
            for offset in range(0, len(unique_ids), 1000):
                batch = unique_ids[offset : offset + 1000]
                count += int(
                    await session.scalar(
                        select(func.count())
                        .select_from(SelectionSetKeyMemberRecord)
                        .where(
                            SelectionSetKeyMemberRecord.selection_id == selection_id,
                            SelectionSetKeyMemberRecord.entity_id.in_(batch),
                        )
                    )
                )
        return count

    async def update(
        self,
        selection_id: UUID,
        kind: RelationEntityKind,
        entity_ids: list[UUID],
        *,
        selected: bool,
        revision: int,
    ) -> SelectionSetRecord:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SelectionSetRecord)
                .where(
                    SelectionSetRecord.id == selection_id,
                    SelectionSetRecord.entity_kind == kind,
                )
                .with_for_update()
            )
            self._validate(record, revision)
            assert record is not None
            if selected:
                await session.execute(
                    insert(SelectionSetKeyMemberRecord)
                    .values(
                        [
                            {"selection_id": selection_id, "entity_id": entity_id}
                            for entity_id in entity_ids
                        ]
                    )
                    .on_conflict_do_nothing()
                )
            else:
                await session.execute(
                    delete(SelectionSetKeyMemberRecord).where(
                        SelectionSetKeyMemberRecord.selection_id == selection_id,
                        SelectionSetKeyMemberRecord.entity_id.in_(entity_ids),
                    )
                )
            await self._touch(session, record)
            return record

    async def replace(
        self, selection_id: UUID, kind: RelationEntityKind, entity_ids: list[UUID]
    ) -> SelectionSetRecord:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SelectionSetRecord)
                .where(
                    SelectionSetRecord.id == selection_id,
                    SelectionSetRecord.entity_kind == kind,
                )
                .with_for_update()
            )
            self._validate(record)
            assert record is not None
            await session.execute(
                delete(SelectionSetKeyMemberRecord).where(
                    SelectionSetKeyMemberRecord.selection_id == selection_id
                )
            )
            unique_ids = list(dict.fromkeys(entity_ids))
            if unique_ids:
                await session.execute(
                    insert(SelectionSetKeyMemberRecord)
                    .values(
                        [
                            {"selection_id": selection_id, "entity_id": entity_id}
                            for entity_id in unique_ids
                        ]
                    )
                    .on_conflict_do_nothing()
                )
            await self._touch(session, record)
            return record

    async def update_matching(
        self,
        selection_id: UUID,
        kind: RelationEntityKind,
        entity_ids: list[UUID],
        *,
        selected: bool,
        revision: int,
    ) -> SelectionSetRecord:
        """Apply a query-resolved delta without discarding unrelated members."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SelectionSetRecord)
                .where(
                    SelectionSetRecord.id == selection_id,
                    SelectionSetRecord.entity_kind == kind,
                )
                .with_for_update()
            )
            self._validate(record, revision)
            assert record is not None
            unique_ids = list(dict.fromkeys(entity_ids))
            for offset in range(0, len(unique_ids), 1000):
                batch = unique_ids[offset : offset + 1000]
                if selected:
                    await session.execute(
                        insert(SelectionSetKeyMemberRecord)
                        .values(
                            [
                                {"selection_id": selection_id, "entity_id": entity_id}
                                for entity_id in batch
                            ]
                        )
                        .on_conflict_do_nothing()
                    )
                else:
                    await session.execute(
                        delete(SelectionSetKeyMemberRecord).where(
                            SelectionSetKeyMemberRecord.selection_id == selection_id,
                            SelectionSetKeyMemberRecord.entity_id.in_(batch),
                        )
                    )
            await self._touch(session, record)
            return record

    async def remove(self, selection_id: UUID, entity_ids: list[UUID]) -> None:
        if not entity_ids:
            return
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SelectionSetRecord)
                .where(SelectionSetRecord.id == selection_id)
                .with_for_update()
            )
            if record is None:
                return
            await session.execute(
                delete(SelectionSetKeyMemberRecord).where(
                    SelectionSetKeyMemberRecord.selection_id == selection_id,
                    SelectionSetKeyMemberRecord.entity_id.in_(entity_ids),
                )
            )
            await self._touch(session, record)

    @staticmethod
    def _validate(record: SelectionSetRecord | None, revision: int | None = None) -> None:
        if record is None:
            raise ValueError("Selection set was not found")
        if record.status != "active" or record.expires_at <= datetime.now(UTC):
            raise ValueError("Selection set has expired")
        if revision is not None and record.revision != revision:
            raise ValueError("Selection set changed; reload its membership")

    @staticmethod
    async def _touch(session, record: SelectionSetRecord) -> None:
        record.selected_count = int(
            await session.scalar(
                select(func.count())
                .select_from(SelectionSetKeyMemberRecord)
                .where(SelectionSetKeyMemberRecord.selection_id == record.id)
            )
        )
        record.revision += 1
        record.updated_at = datetime.now(UTC)
        await session.flush()

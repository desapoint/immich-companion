"""Persisted runtime settings that control global-sync host pressure."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select, text

from companion.config import Settings
from companion.database import DatabaseManager
from companion.models import SyncRuntimeSettingsRecord


class SyncRuntimeSettings(BaseModel):
    full_batch_size: int = Field(ge=1, le=500)
    full_min_batch_delay_seconds: float = Field(ge=0, le=60)
    tag_association_concurrency: int = Field(ge=1, le=32)


class SyncRuntimeSettingsUpdate(SyncRuntimeSettings):
    """The complete user-editable global-sync pacing configuration."""


class SyncRuntimeSettingsRepository:
    def __init__(self, database: DatabaseManager, defaults: Settings) -> None:
        self._database = database
        self._defaults = defaults

    def _default(self) -> SyncRuntimeSettings:
        return SyncRuntimeSettings(
            full_batch_size=self._defaults.sync_full_batch_size,
            full_min_batch_delay_seconds=self._defaults.sync_full_min_batch_delay_seconds,
            tag_association_concurrency=self._defaults.sync_tag_association_concurrency,
        )

    async def get(self) -> SyncRuntimeSettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SyncRuntimeSettingsRecord)
                .where(SyncRuntimeSettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                default = self._default()
                record = SyncRuntimeSettingsRecord(
                    id=1,
                    full_batch_size=default.full_batch_size,
                    full_min_batch_delay_seconds=default.full_min_batch_delay_seconds,
                )
                session.add(record)
                await session.flush()
            tag_association_concurrency = await session.scalar(
                text(
                    "SELECT tag_association_concurrency "
                    "FROM sync_runtime_settings WHERE id = 1"
                )
            )
            return SyncRuntimeSettings(
                full_batch_size=record.full_batch_size,
                full_min_batch_delay_seconds=record.full_min_batch_delay_seconds,
                tag_association_concurrency=int(
                    tag_association_concurrency
                    if tag_association_concurrency is not None
                    else self._defaults.sync_tag_association_concurrency
                ),
            )

    async def update(self, value: SyncRuntimeSettingsUpdate) -> SyncRuntimeSettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SyncRuntimeSettingsRecord)
                .where(SyncRuntimeSettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = SyncRuntimeSettingsRecord(id=1)
                session.add(record)
                await session.flush()
            record.full_batch_size = value.full_batch_size
            record.full_min_batch_delay_seconds = value.full_min_batch_delay_seconds
            await session.execute(
                text(
                    "UPDATE sync_runtime_settings "
                    "SET tag_association_concurrency = :concurrency WHERE id = 1"
                ),
                {"concurrency": value.tag_association_concurrency},
            )
            return SyncRuntimeSettings.model_validate(value)


class DefaultSyncRuntimeSettingsRepository:
    """Settings fallback for in-memory unit tests without companion PostgreSQL."""

    def __init__(self, defaults: Settings) -> None:
        self._value = SyncRuntimeSettings(
            full_batch_size=defaults.sync_full_batch_size,
            full_min_batch_delay_seconds=defaults.sync_full_min_batch_delay_seconds,
            tag_association_concurrency=defaults.sync_tag_association_concurrency,
        )

    async def get(self) -> SyncRuntimeSettings:
        return self._value

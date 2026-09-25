"""Persisted runtime settings that control global-sync host pressure."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from companion.config import (
    SYNC_FULL_BATCH_SIZE_MAX,
    SYNC_FULL_MIN_BATCH_DELAY_SECONDS_MAX,
    SYNC_INCREMENTAL_OVERLAP_SECONDS_MAX,
    SYNC_METADATA_REQUEST_CONCURRENCY_MAX,
    SYNC_PAGE_PREFETCH_MAX,
    SYNC_TAG_ASSOCIATION_CONCURRENCY_MAX,
    Settings,
)
from companion.database import DatabaseManager
from companion.models import SyncRuntimeSettingsRecord


class SyncRuntimeSettings(BaseModel):
    full_batch_size: int = Field(ge=1, le=SYNC_FULL_BATCH_SIZE_MAX)
    full_min_batch_delay_seconds: float = Field(
        ge=0, le=SYNC_FULL_MIN_BATCH_DELAY_SECONDS_MAX
    )
    tag_association_concurrency: int = Field(
        default=4, ge=1, le=SYNC_TAG_ASSOCIATION_CONCURRENCY_MAX
    )
    metadata_request_concurrency: int = Field(
        default=4, ge=1, le=SYNC_METADATA_REQUEST_CONCURRENCY_MAX
    )
    page_prefetch: int = Field(default=1, ge=0, le=SYNC_PAGE_PREFETCH_MAX)
    api_page_size: int = Field(default=1000, ge=25, le=1000)
    incremental_overlap_seconds: int = Field(
        default=300, ge=0, le=SYNC_INCREMENTAL_OVERLAP_SECONDS_MAX
    )
    incremental_strategy: Literal["automatic", "asset", "relation"] = "automatic"
    adaptive_throttling: bool = True


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
            metadata_request_concurrency=self._defaults.sync_metadata_request_concurrency,
            page_prefetch=self._defaults.sync_page_prefetch,
            api_page_size=self._defaults.sync_media_page_size,
            incremental_overlap_seconds=self._defaults.sync_overlap_seconds,
            incremental_strategy=self._defaults.sync_incremental_strategy,
            adaptive_throttling=self._defaults.sync_adaptive_throttling,
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
                    tag_association_concurrency=default.tag_association_concurrency,
                    metadata_request_concurrency=default.metadata_request_concurrency,
                    page_prefetch=default.page_prefetch,
                    api_page_size=default.api_page_size,
                    incremental_overlap_seconds=default.incremental_overlap_seconds,
                    incremental_strategy=default.incremental_strategy,
                    adaptive_throttling=default.adaptive_throttling,
                )
                session.add(record)
                await session.flush()
            return SyncRuntimeSettings(
                full_batch_size=record.full_batch_size,
                full_min_batch_delay_seconds=record.full_min_batch_delay_seconds,
                tag_association_concurrency=record.tag_association_concurrency,
                metadata_request_concurrency=record.metadata_request_concurrency,
                page_prefetch=record.page_prefetch,
                api_page_size=record.api_page_size,
                incremental_overlap_seconds=record.incremental_overlap_seconds,
                incremental_strategy=record.incremental_strategy,
                adaptive_throttling=record.adaptive_throttling,
            )

    async def update(self, value: SyncRuntimeSettingsUpdate) -> SyncRuntimeSettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SyncRuntimeSettingsRecord)
                .where(SyncRuntimeSettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = SyncRuntimeSettingsRecord(
                    id=1,
                    full_batch_size=value.full_batch_size,
                    full_min_batch_delay_seconds=value.full_min_batch_delay_seconds,
                    tag_association_concurrency=value.tag_association_concurrency,
                    metadata_request_concurrency=value.metadata_request_concurrency,
                    page_prefetch=value.page_prefetch,
                    api_page_size=value.api_page_size,
                    incremental_overlap_seconds=value.incremental_overlap_seconds,
                    incremental_strategy=value.incremental_strategy,
                    adaptive_throttling=value.adaptive_throttling,
                )
                session.add(record)
            else:
                record.full_batch_size = value.full_batch_size
                record.full_min_batch_delay_seconds = value.full_min_batch_delay_seconds
                record.tag_association_concurrency = value.tag_association_concurrency
                record.metadata_request_concurrency = value.metadata_request_concurrency
                record.page_prefetch = value.page_prefetch
                record.api_page_size = value.api_page_size
                record.incremental_overlap_seconds = value.incremental_overlap_seconds
                record.incremental_strategy = value.incremental_strategy
                record.adaptive_throttling = value.adaptive_throttling
            return SyncRuntimeSettings.model_validate(value)


class DefaultSyncRuntimeSettingsRepository:
    """Settings fallback for in-memory unit tests without companion PostgreSQL."""

    def __init__(self, defaults: Settings) -> None:
        self._value = SyncRuntimeSettings(
            full_batch_size=defaults.sync_full_batch_size,
            full_min_batch_delay_seconds=defaults.sync_full_min_batch_delay_seconds,
            tag_association_concurrency=defaults.sync_tag_association_concurrency,
            metadata_request_concurrency=defaults.sync_metadata_request_concurrency,
            page_prefetch=defaults.sync_page_prefetch,
            api_page_size=defaults.sync_media_page_size,
            incremental_overlap_seconds=defaults.sync_overlap_seconds,
            incremental_strategy=defaults.sync_incremental_strategy,
            adaptive_throttling=defaults.sync_adaptive_throttling,
        )

    async def get(self) -> SyncRuntimeSettings:
        return self._value

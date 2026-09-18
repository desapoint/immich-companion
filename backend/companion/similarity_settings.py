"""Persisted runtime settings for library similarity fingerprinting."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select

from companion.config import Settings
from companion.database import DatabaseManager
from companion.models import SimilarityRuntimeSettingsRecord


class SimilarityRuntimeSettings(BaseModel):
    fingerprint_page_size: int = Field(ge=25, le=2000)


class SimilarityRuntimeSettingsUpdate(SimilarityRuntimeSettings):
    """Complete user-editable similarity fingerprint runtime configuration."""


class SimilarityRuntimeSettingsRepository:
    def __init__(self, database: DatabaseManager, defaults: Settings) -> None:
        self._database = database
        self._defaults = defaults

    def _default(self) -> SimilarityRuntimeSettings:
        return SimilarityRuntimeSettings(
            fingerprint_page_size=self._defaults.similarity_fingerprint_page_size,
        )

    async def get(self) -> SimilarityRuntimeSettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SimilarityRuntimeSettingsRecord)
                .where(SimilarityRuntimeSettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                default = self._default()
                record = SimilarityRuntimeSettingsRecord(
                    id=1,
                    fingerprint_page_size=default.fingerprint_page_size,
                )
                session.add(record)
                await session.flush()
            return SimilarityRuntimeSettings(
                fingerprint_page_size=record.fingerprint_page_size,
            )

    async def update(
        self, value: SimilarityRuntimeSettingsUpdate
    ) -> SimilarityRuntimeSettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SimilarityRuntimeSettingsRecord)
                .where(SimilarityRuntimeSettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = SimilarityRuntimeSettingsRecord(
                    id=1,
                    fingerprint_page_size=value.fingerprint_page_size,
                )
                session.add(record)
            else:
                record.fingerprint_page_size = value.fingerprint_page_size
            await session.flush()
            return SimilarityRuntimeSettings.model_validate(value)

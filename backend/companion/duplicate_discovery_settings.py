"""Persisted user-editable defaults for duplicate discovery."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from companion.database import DatabaseManager
from companion.models import DuplicateDiscoverySettingsRecord


class DuplicateDiscoverySettings(BaseModel):
    include_exact: bool = True
    include_similar: bool = True
    similarity_threshold: float = Field(default=95.0, ge=50, le=100)
    maximum_perceptual_distance: int = Field(default=12, ge=0, le=64)
    validation_mode: Literal["reference", "linked", "strict"] = "strict"
    max_link_depth: int = Field(default=2, ge=0, le=64)
    max_candidates: int = Field(default=8, ge=1, le=64)


class DuplicateDiscoverySettingsUpdate(DuplicateDiscoverySettings):
    """Complete persisted duplicate-discovery configuration."""


# These fields can change which assets become members of similarity-derived duplicate
# groups. They are classified so the explicit discovery workflow can decide what work
# to run; persisting settings itself intentionally has no orchestration side effects.
MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS = frozenset(
    {
        "similarity_threshold",
        "maximum_perceptual_distance",
        "validation_mode",
        "max_link_depth",
        "max_candidates",
    }
)

# These flags choose which discovery jobs the UI runs. They do not alter the semantics
# of an already-produced similarity scan or composite projection.
ORCHESTRATION_ONLY_DISCOVERY_FIELDS = frozenset({"include_exact", "include_similar"})


class DuplicateDiscoverySettingsRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def get(self) -> DuplicateDiscoverySettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateDiscoverySettingsRecord)
                .where(DuplicateDiscoverySettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                settings = DuplicateDiscoverySettings()
                record = DuplicateDiscoverySettingsRecord(
                    id=1,
                    **settings.model_dump(),
                )
                session.add(record)
                await session.flush()
                return settings
            return DuplicateDiscoverySettings(
                include_exact=record.include_exact,
                include_similar=record.include_similar,
                similarity_threshold=record.similarity_threshold,
                maximum_perceptual_distance=record.maximum_perceptual_distance,
                validation_mode=record.validation_mode,
                max_link_depth=record.max_link_depth,
                max_candidates=record.max_candidates,
            )

    async def update(
        self,
        value: DuplicateDiscoverySettingsUpdate,
    ) -> DuplicateDiscoverySettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateDiscoverySettingsRecord)
                .where(DuplicateDiscoverySettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = DuplicateDiscoverySettingsRecord(id=1)
                session.add(record)
            for key, item in value.model_dump().items():
                setattr(record, key, item)
            await session.flush()

        return DuplicateDiscoverySettings(**value.model_dump())

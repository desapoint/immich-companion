"""Persisted user-editable defaults for duplicate discovery."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from companion.database import DatabaseManager
from companion.duplicate_schema import SimilarityScanRequest
from companion.models import DuplicateDiscoverySettingsRecord
from companion.similarity_generation import SimilarityEvidenceEpochRepository


class DuplicateDiscoverySettings(BaseModel):
    include_exact: bool = True
    include_similar: bool = True
    similarity_threshold: float = Field(default=95.0, ge=50, le=100)
    validation_mode: Literal["reference", "linked", "strict"] = "strict"
    max_link_depth: int = Field(default=2, ge=0, le=64)
    max_candidates: int = Field(default=8, ge=1, le=64)


class DuplicateDiscoverySettingsUpdate(DuplicateDiscoverySettings):
    """Complete persisted duplicate-discovery configuration."""


# These fields can change which assets become members of similarity-derived duplicate
# groups. Any changed value must cross the evidence-generation boundary so persisted
# similarity evidence and the derived composite projection cannot survive with stale
# membership semantics.
MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS = frozenset(
    {
        "similarity_threshold",
        "validation_mode",
        "max_link_depth",
        "max_candidates",
    }
)

# These flags choose which discovery jobs the UI runs. They do not alter the semantics
# of an already-produced similarity scan or composite projection.
ORCHESTRATION_ONLY_DISCOVERY_FIELDS = frozenset({"include_exact", "include_similar"})


def _membership_configuration(
    value: DuplicateDiscoverySettings,
) -> dict[str, object]:
    return value.model_dump(include=MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS)


def _replacement_scan_payload(
    value: DuplicateDiscoverySettings,
) -> dict[str, object]:
    return SimilarityScanRequest(
        similarity_threshold=value.similarity_threshold,
        validation_mode=value.validation_mode,
        max_link_depth=value.max_link_depth,
        maximum_neighbors_per_asset=value.max_candidates,
    ).model_dump(mode="json")


class DuplicateDiscoverySettingsRepository:
    def __init__(
        self,
        database: DatabaseManager,
        evidence_epoch: SimilarityEvidenceEpochRepository | None = None,
    ) -> None:
        self._database = database
        self._evidence_epoch = evidence_epoch or SimilarityEvidenceEpochRepository(database)

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
            previous = (
                DuplicateDiscoverySettings()
                if record is None
                else DuplicateDiscoverySettings(
                    include_exact=record.include_exact,
                    include_similar=record.include_similar,
                    similarity_threshold=record.similarity_threshold,
                    validation_mode=record.validation_mode,
                    max_link_depth=record.max_link_depth,
                    max_candidates=record.max_candidates,
                )
            )
            if record is None:
                record = DuplicateDiscoverySettingsRecord(id=1)
                session.add(record)
            for key, item in value.model_dump().items():
                setattr(record, key, item)
            await session.flush()

            if _membership_configuration(previous) != _membership_configuration(value):
                await self._evidence_epoch.rebuild_in_session(
                    session,
                    _replacement_scan_payload(value),
                )

        return DuplicateDiscoverySettings(**value.model_dump())

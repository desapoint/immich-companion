"""Persisted user-editable defaults for duplicate discovery."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from companion.database import DatabaseManager
from companion.models import DuplicateDiscoverySettingsRecord


class DuplicateDiscoverySettings(BaseModel):
    include_exact: bool = True
    include_similar: bool = True
    similarity_threshold: float = Field(default=95.0, ge=50, le=100)
    maximum_perceptual_distance: int = Field(default=12, ge=0, le=64)
    comparison_max_displacement_percent: int = Field(default=10, ge=0, le=20)
    comparison_max_rotation_degrees: int = Field(default=0, ge=0, le=5)
    validation_mode: Literal["reference", "linked", "strict"] = "strict"
    max_link_depth: int = Field(default=2, ge=0, le=64)
    max_candidates: int = Field(default=8, ge=1, le=64)
    maximum_matches: int = Field(default=5000, ge=1, le=50_000)


class DuplicateDiscoverySettingsUpdate(DuplicateDiscoverySettings):
    """Complete persisted duplicate-discovery configuration."""


class DuplicateDiscoverySettingsPatch(BaseModel):
    """Partial update for discovery controls; alignment fields are deliberately excluded."""

    include_exact: bool | None = None
    include_similar: bool | None = None
    similarity_threshold: float | None = Field(default=None, ge=50, le=100)
    maximum_perceptual_distance: int | None = Field(default=None, ge=0, le=64)
    validation_mode: Literal["reference", "linked", "strict"] | None = None
    max_link_depth: int | None = Field(default=None, ge=0, le=64)
    max_candidates: int | None = Field(default=None, ge=1, le=64)
    maximum_matches: int | None = Field(default=None, ge=1, le=50_000)

    @model_validator(mode="after")
    def reject_empty_or_null_patch(self) -> DuplicateDiscoverySettingsPatch:
        if not self.model_fields_set:
            raise ValueError("At least one duplicate discovery setting is required")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Duplicate discovery settings cannot be null")
        return self


class ComparisonAlignmentSettings(BaseModel):
    comparison_max_displacement_percent: int = Field(default=10, ge=0, le=20)
    comparison_max_rotation_degrees: int = Field(default=0, ge=0, le=5)


class ComparisonAlignmentSettingsUpdate(ComparisonAlignmentSettings):
    """Validated partial settings for localized comparison alignment."""


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
        "maximum_matches",
    }
)

# These flags choose which discovery jobs the UI runs. They do not alter the semantics
# of an already-produced similarity scan or composite projection.
ORCHESTRATION_ONLY_DISCOVERY_FIELDS = frozenset({"include_exact", "include_similar"})

# These values affect only the interactive comparison diagnostics. They do not
# change which assets are discovered or the evidence generation.
COMPARISON_ONLY_DISCOVERY_FIELDS = frozenset(
    {"comparison_max_displacement_percent", "comparison_max_rotation_degrees"}
)


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
                comparison_max_displacement_percent=record.comparison_max_displacement_percent,
                comparison_max_rotation_degrees=record.comparison_max_rotation_degrees,
                validation_mode=record.validation_mode,
                max_link_depth=record.max_link_depth,
                max_candidates=record.max_candidates,
                maximum_matches=record.maximum_matches,
            )

    async def update(
        self,
        value: DuplicateDiscoverySettingsUpdate,
    ) -> DuplicateDiscoverySettings:
        supplied_fields = value.model_fields_set
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateDiscoverySettingsRecord)
                .where(DuplicateDiscoverySettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = DuplicateDiscoverySettingsRecord(
                    id=1,
                    **DuplicateDiscoverySettings().model_dump(),
                )
                session.add(record)
            for key, item in value.model_dump().items():
                # Older clients PUT the discovery document without the newly added
                # comparison-only fields. Pydantic supplies defaults for those, but
                # omission must not reset values saved by a newer client.
                if key in COMPARISON_ONLY_DISCOVERY_FIELDS and key not in supplied_fields:
                    continue
                setattr(record, key, item)
            await session.flush()
            result = DuplicateDiscoverySettings(
                include_exact=record.include_exact,
                include_similar=record.include_similar,
                similarity_threshold=record.similarity_threshold,
                maximum_perceptual_distance=record.maximum_perceptual_distance,
                comparison_max_displacement_percent=record.comparison_max_displacement_percent,
                comparison_max_rotation_degrees=record.comparison_max_rotation_degrees,
                validation_mode=record.validation_mode,
                max_link_depth=record.max_link_depth,
                max_candidates=record.max_candidates,
                maximum_matches=record.maximum_matches,
            )
        return result

    async def update_discovery_settings(
        self,
        value: DuplicateDiscoverySettingsPatch,
    ) -> DuplicateDiscoverySettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateDiscoverySettingsRecord)
                .where(DuplicateDiscoverySettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = DuplicateDiscoverySettingsRecord(
                    id=1,
                    **DuplicateDiscoverySettings().model_dump(),
                )
                session.add(record)
            for key, item in value.model_dump(exclude_unset=True).items():
                setattr(record, key, item)
            await session.flush()
            result = DuplicateDiscoverySettings(
                include_exact=record.include_exact,
                include_similar=record.include_similar,
                similarity_threshold=record.similarity_threshold,
                maximum_perceptual_distance=record.maximum_perceptual_distance,
                comparison_max_displacement_percent=record.comparison_max_displacement_percent,
                comparison_max_rotation_degrees=record.comparison_max_rotation_degrees,
                validation_mode=record.validation_mode,
                max_link_depth=record.max_link_depth,
                max_candidates=record.max_candidates,
                maximum_matches=record.maximum_matches,
            )
        return result

    async def comparison_alignment(self) -> ComparisonAlignmentSettings:
        settings = await self.get()
        return ComparisonAlignmentSettings(
            comparison_max_displacement_percent=settings.comparison_max_displacement_percent,
            comparison_max_rotation_degrees=settings.comparison_max_rotation_degrees,
        )

    async def update_comparison_alignment(
        self,
        value: ComparisonAlignmentSettingsUpdate,
    ) -> ComparisonAlignmentSettings:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicateDiscoverySettingsRecord)
                .where(DuplicateDiscoverySettingsRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = DuplicateDiscoverySettingsRecord(
                    id=1,
                    **DuplicateDiscoverySettings().model_dump(),
                )
                session.add(record)
            record.comparison_max_displacement_percent = (
                value.comparison_max_displacement_percent
            )
            record.comparison_max_rotation_degrees = value.comparison_max_rotation_degrees
            await session.flush()
        return value

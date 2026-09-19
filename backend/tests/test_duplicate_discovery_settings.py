from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from companion.duplicate_discovery_settings import (
    MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS,
    ORCHESTRATION_ONLY_DISCOVERY_FIELDS,
    DuplicateDiscoverySettings,
    DuplicateDiscoverySettingsRepository,
    DuplicateDiscoverySettingsUpdate,
)


def test_duplicate_discovery_settings_defaults_match_v2_discovery_defaults() -> None:
    settings = DuplicateDiscoverySettings()

    assert settings.include_exact is True
    assert settings.include_similar is True
    assert settings.similarity_threshold == 95.0
    assert settings.validation_mode == "strict"
    assert settings.max_link_depth == 2
    assert settings.max_candidates == 8


def test_every_discovery_setting_is_explicitly_classified_for_generation_impact() -> None:
    assert MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS.isdisjoint(
        ORCHESTRATION_ONLY_DISCOVERY_FIELDS
    )
    assert (
        set(DuplicateDiscoverySettings.model_fields)
        == MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS | ORCHESTRATION_ONLY_DISCOVERY_FIELDS
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("similarity_threshold", 49.9),
        ("similarity_threshold", 100.1),
        ("validation_mode", "unknown"),
        ("max_link_depth", -1),
        ("max_link_depth", 65),
        ("max_candidates", 0),
        ("max_candidates", 65),
    ],
)
def test_duplicate_discovery_settings_reject_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        DuplicateDiscoverySettings(**{field: value})


class _Session:
    def __init__(self, record) -> None:
        self.record = record
        self.added = None
        self.flushed = False

    @asynccontextmanager
    async def begin(self):
        yield self

    async def scalar(self, _statement):
        return self.record

    def add(self, record) -> None:
        self.record = record
        self.added = record

    async def flush(self) -> None:
        self.flushed = True


class _Database:
    def __init__(self, record) -> None:
        self.session = _Session(record)

    @asynccontextmanager
    async def sessions(self):
        yield self.session



def _record(**overrides):
    values = DuplicateDiscoverySettings().model_dump()
    values.update(overrides)
    return SimpleNamespace(id=1, **values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("similarity_threshold", 94.0),
        ("validation_mode", "linked"),
        ("max_link_depth", 4),
        ("max_candidates", 12),
    ],
)
async def test_membership_affecting_setting_change_only_persists_configuration(
    field: str,
    value: object,
) -> None:
    database = _Database(_record())
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]
    payload = DuplicateDiscoverySettings().model_dump()
    payload[field] = value

    saved = await repository.update(DuplicateDiscoverySettingsUpdate(**payload))

    assert getattr(saved, field) == value
    assert getattr(database.session.record, field) == value
    assert database.session.flushed is True


@pytest.mark.asyncio
async def test_unchanged_membership_settings_do_not_schedule_rebuild() -> None:
    database = _Database(_record())
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]

    await repository.update(DuplicateDiscoverySettingsUpdate())

    assert database.session.flushed is True


@pytest.mark.asyncio
async def test_orchestration_only_setting_change_does_not_invalidate_similarity_generation(
) -> None:
    database = _Database(_record())
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]

    await repository.update(
        DuplicateDiscoverySettingsUpdate(
            include_exact=False,
            include_similar=False,
        )
    )

    assert database.session.flushed is True


@pytest.mark.asyncio
async def test_first_persisted_nondefault_membership_configuration_only_persists() -> None:
    database = _Database(None)
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]

    saved = await repository.update(DuplicateDiscoverySettingsUpdate(max_link_depth=5))

    assert database.session.added is not None
    assert saved.max_link_depth == 5
    assert database.session.record.max_link_depth == 5

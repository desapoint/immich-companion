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
        MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS | ORCHESTRATION_ONLY_DISCOVERY_FIELDS
        == set(DuplicateDiscoverySettings.model_fields)
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


class _EvidenceEpoch:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []

    async def rebuild_in_session(self, session, payload):
        self.calls.append((session, payload))
        return 0, {}, SimpleNamespace(int=1)


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
async def test_membership_affecting_setting_change_atomically_schedules_rebuild(
    field: str,
    value: object,
) -> None:
    database = _Database(_record())
    evidence_epoch = _EvidenceEpoch()
    repository = DuplicateDiscoverySettingsRepository(  # type: ignore[arg-type]
        database,
        evidence_epoch=evidence_epoch,  # type: ignore[arg-type]
    )
    payload = DuplicateDiscoverySettings().model_dump()
    payload[field] = value

    saved = await repository.update(DuplicateDiscoverySettingsUpdate(**payload))

    assert getattr(saved, field) == value
    assert database.session.flushed is True
    assert len(evidence_epoch.calls) == 1
    session, scan_payload = evidence_epoch.calls[0]
    assert session is database.session
    assert scan_payload["similarity_threshold"] == saved.similarity_threshold
    assert scan_payload["validation_mode"] == saved.validation_mode
    assert scan_payload["max_link_depth"] == saved.max_link_depth
    assert scan_payload["maximum_neighbors_per_asset"] == saved.max_candidates
    assert scan_payload["anchor_asset_id"] is None
    assert scan_payload["scope"] == "all_eligible_assets"


@pytest.mark.asyncio
async def test_unchanged_membership_settings_do_not_schedule_rebuild() -> None:
    database = _Database(_record())
    evidence_epoch = _EvidenceEpoch()
    repository = DuplicateDiscoverySettingsRepository(  # type: ignore[arg-type]
        database,
        evidence_epoch=evidence_epoch,  # type: ignore[arg-type]
    )

    await repository.update(DuplicateDiscoverySettingsUpdate())

    assert evidence_epoch.calls == []


@pytest.mark.asyncio
async def test_orchestration_only_setting_change_does_not_invalidate_similarity_generation() -> None:
    database = _Database(_record())
    evidence_epoch = _EvidenceEpoch()
    repository = DuplicateDiscoverySettingsRepository(  # type: ignore[arg-type]
        database,
        evidence_epoch=evidence_epoch,  # type: ignore[arg-type]
    )

    await repository.update(
        DuplicateDiscoverySettingsUpdate(
            include_exact=False,
            include_similar=False,
        )
    )

    assert evidence_epoch.calls == []


@pytest.mark.asyncio
async def test_first_persisted_nondefault_membership_configuration_schedules_rebuild() -> None:
    database = _Database(None)
    evidence_epoch = _EvidenceEpoch()
    repository = DuplicateDiscoverySettingsRepository(  # type: ignore[arg-type]
        database,
        evidence_epoch=evidence_epoch,  # type: ignore[arg-type]
    )

    await repository.update(DuplicateDiscoverySettingsUpdate(max_link_depth=5))

    assert database.session.added is not None
    assert len(evidence_epoch.calls) == 1
    assert evidence_epoch.calls[0][1]["max_link_depth"] == 5

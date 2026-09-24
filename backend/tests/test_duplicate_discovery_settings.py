from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from companion.duplicate_discovery_settings import (
    COMPARISON_ONLY_DISCOVERY_FIELDS,
    MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS,
    ORCHESTRATION_ONLY_DISCOVERY_FIELDS,
    ComparisonAlignmentSettingsUpdate,
    DuplicateDiscoverySettings,
    DuplicateDiscoverySettingsPatch,
    DuplicateDiscoverySettingsRepository,
    DuplicateDiscoverySettingsUpdate,
)
from companion.sync_settings_routes import register_sync_settings_routes


def test_duplicate_discovery_settings_defaults_match_v2_discovery_defaults() -> None:
    settings = DuplicateDiscoverySettings()

    assert settings.include_exact is True
    assert settings.include_similar is True
    assert settings.similarity_threshold == 95.0
    assert settings.maximum_perceptual_distance == 12
    assert settings.comparison_max_displacement_percent == 10
    assert settings.comparison_max_rotation_degrees == 0
    assert settings.validation_mode == "strict"
    assert settings.max_link_depth == 2
    assert settings.max_candidates == 8
    assert settings.maximum_matches == 5000


def test_every_discovery_setting_is_explicitly_classified_for_generation_impact() -> None:
    assert MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS.isdisjoint(
        ORCHESTRATION_ONLY_DISCOVERY_FIELDS
    )
    assert COMPARISON_ONLY_DISCOVERY_FIELDS.isdisjoint(
        MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS | ORCHESTRATION_ONLY_DISCOVERY_FIELDS
    )
    assert (
        set(DuplicateDiscoverySettings.model_fields)
        == MEMBERSHIP_AFFECTING_DISCOVERY_FIELDS
        | ORCHESTRATION_ONLY_DISCOVERY_FIELDS
        | COMPARISON_ONLY_DISCOVERY_FIELDS
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("similarity_threshold", 49.9),
        ("similarity_threshold", 100.1),
        ("maximum_perceptual_distance", -1),
        ("maximum_perceptual_distance", 65),
        ("comparison_max_displacement_percent", -1),
        ("comparison_max_displacement_percent", 21),
        ("comparison_max_rotation_degrees", -1),
        ("comparison_max_rotation_degrees", 6),
        ("validation_mode", "unknown"),
        ("max_link_depth", -1),
        ("max_link_depth", 65),
        ("max_candidates", 0),
        ("max_candidates", 65),
        ("maximum_matches", 0),
        ("maximum_matches", 50_001),
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
        ("maximum_perceptual_distance", 14),
        ("validation_mode", "linked"),
        ("max_link_depth", 4),
        ("max_candidates", 12),
        ("maximum_matches", 12_000),
        ("comparison_max_displacement_percent", 14),
        ("comparison_max_rotation_degrees", 3),
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


@pytest.mark.asyncio
async def test_legacy_full_update_preserves_alignment_fields_omitted_from_payload() -> None:
    database = _Database(
        _record(comparison_max_displacement_percent=17, comparison_max_rotation_degrees=4)
    )
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]

    saved = await repository.update(
        DuplicateDiscoverySettingsUpdate(
            include_exact=True,
            include_similar=True,
            similarity_threshold=95,
            maximum_perceptual_distance=12,
            validation_mode="strict",
            max_link_depth=2,
            max_candidates=8,
            maximum_matches=5000,
        )
    )

    assert saved.comparison_max_displacement_percent == 17
    assert saved.comparison_max_rotation_degrees == 4
    assert database.session.record.comparison_max_displacement_percent == 17
    assert database.session.record.comparison_max_rotation_degrees == 4


@pytest.mark.asyncio
async def test_full_update_can_explicitly_reset_alignment_fields_to_defaults() -> None:
    database = _Database(
        _record(comparison_max_displacement_percent=17, comparison_max_rotation_degrees=4)
    )
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]

    saved = await repository.update(
        DuplicateDiscoverySettingsUpdate(
            comparison_max_displacement_percent=10,
            comparison_max_rotation_degrees=0,
        )
    )

    assert saved.comparison_max_displacement_percent == 10
    assert saved.comparison_max_rotation_degrees == 0


def test_legacy_discovery_put_preserves_custom_comparison_alignment_settings() -> None:
    database = _Database(
        _record(comparison_max_displacement_percent=17, comparison_max_rotation_degrees=4)
    )
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]
    app = FastAPI()
    register_sync_settings_routes(
        app,
        asset_sync=None,
        database=None,
        immich=None,  # type: ignore[arg-type]
        runtime_settings=None,
        similarity_runtime_settings_repository=None,
        duplicate_discovery_settings_repository=repository,
        duplicate_policy_repository=None,
        task_coordinator=None,
        require_asset_repository=lambda: None,
        require_immich=lambda: None,  # type: ignore[arg-type]
        require_immich_duplicate_sync_service=lambda: None,
        map_immich_error=lambda error: error,  # type: ignore[return-value]
    )
    old_payload = {
        "include_exact": True,
        "include_similar": True,
        "similarity_threshold": 95,
        "maximum_perceptual_distance": 12,
        "validation_mode": "strict",
        "max_link_depth": 2,
        "max_candidates": 8,
        "maximum_matches": 5000,
    }

    with TestClient(app) as client:
        response = client.put("/api/settings/duplicates/discovery", json=old_payload)

    assert response.status_code == 200
    assert response.json()["comparison_max_displacement_percent"] == 17
    assert response.json()["comparison_max_rotation_degrees"] == 4
    assert database.session.record.comparison_max_displacement_percent == 17
    assert database.session.record.comparison_max_rotation_degrees == 4


@pytest.mark.asyncio
async def test_discovery_patch_preserves_newer_comparison_alignment_settings() -> None:
    database = _Database(
        _record(comparison_max_displacement_percent=17, comparison_max_rotation_degrees=4)
    )
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]

    saved = await repository.update_discovery_settings(
        DuplicateDiscoverySettingsPatch(
            similarity_threshold=91.5,
            maximum_perceptual_distance=15,
        )
    )

    assert saved.similarity_threshold == 91.5
    assert saved.maximum_perceptual_distance == 15
    assert saved.comparison_max_displacement_percent == 17
    assert saved.comparison_max_rotation_degrees == 4


@pytest.mark.asyncio
async def test_comparison_alignment_update_preserves_discovery_settings() -> None:
    database = _Database(
        _record(similarity_threshold=89.5, maximum_perceptual_distance=13)
    )
    repository = DuplicateDiscoverySettingsRepository(database)  # type: ignore[arg-type]

    saved = await repository.update_comparison_alignment(
        ComparisonAlignmentSettingsUpdate(
            comparison_max_displacement_percent=16,
            comparison_max_rotation_degrees=3,
        )
    )

    assert saved.comparison_max_displacement_percent == 16
    assert saved.comparison_max_rotation_degrees == 3
    assert database.session.record.similarity_threshold == 89.5
    assert database.session.record.maximum_perceptual_distance == 13

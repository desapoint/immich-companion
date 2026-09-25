from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from companion.asset_service import AssetSyncService
from companion.config import Settings
from companion.sync_schema import SyncRunStatus
from companion.sync_settings import DefaultSyncRuntimeSettingsRepository, SyncRuntimeSettings


def full_run() -> SyncRunStatus:
    now = datetime.now(UTC)
    return SyncRunStatus(
        id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        mode="full",
        status="running",
        phase="assets",
        generation=1,
        window_start=None,
        window_end=now,
        cursor=None,
        attempts=1,
        error=None,
        created_at=now,
        started_at=now,
        heartbeat_at=now,
        completed_at=None,
    )


class RuntimeSettings:
    async def get(self) -> SyncRuntimeSettings:
        return SyncRuntimeSettings(
            full_batch_size=50,
            full_min_batch_delay_seconds=0.2,
            tag_association_concurrency=4,
        )


@pytest.mark.asyncio
async def test_full_sync_pacing_waits_only_for_remaining_minimum_duration(monkeypatch) -> None:
    service = AssetSyncService(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        Settings(sync_full_batch_size=50, sync_full_min_batch_delay_seconds=0.2),
        runtime_sync_settings=RuntimeSettings(),
    )
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("companion.synchronization.service.perf_counter", lambda: 3.0)
    monkeypatch.setattr("companion.synchronization.service.asyncio.sleep", sleep)

    await service._pace_full_batch(full_run(), 1.0)
    await service._pace_full_batch(full_run(), 2.9)

    assert sleeps == [pytest.approx(0.1)]


@pytest.mark.asyncio
async def test_media_page_pacing_uses_only_configured_delay(monkeypatch) -> None:
    service = AssetSyncService(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        Settings(sync_full_batch_size=50, sync_full_min_batch_delay_seconds=0.2),
        runtime_sync_settings=RuntimeSettings(),
    )
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("companion.synchronization.service.asyncio.sleep", sleep)

    await service._pace_full_page(full_run())
    await service._pace_full_page(full_run().model_copy(update={"mode": "incremental"}))

    assert sleeps == [0.2]


@pytest.mark.asyncio
async def test_environment_values_seed_runtime_settings_and_incremental_batch_size() -> None:
    settings = Settings(
        sync_batch_size=250,
        sync_full_batch_size=50,
        sync_full_min_batch_delay_seconds=0.2,
        sync_tag_association_concurrency=4,
    )
    runtime = await DefaultSyncRuntimeSettingsRepository(settings).get()

    assert runtime == SyncRuntimeSettings(
        full_batch_size=50,
        full_min_batch_delay_seconds=0.2,
        tag_association_concurrency=4,
        metadata_request_concurrency=4,
        page_prefetch=1,
        api_page_size=1000,
        incremental_overlap_seconds=300,
        incremental_strategy="automatic",
        adaptive_throttling=True,
    )
    assert AssetSyncService._full_batch_size(full_run(), settings) == 50
    incremental = full_run().model_copy(update={"mode": "incremental"})
    assert AssetSyncService._full_batch_size(incremental, settings) == 250
    assert settings.sync_media_page_size == 1000
    assert settings.sync_relationship_page_size == 1000
    assert settings.sync_tag_association_concurrency == 4


def test_runtime_settings_accept_expanded_safe_upper_bounds() -> None:
    value = SyncRuntimeSettings(
        full_batch_size=2_000,
        full_min_batch_delay_seconds=300,
        tag_association_concurrency=128,
        metadata_request_concurrency=64,
        page_prefetch=16,
        api_page_size=1_000,
        incremental_overlap_seconds=7 * 86_400,
    )

    assert value.full_batch_size == 2_000
    assert value.incremental_overlap_seconds == 604_800


def test_runtime_settings_still_reject_values_above_expanded_bounds() -> None:
    with pytest.raises(ValidationError):
        SyncRuntimeSettings(
            full_batch_size=2_001,
            full_min_batch_delay_seconds=300,
            tag_association_concurrency=128,
            metadata_request_concurrency=64,
            page_prefetch=16,
            api_page_size=1_000,
            incremental_overlap_seconds=7 * 86_400,
        )

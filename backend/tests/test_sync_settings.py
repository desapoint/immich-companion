from datetime import UTC, datetime
from uuid import UUID

import pytest

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
        return SyncRuntimeSettings(full_batch_size=50, full_min_batch_delay_seconds=0.2)


@pytest.mark.asyncio
async def test_full_sync_pacing_uses_the_longer_of_minimum_delay_and_work_time(monkeypatch) -> None:
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

    monkeypatch.setattr("companion.asset_service.perf_counter", lambda: 3.0)
    monkeypatch.setattr("companion.asset_service.asyncio.sleep", sleep)

    await service._pace_full_batch(full_run(), 1.0)
    await service._pace_full_batch(full_run(), 2.9)

    assert sleeps == [2.0, 0.2]


@pytest.mark.asyncio
async def test_environment_values_seed_runtime_settings_and_incremental_batch_size() -> None:
    settings = Settings(
        sync_batch_size=250,
        sync_full_batch_size=50,
        sync_full_min_batch_delay_seconds=0.2,
    )
    runtime = await DefaultSyncRuntimeSettingsRepository(settings).get()

    assert runtime == SyncRuntimeSettings(full_batch_size=50, full_min_batch_delay_seconds=0.2)
    assert AssetSyncService._full_batch_size(full_run(), settings) == 50
    incremental = full_run().model_copy(update={"mode": "incremental"})
    assert AssetSyncService._full_batch_size(incremental, settings) == 250
    assert settings.sync_relationship_page_size == 1000

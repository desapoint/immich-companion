"""V2 sync-step contracts stay isolated and frontend-progress compatible."""

import pytest

from companion.asset_service import AssetSyncService
from companion.v2.legacy_asset_service import AssetSyncService as LegacyAssetSyncService
from companion.v2.sync_steps import (
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
    SyncStepProgress,
    task_checkpoint_callback,
)


class FakeTaskContext:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def checkpoint_sync_step(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_v2_step_config_validates_shared_operational_limits() -> None:
    with pytest.raises(ValueError):
        SyncStepConfig(concurrency=0)
    with pytest.raises(ValueError):
        SyncStepConfig(page_size=0)
    with pytest.raises(ValueError):
        SyncStepConfig(batch_size=0)
    with pytest.raises(ValueError):
        SyncStepConfig(min_batch_delay_seconds=-0.1)


def test_manual_execution_can_bypass_conditionals() -> None:
    config = SyncStepConfig(conditionals=SyncStepConditionals(enabled=False))
    context = SyncStepContext(
        mode="full",
        generation=0,
        config=config,
        manual=True,
        respect_conditionals=False,
    )
    assert context.manual is True
    assert context.respect_conditionals is False


@pytest.mark.asyncio
async def test_task_checkpoint_bridge_preserves_frontend_progress_contract() -> None:
    task = FakeTaskContext()
    callback = task_checkpoint_callback(task, "assets")  # type: ignore[arg-type]
    progress = SyncStepProgress(
        phase="assets",
        completed=25,
        total=100,
        detail="Media 25/100",
    )

    await callback("assets:2:1", {"assets_seen": 25}, progress)

    assert task.calls == [
        {
            "step": "assets",
            "cursor": "assets:2:1",
            "counters": {"assets_seen": 25},
            "completed": 25,
            "total": 100,
            "detail": "Media 25/100",
        }
    ]


def test_progress_percent_is_derived_from_committed_work() -> None:
    progress = SyncStepProgress(phase="catalogs", completed=3, total=12)
    assert progress.percent == 25.0
    assert progress.as_dict()["step"] == "catalogs"


def test_live_v2_asset_sync_overrides_only_extracted_catalog_stage() -> None:
    assert issubclass(AssetSyncService, LegacyAssetSyncService)
    assert AssetSyncService._sync_catalogs is not LegacyAssetSyncService._sync_catalogs

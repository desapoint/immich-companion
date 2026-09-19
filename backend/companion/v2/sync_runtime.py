"""V2 registration/execution glue for independently runnable sync steps."""

from __future__ import annotations

from typing import Protocol

from companion.asset_repository import AssetRepository
from companion.immich import ImmichApiClient
from companion.sync_schema import SyncMode
from companion.v2.sync_steps import (
    CatalogSyncStep,
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
    task_checkpoint_callback,
)
from companion.v2.task_coordinator import TaskContext, TaskCoordinator
from companion.v2.task_schema import TaskResult


class RuntimeSyncSettings(Protocol):
    full_batch_size: int
    full_min_batch_delay_seconds: float
    tag_association_concurrency: int


class RuntimeSyncSettingsRepository(Protocol):
    async def get(self) -> RuntimeSyncSettings: ...


class CatalogSyncTaskHandler:
    """Run the first V2 sync step manually through the durable task lifecycle."""

    task_type = "v2_sync_step_catalogs"
    lane_key = "v2_sync"
    max_concurrency = 1

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        runtime_settings: RuntimeSyncSettingsRepository,
    ) -> None:
        self._immich = immich
        self._step = CatalogSyncStep(assets)
        self._runtime_settings = runtime_settings

    async def execute(self, task: TaskContext, payload: dict[str, object]) -> TaskResult:
        runtime = await self._runtime_settings.get()
        mode: SyncMode = "full" if payload.get("mode") == "full" else "incremental"
        respect_conditionals = bool(payload.get("respect_conditionals", True))
        batch_size = int(payload.get("batch_size") or runtime.full_batch_size)
        concurrency = int(payload.get("concurrency") or 1)
        min_delay = float(
            payload.get("min_batch_delay_seconds")
            if payload.get("min_batch_delay_seconds") is not None
            else runtime.full_min_batch_delay_seconds
        )
        conditionals = SyncStepConditionals(
            enabled=bool(payload.get("enabled", True)),
            run_on_full=bool(payload.get("run_on_full", True)),
            run_on_incremental=bool(payload.get("run_on_incremental", True)),
        )
        checkpoint = task.task.checkpoint
        counters = dict(task.task.counters)
        context = SyncStepContext(
            mode=mode,
            # A manual catalog refresh is non-finalizing. Generation 0 matches the
            # existing relation-repair convention and cannot make a partial step
            # authoritative by itself.
            generation=int(payload.get("generation") or 0),
            config=SyncStepConfig(
                batch_size=batch_size,
                concurrency=concurrency,
                min_batch_delay_seconds=min_delay,
                conditionals=conditionals,
            ),
            counters=counters,
            cursor=(str(checkpoint["cursor"]) if checkpoint.get("cursor") else None),
            manual=True,
            respect_conditionals=respect_conditionals,
            checkpoint_callback=task_checkpoint_callback(task, self._step.name),
        )
        data = await self._step.load(self._immich)
        result = await self._step.run(context, data)
        return TaskResult(
            summary={
                "step": result.name,
                "skipped": result.skipped,
                "processed": result.completed,
                "total": result.total,
            },
            counters=result.counters,
        )


def register_sync_steps(
    coordinator: TaskCoordinator,
    immich: ImmichApiClient,
    assets: AssetRepository,
    runtime_settings: RuntimeSyncSettingsRepository,
) -> None:
    """Register V2 sync-step handlers without changing V1 coordinator modules."""

    coordinator.register_handler(
        CatalogSyncTaskHandler(immich, assets, runtime_settings)
    )

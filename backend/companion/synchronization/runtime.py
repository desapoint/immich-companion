"""Durable generic execution and API glue for first-class synchronization steps."""

from __future__ import annotations

from typing import Protocol, Self
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from companion.sync_settings import SyncRuntimeSettings
from companion.synchronization.evidence import SyncEvidence
from companion.synchronization.planner import SyncStepConfigOverride
from companion.synchronization.registry import SyncStepRegistry
from companion.synchronization.scopes import (
    FinalizationScope,
    SyncScope,
    SyncStepName,
    ValidationScope,
)
from companion.synchronization.steps import (
    SyncStepConfig,
    SyncStepContext,
    SyncStepResult,
    task_checkpoint_callback,
)
from companion.tasks.contracts import TaskResult
from companion.tasks.coordinator import TaskContext, TaskCoordinator


class RuntimeSyncSettingsRepository(Protocol):
    async def get(self) -> SyncRuntimeSettings: ...


class ManualGenerationAllocator(Protocol):
    async def allocate_manual_generation(self) -> int: ...


class RelationCountRefresher(Protocol):
    async def refresh_relation_counts(self) -> None: ...


class ManualSyncStepRequest(BaseModel):
    """Public request for one independently durable synchronization step."""

    scope: SyncScope
    config: SyncStepConfigOverride | None = None

    @model_validator(mode="after")
    def validate_manual_finalization(self) -> Self:
        if isinstance(self.scope, FinalizationScope):
            if self.scope.validation_task_id is None:
                raise ValueError(
                    "Manual finalization requires a validation_task_id"
                )
            if not self.scope.confirm_destructive:
                raise ValueError(
                    "Manual finalization requires confirm_destructive=true"
                )
        return self


class SyncStepTaskStart(BaseModel):
    task_id: UUID


class SyncStepTaskPayload(BaseModel):
    """Serializable payload persisted by the generic durable task coordinator."""

    step: SyncStepName
    scope: SyncScope
    config: SyncStepConfigOverride | None = None
    generation: int | None = Field(default=None, ge=0)
    respect_conditionals: bool = False

    @model_validator(mode="after")
    def validate_scope_matches_step(self) -> Self:
        if self.scope.kind != self.step:
            raise ValueError(
                f"Sync step {self.step!r} cannot execute {self.scope.kind!r} scope"
            )
        if isinstance(self.scope, (ValidationScope, FinalizationScope)):
            if self.generation is not None and self.generation != self.scope.generation:
                raise ValueError(
                    "Task generation must match validation/finalization scope generation"
                )
        return self


class SyncStepPostProcessor:
    """Run only domain-local maintenance after an independent manual step."""

    def __init__(self, assets: RelationCountRefresher) -> None:
        self._assets = assets

    async def after_step(self, result: SyncStepResult) -> None:
        if result.name == "relationships" and not result.skipped:
            await self._assets.refresh_relation_counts()


class SyncStepTaskHandler:
    """Run any registered synchronization step through the durable sync write lane."""

    task_type = "sync_step"
    lane_key = "asset_sync"
    max_concurrency = 1

    def __init__(
        self,
        registry: SyncStepRegistry,
        generations: ManualGenerationAllocator,
        runtime_settings: RuntimeSyncSettingsRepository,
        coordinator: TaskCoordinator,
        post_processor: SyncStepPostProcessor,
    ) -> None:
        self._registry = registry
        self._generations = generations
        self._runtime_settings = runtime_settings
        self._coordinator = coordinator
        self._post_processor = post_processor

    async def execute(
        self,
        task: TaskContext,
        payload: dict[str, object],
    ) -> TaskResult:
        parsed = SyncStepTaskPayload.model_validate(payload)
        generation = await self._resolve_generation(task, parsed)
        runtime = await self._runtime_settings.get()
        config = self._config_for(parsed.step, runtime, parsed.config)
        evidence = await self._input_evidence(
            task.task.id,
            parsed,
            generation,
        )
        step = self._registry.get(parsed.step)
        checkpoint = task.task.checkpoint
        context = SyncStepContext(
            mode="full",
            generation=generation,
            config=config,
            counters=dict(task.task.counters),
            cursor=(
                str(checkpoint["cursor"])
                if checkpoint.get("cursor") is not None
                else None
            ),
            manual=True,
            respect_conditionals=parsed.respect_conditionals,
            evidence=evidence,
            checkpoint_callback=task_checkpoint_callback(task, parsed.step),
        )
        result = await step.run(context, parsed.scope)
        await self._post_processor.after_step(result)
        return TaskResult(
            summary={
                "step": result.name,
                "generation": generation,
                "skipped": result.skipped,
                "processed": result.completed,
                "total": result.total,
                "evidence": [
                    item.model_dump(mode="json") for item in result.evidence
                ],
                "outputs": result.outputs,
            },
            counters=result.counters,
        )

    async def _resolve_generation(
        self,
        task: TaskContext,
        parsed: SyncStepTaskPayload,
    ) -> int:
        if isinstance(parsed.scope, (ValidationScope, FinalizationScope)):
            generation = parsed.scope.generation
        elif parsed.generation is not None:
            generation = parsed.generation
        else:
            generation = await self._generations.allocate_manual_generation()

        if parsed.generation != generation:
            updated = parsed.model_copy(update={"generation": generation})
            await task.update_payload(updated.model_dump(mode="json"))
        return generation

    async def _input_evidence(
        self,
        task_id: UUID,
        parsed: SyncStepTaskPayload,
        generation: int,
    ) -> list[SyncEvidence]:
        if isinstance(parsed.scope, FinalizationScope):
            return await self._validation_evidence(parsed.scope, generation)
        if isinstance(parsed.scope, ValidationScope):
            return await self._generation_evidence(task_id, generation)
        return []

    async def _generation_evidence(
        self,
        current_task_id: UUID,
        generation: int,
    ) -> list[SyncEvidence]:
        tasks = await self._coordinator.list_tasks(
            task_type=self.task_type,
            limit=1000,
        )
        evidence: list[SyncEvidence] = []
        for candidate in tasks:
            if (
                candidate.id == current_task_id
                or candidate.status != "completed"
                or candidate.result is None
            ):
                continue
            summary = candidate.result.summary
            if int(summary.get("generation", -1)) != generation:
                continue
            if summary.get("step") in {"validation", "finalization"}:
                continue
            raw_evidence = summary.get("evidence", [])
            if not isinstance(raw_evidence, list):
                continue
            evidence.extend(
                SyncEvidence.model_validate(item)
                for item in raw_evidence
                if isinstance(item, dict)
            )
        return evidence

    async def _validation_evidence(
        self,
        scope: FinalizationScope,
        generation: int,
    ) -> list[SyncEvidence]:
        assert scope.validation_task_id is not None
        validation = await self._coordinator.get_status(scope.validation_task_id)
        if validation is None:
            raise ValueError("The referenced validation task was not found")
        if (
            validation.task_type != self.task_type
            or validation.status != "completed"
            or validation.result is None
            or validation.result.summary.get("step") != "validation"
        ):
            raise ValueError(
                "Manual finalization requires a completed sync-step validation task"
            )
        if int(validation.result.summary.get("generation", -1)) != generation:
            raise ValueError(
                "Validation evidence generation does not match finalization generation"
            )
        raw_evidence = validation.result.summary.get("evidence", [])
        if not isinstance(raw_evidence, list):
            return []
        return [
            SyncEvidence.model_validate(item)
            for item in raw_evidence
            if isinstance(item, dict)
        ]

    @staticmethod
    def _config_for(
        step: SyncStepName,
        runtime: SyncRuntimeSettings,
        override: SyncStepConfigOverride | None,
    ) -> SyncStepConfig:
        values: dict[str, object] = {
            "batch_size": runtime.full_batch_size,
            "page_size": None,
            "concurrency": 1,
            "page_prefetch": None,
            "metadata_concurrency": None,
            "min_batch_delay_seconds": runtime.full_min_batch_delay_seconds,
        }
        if step == "assets":
            values.update(
                {
                    "page_size": runtime.api_page_size,
                    "concurrency": runtime.metadata_request_concurrency,
                    "page_prefetch": runtime.page_prefetch,
                }
            )
        elif step == "relationships":
            values.update(
                {
                    "page_size": runtime.api_page_size,
                    "concurrency": runtime.tag_association_concurrency,
                    "page_prefetch": runtime.page_prefetch,
                    "metadata_concurrency": runtime.metadata_request_concurrency,
                }
            )
        elif step == "events":
            values.update(
                {
                    "batch_size": None,
                    "min_batch_delay_seconds": 0.0,
                }
            )

        if override is not None:
            for name, value in override.model_dump().items():
                if value is not None:
                    values[name] = value
        return SyncStepConfig(**values)  # type: ignore[arg-type]


class SyncStepSubmissionService:
    """Submit validated manual-step requests to the generic coordinator."""

    def __init__(self, coordinator: TaskCoordinator) -> None:
        self._coordinator = coordinator

    async def start(
        self,
        step: SyncStepName,
        request: ManualSyncStepRequest,
    ) -> SyncStepTaskStart:
        if request.scope.kind != step:
            raise ValueError(
                f"Path step {step!r} does not match scope {request.scope.kind!r}"
            )
        payload = SyncStepTaskPayload(
            step=step,
            scope=request.scope,
            config=request.config,
            respect_conditionals=False,
        )
        task = await self._coordinator.submit(
            SyncStepTaskHandler.task_type,
            payload.model_dump(mode="json"),
            priority=50,
        )
        await self._coordinator.start()
        return SyncStepTaskStart(task_id=task.id)


def register_sync_steps(
    coordinator: TaskCoordinator,
    *,
    registry: SyncStepRegistry,
    generations: ManualGenerationAllocator,
    runtime_settings: RuntimeSyncSettingsRepository,
    assets: RelationCountRefresher,
) -> SyncStepSubmissionService:
    """Register generic manual sync-step execution using the production registry."""

    coordinator.register_handler(
        SyncStepTaskHandler(
            registry,
            generations,
            runtime_settings,
            coordinator,
            SyncStepPostProcessor(assets),
        )
    )
    return SyncStepSubmissionService(coordinator)


def register_sync_step_routes(
    app: FastAPI,
    submission: SyncStepSubmissionService | None,
) -> None:
    """Expose the generic typed manual-step submission endpoint."""

    @app.post(
        "/api/sync/steps/{step}/start",
        response_model=SyncStepTaskStart,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_sync_step(
        step: SyncStepName,
        request: ManualSyncStepRequest,
    ) -> SyncStepTaskStart:
        if submission is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        try:
            return await submission.start(step, request)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error


__all__ = [
    "ManualSyncStepRequest",
    "SyncStepPostProcessor",
    "SyncStepSubmissionService",
    "SyncStepTaskHandler",
    "SyncStepTaskPayload",
    "SyncStepTaskStart",
    "register_sync_step_routes",
    "register_sync_steps",
]

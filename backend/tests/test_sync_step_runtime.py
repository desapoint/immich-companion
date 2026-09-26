"""Generic durable manual synchronization-step runtime behavior."""

from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from companion.action_schema import AssetSelectionRequest
from companion.sync_settings import SyncRuntimeSettings
from companion.synchronization.evidence import SyncAuthority, SyncEvidence
from companion.synchronization.planner import SyncStepConfigOverride
from companion.synchronization.registry import SyncStepRegistry
from companion.synchronization.runtime import (
    ManualSyncStepRequest,
    SyncStepPostProcessor,
    SyncStepSubmissionService,
    SyncStepTaskHandler,
    SyncStepTaskPayload,
)
from companion.synchronization.scopes import (
    AssetScope,
    FinalizationScope,
    RelationshipScope,
    ValidationScope,
)
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    RequestSelection,
)
from companion.synchronization.steps import (
    SyncStep,
    SyncStepContext,
    SyncStepResult,
)

TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
VALIDATION_TASK_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime(2026, 9, 26, 18, 0, tzinfo=UTC)


class RecordingStep(SyncStep[AssetScope]):
    name = "assets"
    phase = "assets"

    def __init__(self) -> None:
        self.contexts: list[SyncStepContext] = []
        self.scopes: list[AssetScope] = []

    async def execute(self, context, scope):
        self.contexts.append(context)
        self.scopes.append(scope)
        context.counters["assets_seen"] = 1
        return 1, 1

    async def run(self, context, scope):
        await self.execute(context, scope)
        return SyncStepResult(
            name="assets",
            phase="assets",
            skipped=False,
            completed=1,
            total=1,
            counters=dict(context.counters),
            evidence=[
                SyncEvidence(
                    domain="assets",
                    authority=SyncAuthority.SELECTED,
                    selection=scope.selection,
                    generation=context.generation,
                )
            ],
        )


class RecordingValidationStep(SyncStep[ValidationScope]):
    name = "validation"
    phase = "finalizing"

    def __init__(self) -> None:
        self.contexts: list[SyncStepContext] = []

    async def execute(self, context, scope):
        self.contexts.append(context)
        return 1, 1

    async def run(self, context, scope):
        await self.execute(context, scope)
        return SyncStepResult(
            name="validation",
            phase="finalizing",
            skipped=False,
            completed=1,
            total=1,
            counters=dict(context.counters),
            evidence=list(context.evidence),
        )


class RecordingFinalizationStep(SyncStep[FinalizationScope]):
    name = "finalization"
    phase = "finalizing"

    def __init__(self) -> None:
        self.contexts: list[SyncStepContext] = []

    async def execute(self, context, scope):
        self.contexts.append(context)
        return 1, 1

    async def run(self, context, scope):
        await self.execute(context, scope)
        return SyncStepResult(
            name="finalization",
            phase="finalizing",
            skipped=False,
            completed=1,
            total=1,
            counters=dict(context.counters),
            evidence=list(context.evidence),
        )


class FakeGenerationAllocator:
    def __init__(self, generation: int = 88) -> None:
        self.generation = generation
        self.calls = 0

    async def allocate_manual_generation(self) -> int:
        self.calls += 1
        return self.generation


class FakeRuntimeSettings:
    async def get(self) -> SyncRuntimeSettings:
        return SyncRuntimeSettings(
            full_batch_size=25,
            full_min_batch_delay_seconds=0.0,
            tag_association_concurrency=4,
            metadata_request_concurrency=3,
            page_prefetch=2,
            api_page_size=500,
            incremental_overlap_seconds=300,
            incremental_strategy="automatic",
            adaptive_throttling=True,
        )


class FakePostProcessor:
    def __init__(self) -> None:
        self.results = []

    async def after_step(self, result) -> None:
        self.results.append(result)


class FakeTaskContext:
    def __init__(self, *, payload: dict[str, object]) -> None:
        self.task = SimpleNamespace(
            id=TASK_ID,
            payload=payload,
            checkpoint={},
            counters={},
        )
        self.updated_payloads: list[dict[str, object]] = []
        self.checkpoints: list[dict[str, object]] = []

    async def update_payload(self, payload):
        self.updated_payloads.append(dict(payload))
        self.task.payload = dict(payload)

    async def checkpoint_sync_step(self, **kwargs):
        self.checkpoints.append(dict(kwargs))


class FakeCoordinator:
    def __init__(self) -> None:
        self.tasks = []
        self.by_id = {}
        self.submissions = []
        self.started = 0

    async def list_tasks(self, **_kwargs):
        return list(self.tasks)

    async def get_status(self, task_id):
        return self.by_id.get(task_id)

    async def submit(self, task_type, payload, **kwargs):
        self.submissions.append((task_type, payload, kwargs))
        return SimpleNamespace(id=TASK_ID)

    async def start(self):
        self.started += 1


@pytest.mark.asyncio
async def test_manual_write_step_allocates_isolated_generation_and_persists_it() -> None:
    step = RecordingStep()
    registry = SyncStepRegistry([step])  # type: ignore[list-item]
    generations = FakeGenerationAllocator()
    coordinator = FakeCoordinator()
    post = FakePostProcessor()
    payload = SyncStepTaskPayload(
        step="assets",
        scope=AssetScope(
            selection=ExplicitIdsSelection(ids=[ASSET_ID]),
        ),
    ).model_dump(mode="json")
    task = FakeTaskContext(payload=payload)
    handler = SyncStepTaskHandler(
        registry,
        generations,
        FakeRuntimeSettings(),
        coordinator,  # type: ignore[arg-type]
        post,  # type: ignore[arg-type]
    )

    result = await handler.execute(task, payload)  # type: ignore[arg-type]

    assert generations.calls == 1
    assert task.updated_payloads[-1]["generation"] == 88
    assert step.contexts[0].generation == 88
    assert step.contexts[0].manual is True
    assert step.contexts[0].respect_conditionals is False
    assert step.contexts[0].config.batch_size == 25
    assert step.contexts[0].config.page_size == 500
    assert step.contexts[0].config.concurrency == 3
    assert step.contexts[0].config.page_prefetch == 2
    assert result.summary["generation"] == 88
    assert result.summary["evidence"][0]["authority"] == "selected"
    assert len(post.results) == 1
    assert post.results[0].name == "assets"


@pytest.mark.asyncio
async def test_retry_reuses_persisted_manual_generation() -> None:
    step = RecordingStep()
    generations = FakeGenerationAllocator()
    payload = SyncStepTaskPayload(
        step="assets",
        scope=AssetScope(selection=ExplicitIdsSelection(ids=[ASSET_ID])),
        generation=91,
    ).model_dump(mode="json")
    task = FakeTaskContext(payload=payload)
    handler = SyncStepTaskHandler(
        SyncStepRegistry([step]),  # type: ignore[list-item]
        generations,
        FakeRuntimeSettings(),
        FakeCoordinator(),  # type: ignore[arg-type]
        FakePostProcessor(),  # type: ignore[arg-type]
    )

    await handler.execute(task, payload)  # type: ignore[arg-type]

    assert generations.calls == 0
    assert task.updated_payloads == []
    assert step.contexts[0].generation == 91


@pytest.mark.asyncio
async def test_validation_loads_completed_step_evidence_for_target_generation() -> None:
    evidence = SyncEvidence(
        domain="assets",
        authority=SyncAuthority.SELECTED,
        selection=ExplicitIdsSelection(ids=[ASSET_ID]),
        generation=54,
    )
    previous = SimpleNamespace(
        id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        status="completed",
        result=SimpleNamespace(
            summary={
                "step": "assets",
                "generation": 54,
                "evidence": [evidence.model_dump(mode="json")],
            }
        ),
    )
    coordinator = FakeCoordinator()
    coordinator.tasks = [previous]
    step = RecordingValidationStep()
    payload = SyncStepTaskPayload(
        step="validation",
        scope=ValidationScope(
            generation=54,
            expected_domains={"assets"},
        ),
    ).model_dump(mode="json")
    task = FakeTaskContext(payload=payload)
    handler = SyncStepTaskHandler(
        SyncStepRegistry([step]),  # type: ignore[list-item]
        FakeGenerationAllocator(),
        FakeRuntimeSettings(),
        coordinator,  # type: ignore[arg-type]
        FakePostProcessor(),  # type: ignore[arg-type]
    )

    result = await handler.execute(task, payload)  # type: ignore[arg-type]

    assert step.contexts[0].evidence == [evidence]
    assert result.summary["generation"] == 54
    assert result.summary["evidence"] == [evidence.model_dump(mode="json")]


@pytest.mark.asyncio
async def test_finalization_loads_only_completed_validation_evidence_same_generation() -> None:
    evidence = SyncEvidence(
        domain="assets",
        authority=SyncAuthority.SELECTED,
        selection=ExplicitIdsSelection(ids=[ASSET_ID]),
        generation=55,
    )
    validation = SimpleNamespace(
        task_type="sync_step",
        status="completed",
        result=SimpleNamespace(
            summary={
                "step": "validation",
                "generation": 55,
                "evidence": [evidence.model_dump(mode="json")],
            }
        ),
    )
    coordinator = FakeCoordinator()
    coordinator.by_id[VALIDATION_TASK_ID] = validation
    step = RecordingFinalizationStep()
    payload = SyncStepTaskPayload(
        step="finalization",
        scope=FinalizationScope(
            generation=55,
            validation_task_id=VALIDATION_TASK_ID,
            confirm_destructive=True,
        ),
    ).model_dump(mode="json")
    task = FakeTaskContext(payload=payload)
    handler = SyncStepTaskHandler(
        SyncStepRegistry([step]),  # type: ignore[list-item]
        FakeGenerationAllocator(),
        FakeRuntimeSettings(),
        coordinator,  # type: ignore[arg-type]
        FakePostProcessor(),  # type: ignore[arg-type]
    )

    result = await handler.execute(task, payload)  # type: ignore[arg-type]

    assert step.contexts[0].generation == 55
    assert step.contexts[0].evidence == [evidence]
    assert result.summary["evidence"] == [evidence.model_dump(mode="json")]


def test_public_manual_finalization_requires_reference_and_confirmation() -> None:
    with pytest.raises(ValidationError, match="validation_task_id"):
        ManualSyncStepRequest(
            scope=FinalizationScope(
                generation=9,
                confirm_destructive=True,
            )
        )

    with pytest.raises(ValidationError, match="confirm_destructive"):
        ManualSyncStepRequest(
            scope=FinalizationScope(
                generation=9,
                validation_task_id=VALIDATION_TASK_ID,
            )
        )


@pytest.mark.asyncio
async def test_submission_uses_generic_task_type_and_shared_asset_sync_lane_contract() -> None:
    coordinator = FakeCoordinator()
    service = SyncStepSubmissionService(coordinator)  # type: ignore[arg-type]
    request = ManualSyncStepRequest(
        scope=AssetScope(
            selection=RequestSelection(
                request=AssetSelectionRequest(
                    mode="explicit",
                    ids=[ASSET_ID],
                )
            )
        ),
        config=SyncStepConfigOverride(batch_size=25),
    )

    started = await service.start("assets", request)

    assert started.task_id == TASK_ID
    assert coordinator.submissions[0][0] == "sync_step"
    assert coordinator.submissions[0][1]["step"] == "assets"
    assert coordinator.started == 1
    assert SyncStepTaskHandler.lane_key == "asset_sync"
    assert SyncStepTaskHandler.max_concurrency == 1


@pytest.mark.asyncio
async def test_submission_rejects_path_scope_mismatch_before_queueing() -> None:
    coordinator = FakeCoordinator()
    service = SyncStepSubmissionService(coordinator)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="does not match"):
        await service.start(
            "relationships",
            ManualSyncStepRequest(
                scope=AssetScope(selection=AllSelection()),
            ),
        )

    assert coordinator.submissions == []


@pytest.mark.asyncio
async def test_relationship_post_processor_refreshes_relation_counts() -> None:
    class Assets:
        def __init__(self) -> None:
            self.calls = 0

        async def refresh_relation_counts(self) -> None:
            self.calls += 1

    assets = Assets()
    processor = SyncStepPostProcessor(assets)
    result = SyncStepResult(
        name="relationships",
        phase="relationships",
        skipped=False,
        completed=1,
        total=None,
        counters={},
    )

    await processor.after_step(result)

    assert assets.calls == 1


def test_generic_payload_accepts_typed_persistable_relationship_scope() -> None:
    payload = SyncStepTaskPayload(
        step="relationships",
        scope=RelationshipScope(
            kinds={"albums"},
            strategy="by_asset",
            assets=ExplicitIdsSelection(ids=[ASSET_ID]),
        ),
    )
    restored = SyncStepTaskPayload.model_validate_json(payload.model_dump_json())
    assert restored == payload

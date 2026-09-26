"""Repair task compatibility adapters delegate to first-class sync steps."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.sync_settings import SyncRuntimeSettings
from companion.synchronization.registry import SyncStepRegistry
from companion.synchronization.scopes import AssetScope, CatalogScope, RelationshipScope, StackScope
from companion.synchronization.selections import AffectedAssetsSelection, ExplicitIdsSelection
from companion.synchronization.service import (
    AssetRelationRepairTaskHandler,
    AssetRepairTaskHandler,
    AssetSyncService,
)
from companion.synchronization.steps import SyncStepProgress, SyncStepResult

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ALBUM_ONE = UUID("33333333-3333-4333-8333-333333333333")
TAG_ONE = UUID("44444444-4444-4444-8444-444444444444")
TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime(2026, 9, 26, 18, 0, tzinfo=UTC)


class RuntimeSettings:
    async def get(self) -> SyncRuntimeSettings:
        return SyncRuntimeSettings(
            full_batch_size=25,
            full_min_batch_delay_seconds=0,
            tag_association_concurrency=4,
            metadata_request_concurrency=3,
            page_prefetch=2,
            api_page_size=1000,
            incremental_overlap_seconds=300,
            incremental_strategy="automatic",
            adaptive_throttling=True,
        )


class RecordingStep:
    def __init__(self, name: str, phase: str) -> None:
        self.name = name
        self.phase = phase
        self.calls = []

    async def run(self, context, scope):
        self.calls.append((context, scope))
        completed = 1
        if self.name == "assets":
            context.counters["assets_seen"] = context.counters.get("assets_seen", 0) + 1
        elif self.name == "catalogs":
            completed = int(scope.albums is not None) + int(scope.tags is not None)
        elif self.name == "relationships":
            context.counters["album_memberships"] = (
                context.counters.get("album_memberships", 0) + 1
            )
            context.counters["tag_memberships"] = (
                context.counters.get("tag_memberships", 0) + 1
            )
        return SyncStepResult(
            name=self.name,  # type: ignore[arg-type]
            phase=self.phase,
            skipped=False,
            completed=completed,
            total=1,
            counters=dict(context.counters),
        )


async def checkpoint(
    _cursor: str | None,
    _counters: dict[str, int],
    _progress: SyncStepProgress,
) -> None:
    return None


def service_with_steps(*steps: RecordingStep) -> AssetSyncService:
    service = object.__new__(AssetSyncService)
    service._steps = SyncStepRegistry(steps)  # type: ignore[arg-type]
    service._runtime_sync_settings = RuntimeSettings()
    return service


@pytest.mark.asyncio
async def test_asset_repair_sequence_uses_asset_relationship_and_optional_stack_steps() -> None:
    assets = RecordingStep("assets", "assets")
    relationships = RecordingStep("relationships", "relationships")
    stacks = RecordingStep("stacks", "stacks")
    service = service_with_steps(assets, relationships, stacks)
    counters = {}

    results = await service._run_asset_repair_steps(
        [ASSET_ONE, ASSET_TWO],
        generation=71,
        include_stacks=True,
        counters=counters,
        checkpoint_callback=checkpoint,
    )

    assert [result.name for result in results] == [
        "assets",
        "relationships",
        "stacks",
    ]
    asset_context, asset_scope = assets.calls[0]
    assert asset_context.generation == 71
    assert asset_context.manual is True
    assert asset_context.respect_conditionals is False
    assert isinstance(asset_scope, AssetScope)
    assert asset_scope.selection == ExplicitIdsSelection(ids=[ASSET_ONE, ASSET_TWO])

    relationship_context, relationship_scope = relationships.calls[0]
    assert relationship_context.generation == 71
    assert isinstance(relationship_scope, RelationshipScope)
    assert relationship_scope.strategy == "by_asset"
    assert relationship_scope.assets == asset_scope.selection

    _stack_context, stack_scope = stacks.calls[0]
    assert isinstance(stack_scope, StackScope)
    assert stack_scope.selection == AffectedAssetsSelection(assets=asset_scope.selection)


@pytest.mark.asyncio
async def test_relation_repair_sequence_uses_selected_catalog_then_relation_step() -> None:
    catalogs = RecordingStep("catalogs", "catalogs")
    relationships = RecordingStep("relationships", "relationships")
    service = service_with_steps(catalogs, relationships)
    counters = {}

    results = await service._run_relation_repair_steps(
        [("album", ALBUM_ONE), ("tag", TAG_ONE)],
        generation=72,
        counters=counters,
        checkpoint_callback=checkpoint,
    )

    assert [result.name for result in results] == ["catalogs", "relationships"]
    catalog_context, catalog_scope = catalogs.calls[0]
    assert catalog_context.generation == 72
    assert isinstance(catalog_scope, CatalogScope)
    assert catalog_scope.albums == ExplicitIdsSelection(ids=[ALBUM_ONE])
    assert catalog_scope.tags == ExplicitIdsSelection(ids=[TAG_ONE])

    _relationship_context, relationship_scope = relationships.calls[0]
    assert relationship_scope.strategy == "by_relation"
    assert relationship_scope.albums == catalog_scope.albums
    assert relationship_scope.tags == catalog_scope.tags


class FakeTaskContext:
    def __init__(self, payload: dict[str, object]) -> None:
        self.task = SimpleNamespace(
            id=TASK_ID,
            payload=payload,
            checkpoint={},
            counters={},
            started_at=NOW,
            created_at=NOW,
        )
        self.payload_updates = []
        self.checkpoints = []

    async def update_payload(self, payload):
        self.payload_updates.append(dict(payload))
        self.task.payload = dict(payload)

    async def checkpoint(self, **kwargs):
        self.checkpoints.append(kwargs)


@pytest.mark.asyncio
async def test_asset_repair_handler_keeps_compatibility_task_type_on_shared_lane() -> None:
    class Service:
        _settings = SimpleNamespace()

        async def _repair_task_generation(self, context, payload):
            await context.update_payload({**payload, "generation": 81})
            return 81

        async def _runtime_settings(self):
            return SimpleNamespace(full_batch_size=25)

        async def _run_asset_repair_steps(
            self,
            asset_ids,
            *,
            generation,
            include_stacks,
            counters,
            checkpoint_callback,
        ):
            assert generation == 81
            assert include_stacks is True
            counters["assets_seen"] = counters.get("assets_seen", 0) + len(asset_ids)
            return []

        async def _pace_runtime_batch(self, _started):
            return None

    payload = {
        "asset_ids": [str(ASSET_ONE), str(ASSET_TWO)],
        "include_stacks": True,
    }
    context = FakeTaskContext(payload)
    handler = AssetRepairTaskHandler(Service())  # type: ignore[arg-type]

    result = await handler.execute(context, payload)  # type: ignore[arg-type]

    assert handler.task_type == "asset_repair"
    assert handler.lane_key == "asset_sync"
    assert handler.max_concurrency == 1
    assert result.summary == {"repaired": 2, "generation": 81}
    assert result.counters["processed"] == 2


@pytest.mark.asyncio
async def test_relation_repair_handler_preserves_relation_progress_contract() -> None:
    class Service:
        async def _repair_task_generation(self, context, payload):
            return 82

        async def _run_relation_repair_steps(
            self,
            relations,
            *,
            generation,
            counters,
            checkpoint_callback,
        ):
            assert generation == 82
            kind, _identifier = relations[0]
            key = "album_memberships" if kind == "album" else "tag_memberships"
            counters[key] = counters.get(key, 0) + 2
            return []

    payload = {
        "relations": [
            {"kind": "album", "id": str(ALBUM_ONE)},
            {"kind": "tag", "id": str(TAG_ONE)},
        ]
    }
    context = FakeTaskContext(payload)
    handler = AssetRelationRepairTaskHandler(Service())  # type: ignore[arg-type]

    result = await handler.execute(context, payload)  # type: ignore[arg-type]

    assert result.summary == {"repaired": 2, "generation": 82}
    assert result.counters["albums"] == 1
    assert result.counters["tags"] == 1
    assert result.counters["memberships"] == 4
    assert context.checkpoints[-1]["progress"]["phase"] == "relation_repair"

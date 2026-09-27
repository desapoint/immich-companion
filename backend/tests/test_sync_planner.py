"""Explicit full/incremental synchronization planning."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from companion.config import Settings
from companion.sync_schema import SyncCapabilities, SyncRunStatus
from companion.sync_settings import SyncRuntimeSettings
from companion.synchronization.planner import (
    PlannedSyncStep,
    SyncPlan,
    SyncPlanner,
)
from companion.synchronization.scopes import AssetScope, CatalogScope
from companion.synchronization.selections import (
    AllSelection,
    GenerationSelection,
    WindowSelection,
)

NOW = datetime(2026, 9, 25, 18, tzinfo=UTC)


class FakeImmich:
    def __init__(self, *, stream: bool) -> None:
        self.stream = stream
        self.capability_calls = 0

    async def sync_capabilities(self) -> SyncCapabilities:
        self.capability_calls += 1
        return SyncCapabilities(stream=self.stream, acknowledgements=self.stream)


def runtime(*, strategy: str = "automatic") -> SyncRuntimeSettings:
    return SyncRuntimeSettings(
        full_batch_size=40,
        full_min_batch_delay_seconds=0.25,
        tag_association_concurrency=6,
        metadata_request_concurrency=3,
        page_prefetch=2,
        api_page_size=750,
        incremental_overlap_seconds=300,
        incremental_strategy=strategy,  # type: ignore[arg-type]
        adaptive_throttling=True,
    )


def run(
    mode: str,
    *,
    attempts: int = 1,
    phase: str = "queued",
) -> SyncRunStatus:
    return SyncRunStatus(
        id="11111111-1111-4111-8111-111111111111",
        mode=mode,  # type: ignore[arg-type]
        status="running",
        phase=phase,  # type: ignore[arg-type]
        generation=73,
        window_start=NOW - timedelta(minutes=10) if mode == "incremental" else None,
        window_end=NOW,
        cursor=None,
        counters={},
        attempts=attempts,
        error=None,
        created_at=NOW,
        started_at=NOW,
        heartbeat_at=NOW,
        completed_at=None,
    )


def test_full_plan_is_explicit_serializable_and_globally_authoritative() -> None:
    immich = FakeImmich(stream=True)
    planner = SyncPlanner(immich, Settings(sync_full_batch_size=25))
    plan = planner.build_full(run("full"), runtime())

    assert [item.step for item in plan.steps] == [
        "catalogs",
        "assets",
        "stacks",
        "relationships",
        "validation",
        "finalization",
    ]
    assert immich.capability_calls == 0
    assert isinstance(plan.steps[0].scope, CatalogScope)
    assert isinstance(plan.steps[0].scope.albums, AllSelection)
    assert isinstance(plan.steps[1].scope, AssetScope)
    assert isinstance(plan.steps[1].scope.selection, AllSelection)
    assert plan.steps[3].scope.strategy == "by_relation"  # type: ignore[union-attr]
    assert plan.steps[4].scope.expected_domains == {  # type: ignore[union-attr]
        "albums",
        "tags",
        "assets",
        "stacks",
        "album_memberships",
        "tag_memberships",
    }
    assert plan.steps[5].config.batch_size == 25

    restored = SyncPlan.model_validate_json(plan.model_dump_json())
    assert restored == plan


@pytest.mark.asyncio
async def test_incremental_plan_includes_capability_event_and_window_scope() -> None:
    immich = FakeImmich(stream=True)
    planner = SyncPlanner(immich, Settings(sync_batch_size=25))
    current = run("incremental")

    plan = await planner.for_run(current, runtime())

    assert [item.step for item in plan.steps] == [
        "events",
        "catalogs",
        "assets",
        "stacks",
        "relationships",
        "validation",
        "finalization",
    ]
    assert immich.capability_calls == 1
    assets = plan.steps[2]
    assert isinstance(assets.scope, AssetScope)
    assert assets.scope.selection == WindowSelection(
        start=current.window_start,
        end=current.window_end,
    )
    relationships = plan.steps[4].scope
    assert relationships.strategy == "automatic"  # type: ignore[union-attr]
    assert relationships.assets == GenerationSelection(generation=73)  # type: ignore[union-attr]
    assert plan.steps[5].scope.allow_counter_repair is False  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_incremental_plan_omits_events_and_preserves_forced_relation_strategy() -> None:
    planner = SyncPlanner(FakeImmich(stream=False), Settings(sync_batch_size=25))

    plan = await planner.for_run(
        run("incremental", attempts=2),
        runtime(strategy="relation"),
    )

    assert [item.step for item in plan.steps] == [
        "catalogs",
        "assets",
        "stacks",
        "relationships",
        "validation",
        "finalization",
    ]
    relationships = plan.steps[3].scope
    assert relationships.strategy == "by_relation"  # type: ignore[union-attr]
    assert relationships.assets is None  # type: ignore[union-attr]
    assert isinstance(relationships.albums, AllSelection)  # type: ignore[union-attr]
    assert isinstance(relationships.tags, AllSelection)  # type: ignore[union-attr]
    assert plan.steps[4].scope.allow_counter_repair is True  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_incremental_plan_maps_forced_asset_strategy_and_runtime_controls() -> None:
    planner = SyncPlanner(FakeImmich(stream=False), Settings(sync_batch_size=25))

    plan = await planner.for_run(
        run("incremental"),
        runtime(strategy="asset"),
    )

    assets = plan.steps[1]
    relationships = plan.steps[3]
    assert assets.config.batch_size == 25
    assert assets.config.page_size == 750
    assert assets.config.page_prefetch == 2
    assert assets.config.concurrency == 3
    assert assets.config.min_batch_delay_seconds == 0
    assert relationships.scope.strategy == "by_asset"  # type: ignore[union-attr]
    assert relationships.config.concurrency == 6
    assert relationships.config.metadata_concurrency == 3
    assert relationships.config.page_prefetch == 2


def test_planned_step_rejects_mismatched_scope() -> None:
    with pytest.raises(ValidationError, match="cannot execute"):
        PlannedSyncStep(
            step="assets",
            scope=CatalogScope(
                albums=AllSelection(),
                tags=AllSelection(),
            ),
        )

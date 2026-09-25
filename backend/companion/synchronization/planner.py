"""Serializable synchronization plans and full/incremental planner presets."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from companion.config import Settings
from companion.immich import ImmichApiClient
from companion.sync_schema import SyncMode, SyncRunStatus
from companion.sync_settings import SyncRuntimeSettings
from companion.synchronization.evidence import SyncDomain
from companion.synchronization.scopes import (
    AssetScope,
    CatalogScope,
    EventScope,
    FinalizationScope,
    RelationshipScope,
    StackScope,
    SyncScope,
    SyncStepName,
    ValidationScope,
)
from companion.synchronization.selections import (
    AllSelection,
    GenerationSelection,
    WindowSelection,
)


class SyncStepConfigOverride(BaseModel):
    """Serializable run-specific operational settings for one planned step."""

    batch_size: int | None = Field(default=None, ge=1)
    page_size: int | None = Field(default=None, ge=1)
    concurrency: int | None = Field(default=None, ge=1)
    page_prefetch: int | None = Field(default=None, ge=0)
    metadata_concurrency: int | None = Field(default=None, ge=1)
    min_batch_delay_seconds: float | None = Field(default=None, ge=0)


class PlannedSyncStep(BaseModel):
    """One ordered step in a synchronization plan."""

    step: SyncStepName
    scope: SyncScope
    config: SyncStepConfigOverride | None = None

    @model_validator(mode="after")
    def validate_scope_matches_step(self) -> Self:
        if self.scope.kind != self.step:
            raise ValueError(
                f"Planned step {self.step!r} cannot execute {self.scope.kind!r} scope"
            )
        return self


class SyncPlan(BaseModel):
    """Persistable/debuggable ordered synchronization plan."""

    mode: SyncMode
    generation: int = Field(ge=0)
    steps: list[PlannedSyncStep] = Field(min_length=1)


_EXPECTED_DOMAINS: set[SyncDomain] = {
    "albums",
    "tags",
    "assets",
    "stacks",
    "album_memberships",
    "tag_memberships",
}


class SyncPlanner:
    """Build full/incremental presets without executing synchronization."""

    def __init__(self, immich: ImmichApiClient, settings: Settings) -> None:
        self._immich = immich
        self._settings = settings

    async def for_run(
        self,
        run: SyncRunStatus,
        runtime: SyncRuntimeSettings,
    ) -> SyncPlan:
        if run.mode == "full":
            return self.build_full(run, runtime)
        return await self.build_incremental(run, runtime)

    def build_full(
        self,
        run: SyncRunStatus,
        runtime: SyncRuntimeSettings,
    ) -> SyncPlan:
        return SyncPlan(
            mode="full",
            generation=run.generation,
            steps=self._base_steps(
                run,
                runtime,
                asset_scope=AssetScope(selection=AllSelection()),
                relationship_scope=RelationshipScope(
                    kinds={"albums", "tags"},
                    strategy="by_relation",
                    albums=AllSelection(),
                    tags=AllSelection(),
                ),
            ),
        )

    async def build_incremental(
        self,
        run: SyncRunStatus,
        runtime: SyncRuntimeSettings,
    ) -> SyncPlan:
        if run.window_start is None:
            raise ValueError("Incremental sync planning requires window_start")

        steps: list[PlannedSyncStep] = []
        capabilities = (
            await self._immich.sync_capabilities()
            if hasattr(self._immich, "sync_capabilities")
            else None
        )
        if capabilities is not None and capabilities.stream:
            steps.append(
                PlannedSyncStep(
                    step="events",
                    scope=EventScope(
                        cursor=run.cursor if run.phase == "queued" else None
                    ),
                )
            )

        relationship_strategy: Literal["automatic", "by_asset", "by_relation"] = {
            "automatic": "automatic",
            "asset": "by_asset",
            "relation": "by_relation",
        }[runtime.incremental_strategy]
        if relationship_strategy == "by_relation":
            relationship_scope = RelationshipScope(
                kinds={"albums", "tags"},
                strategy="by_relation",
                albums=AllSelection(),
                tags=AllSelection(),
            )
        else:
            relationship_scope = RelationshipScope(
                kinds={"albums", "tags"},
                strategy=relationship_strategy,
                assets=GenerationSelection(generation=run.generation),
                albums=AllSelection(),
                tags=AllSelection(),
            )

        steps.extend(
            self._base_steps(
                run,
                runtime,
                asset_scope=AssetScope(
                    selection=WindowSelection(
                        start=run.window_start,
                        end=run.window_end,
                    )
                ),
                relationship_scope=relationship_scope,
            )
        )
        return SyncPlan(
            mode="incremental",
            generation=run.generation,
            steps=steps,
        )

    def _base_steps(
        self,
        run: SyncRunStatus,
        runtime: SyncRuntimeSettings,
        *,
        asset_scope: AssetScope,
        relationship_scope: RelationshipScope,
    ) -> list[PlannedSyncStep]:
        batch_size = run.full_batch_size or (
            self._settings.sync_full_batch_size
            if run.mode == "full"
            else self._settings.sync_batch_size
        )
        pace = (
            runtime.full_min_batch_delay_seconds
            if run.mode == "full"
            else 0.0
        )
        return [
            PlannedSyncStep(
                step="catalogs",
                scope=CatalogScope(
                    albums=AllSelection(),
                    tags=AllSelection(),
                ),
                config=SyncStepConfigOverride(
                    batch_size=batch_size,
                    concurrency=1,
                    min_batch_delay_seconds=pace,
                ),
            ),
            PlannedSyncStep(
                step="assets",
                scope=asset_scope,
                config=SyncStepConfigOverride(
                    batch_size=batch_size,
                    page_size=runtime.api_page_size,
                    concurrency=runtime.metadata_request_concurrency,
                    page_prefetch=runtime.page_prefetch,
                    min_batch_delay_seconds=pace,
                ),
            ),
            PlannedSyncStep(
                step="stacks",
                scope=StackScope(selection=AllSelection()),
                config=SyncStepConfigOverride(
                    batch_size=batch_size,
                    concurrency=1,
                    min_batch_delay_seconds=pace,
                ),
            ),
            PlannedSyncStep(
                step="relationships",
                scope=relationship_scope,
                config=SyncStepConfigOverride(
                    batch_size=batch_size,
                    page_size=runtime.api_page_size,
                    concurrency=runtime.tag_association_concurrency,
                    page_prefetch=runtime.page_prefetch,
                    metadata_concurrency=runtime.metadata_request_concurrency,
                    min_batch_delay_seconds=pace,
                ),
            ),
            PlannedSyncStep(
                step="validation",
                scope=ValidationScope(
                    generation=run.generation,
                    expected_domains=set(_EXPECTED_DOMAINS),
                    allow_counter_repair=run.attempts > 1,
                ),
            ),
            PlannedSyncStep(
                step="finalization",
                scope=FinalizationScope(generation=run.generation),
                config=SyncStepConfigOverride(batch_size=batch_size),
            ),
        ]


__all__ = [
    "PlannedSyncStep",
    "SyncPlan",
    "SyncPlanner",
    "SyncStepConfigOverride",
]

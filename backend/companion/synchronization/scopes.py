"""Typed scopes for first-class synchronization steps."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from companion.synchronization.evidence import SyncDomain
from companion.synchronization.selections import (
    AlbumSelection,
    AssetSelection,
    StackSelection,
    TagSelection,
)

type SyncStepName = Literal[
    "events",
    "catalogs",
    "assets",
    "stacks",
    "relationships",
    "validation",
    "finalization",
]

SYNC_STEP_NAMES: tuple[SyncStepName, ...] = (
    "events",
    "catalogs",
    "assets",
    "stacks",
    "relationships",
    "validation",
    "finalization",
)

type RelationshipKind = Literal["albums", "tags"]
type RelationshipStrategy = Literal["automatic", "by_asset", "by_relation"]


class EventScope(BaseModel):
    """Optional incremental event-stream scope."""

    kind: Literal["events"] = "events"
    cursor: str | None = None


class CatalogScope(BaseModel):
    """Album/tag catalog domains to synchronize."""

    kind: Literal["catalogs"] = "catalogs"
    albums: AlbumSelection | None = None
    tags: TagSelection | None = None

    @model_validator(mode="after")
    def require_domain(self) -> Self:
        if self.albums is None and self.tags is None:
            raise ValueError("Catalog scope requires albums and/or tags")
        return self


class AssetScope(BaseModel):
    """Assets selected for synchronization."""

    kind: Literal["assets"] = "assets"
    selection: AssetSelection


class StackScope(BaseModel):
    """Stacks selected for synchronization."""

    kind: Literal["stacks"] = "stacks"
    selection: StackSelection


class RelationshipScope(BaseModel):
    """Relationship kinds, strategy, and typed target selections."""

    kind: Literal["relationships"] = "relationships"
    kinds: set[RelationshipKind] = Field(min_length=1)
    strategy: RelationshipStrategy
    assets: AssetSelection | None = None
    albums: AlbumSelection | None = None
    tags: TagSelection | None = None

    @model_validator(mode="after")
    def validate_strategy_inputs(self) -> Self:
        if "albums" not in self.kinds and self.albums is not None:
            raise ValueError("Album selection requires the albums relationship kind")
        if "tags" not in self.kinds and self.tags is not None:
            raise ValueError("Tag selection requires the tags relationship kind")

        if self.strategy in {"by_asset", "automatic"} and self.assets is None:
            raise ValueError(f"{self.strategy} relationship strategy requires assets")

        if self.strategy == "by_relation":
            if self.assets is not None:
                raise ValueError("by_relation relationship strategy does not accept assets")
            if "albums" in self.kinds and self.albums is None:
                raise ValueError("by_relation albums require an album selection")
            if "tags" in self.kinds and self.tags is None:
                raise ValueError("by_relation tags require a tag selection")
        return self


class ValidationScope(BaseModel):
    """Generation and domains whose synchronized state must be validated."""

    kind: Literal["validation"] = "validation"
    generation: int = Field(ge=0)
    expected_domains: set[SyncDomain] = Field(min_length=1)
    allow_counter_repair: bool = False


class FinalizationScope(BaseModel):
    """Generation finalization request.

    Manual execution will later require a validation task reference plus explicit
    destructive confirmation. Orchestrated execution can use the same scope without
    a human confirmation once planner/evidence authority is established.
    """

    kind: Literal["finalization"] = "finalization"
    generation: int = Field(ge=0)
    validation_task_id: UUID | None = None
    confirm_destructive: bool = False


type SyncScope = Annotated[
    EventScope
    | CatalogScope
    | AssetScope
    | StackScope
    | RelationshipScope
    | ValidationScope
    | FinalizationScope,
    Field(discriminator="kind"),
]


__all__ = [
    "AssetScope",
    "CatalogScope",
    "EventScope",
    "FinalizationScope",
    "RelationshipKind",
    "RelationshipScope",
    "RelationshipStrategy",
    "SYNC_STEP_NAMES",
    "StackScope",
    "SyncScope",
    "SyncStepName",
    "ValidationScope",
]

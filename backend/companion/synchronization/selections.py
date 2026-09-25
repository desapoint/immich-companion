"""Serializable selection contracts for first-class synchronization steps."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Literal, Protocol, Self, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from companion.action_schema import AssetSelectionRequest


class AllSelection(BaseModel):
    """Select the complete domain supported by a synchronization step."""

    kind: Literal["all"] = "all"


class ExplicitIdsSelection(BaseModel):
    """Select a bounded set of entity identifiers."""

    kind: Literal["ids"] = "ids"
    ids: list[UUID] = Field(min_length=1)


class PersistedSelection(BaseModel):
    """Select entities from an existing server-owned selection set."""

    kind: Literal["selection"] = "selection"
    selection_id: UUID


class RequestSelection(BaseModel):
    """Select assets from the existing typed asset-selection request contract."""

    kind: Literal["request"] = "request"
    request: AssetSelectionRequest


class GenerationSelection(BaseModel):
    """Select entities stamped by one synchronization generation."""

    kind: Literal["generation"] = "generation"
    generation: int = Field(ge=0)


class WindowSelection(BaseModel):
    """Select remote entities observed within a bounded update window."""

    kind: Literal["window"] = "window"
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.start >= self.end:
            raise ValueError("Window selection start must be before end")
        return self


type AssetSelection = Annotated[
    AllSelection
    | ExplicitIdsSelection
    | PersistedSelection
    | RequestSelection
    | GenerationSelection
    | WindowSelection,
    Field(discriminator="kind"),
]

type AlbumSelection = Annotated[
    AllSelection | ExplicitIdsSelection | PersistedSelection,
    Field(discriminator="kind"),
]

type TagSelection = Annotated[
    AllSelection | ExplicitIdsSelection | PersistedSelection,
    Field(discriminator="kind"),
]


class AffectedAssetsSelection(BaseModel):
    """Select stack work derived from an asset selection."""

    kind: Literal["affected_assets"] = "affected_assets"
    assets: AssetSelection


type StackSelection = Annotated[
    AllSelection | ExplicitIdsSelection | PersistedSelection | AffectedAssetsSelection,
    Field(discriminator="kind"),
]

type SelectionSource = Annotated[
    AllSelection
    | ExplicitIdsSelection
    | PersistedSelection
    | RequestSelection
    | GenerationSelection
    | WindowSelection
    | AffectedAssetsSelection,
    Field(discriminator="kind"),
]


@runtime_checkable
class SyncSelectionResolver(Protocol):
    """Resolve typed selection descriptions into bounded identifier streams.

    Phase 1 defines this contract only. Database/query-backed implementations are
    introduced in the dedicated selection-resolver migration phase.
    """

    def iter_asset_ids(
        self,
        selection: AssetSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]: ...

    def iter_album_ids(
        self,
        selection: AlbumSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]: ...

    def iter_tag_ids(
        self,
        selection: TagSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]: ...

    def iter_stack_ids(
        self,
        selection: StackSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]: ...


__all__ = [
    "AffectedAssetsSelection",
    "AlbumSelection",
    "AllSelection",
    "AssetSelection",
    "ExplicitIdsSelection",
    "GenerationSelection",
    "PersistedSelection",
    "RequestSelection",
    "SelectionSource",
    "StackSelection",
    "SyncSelectionResolver",
    "TagSelection",
    "WindowSelection",
]

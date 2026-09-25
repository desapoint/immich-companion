"""Serializable selection contracts and bounded resolver for sync steps."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Annotated, Literal, Protocol, Self
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


class AssetSelectionIdRepository(Protocol):
    def iter_selection_ids(
        self,
        selection: AssetSelectionRequest,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]: ...

    def iter_generation_asset_ids(
        self,
        generation: int,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]: ...


class RelationSelectionIdRepository(Protocol):
    def iter_ids(
        self,
        selection_id: UUID,
        kind: Literal["album", "tag"],
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]: ...


class SyncSelectionResolver:
    """Resolve local/query-backed selections into bounded identifier streams.

    Complete and window selections intentionally remain remote traversal scopes.
    Synchronization steps consume those scopes directly so a local database result
    can never masquerade as complete Immich authority.
    """

    def __init__(
        self,
        assets: AssetSelectionIdRepository,
        relations: RelationSelectionIdRepository,
    ) -> None:
        self._assets = assets
        self._relations = relations

    @staticmethod
    def _validate_batch_size(batch_size: int) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

    @staticmethod
    def _explicit_batches(ids: list[UUID], batch_size: int) -> Iterator[list[UUID]]:
        unique_ids = list(dict.fromkeys(ids))
        for offset in range(0, len(unique_ids), batch_size):
            yield unique_ids[offset : offset + batch_size]

    async def iter_asset_ids(
        self,
        selection: AssetSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]:
        self._validate_batch_size(batch_size)

        if isinstance(selection, ExplicitIdsSelection):
            for batch in self._explicit_batches(selection.ids, batch_size):
                yield batch
            return

        if isinstance(selection, PersistedSelection):
            request = AssetSelectionRequest(
                mode="explicit",
                selection_id=selection.selection_id,
            )
            async for batch in self._assets.iter_selection_ids(
                request,
                batch_size=batch_size,
            ):
                yield batch
            return

        if isinstance(selection, RequestSelection):
            async for batch in self._assets.iter_selection_ids(
                selection.request,
                batch_size=batch_size,
            ):
                yield batch
            return

        if isinstance(selection, GenerationSelection):
            async for batch in self._assets.iter_generation_asset_ids(
                selection.generation,
                batch_size=batch_size,
            ):
                yield batch
            return

        if isinstance(selection, (AllSelection, WindowSelection)):
            raise ValueError(
                "All/window asset selections require remote traversal by the sync step"
            )

        raise TypeError(f"Unsupported asset selection: {type(selection).__name__}")

    async def _iter_relation_ids(
        self,
        selection: AlbumSelection | TagSelection,
        *,
        kind: Literal["album", "tag"],
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]:
        self._validate_batch_size(batch_size)

        if isinstance(selection, ExplicitIdsSelection):
            for batch in self._explicit_batches(selection.ids, batch_size):
                yield batch
            return

        if isinstance(selection, PersistedSelection):
            async for batch in self._relations.iter_ids(
                selection.selection_id,
                kind,
                batch_size=batch_size,
            ):
                yield batch
            return

        if isinstance(selection, AllSelection):
            raise ValueError(
                f"All {kind} selections require remote traversal by the sync step"
            )

        raise TypeError(f"Unsupported {kind} selection: {type(selection).__name__}")

    async def iter_album_ids(
        self,
        selection: AlbumSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]:
        async for batch in self._iter_relation_ids(
            selection,
            kind="album",
            batch_size=batch_size,
        ):
            yield batch

    async def iter_tag_ids(
        self,
        selection: TagSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]:
        async for batch in self._iter_relation_ids(
            selection,
            kind="tag",
            batch_size=batch_size,
        ):
            yield batch

    async def iter_stack_ids(
        self,
        selection: StackSelection,
        *,
        batch_size: int,
    ) -> AsyncIterator[list[UUID]]:
        self._validate_batch_size(batch_size)

        if isinstance(selection, ExplicitIdsSelection):
            for batch in self._explicit_batches(selection.ids, batch_size):
                yield batch
            return

        if isinstance(selection, AllSelection):
            raise ValueError("All stack selections require remote traversal by the sync step")
        if isinstance(selection, AffectedAssetsSelection):
            raise ValueError(
                "Affected-asset stack selection requires stack traversal by the sync step"
            )
        if isinstance(selection, PersistedSelection):
            raise ValueError("Persisted stack selections are not supported by current storage")

        raise TypeError(f"Unsupported stack selection: {type(selection).__name__}")


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

"""Synchronization authority and evidence contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, model_validator

from companion.synchronization.selections import (
    AllSelection,
    SelectionSource,
    WindowSelection,
)

type SyncDomain = Literal[
    "assets",
    "albums",
    "tags",
    "stacks",
    "album_memberships",
    "tag_memberships",
]


class SyncAuthority(StrEnum):
    """How much of one synchronization domain a step proved authoritative."""

    NONE = "none"
    SELECTED = "selected"
    WINDOW = "window"
    COMPLETE = "complete"


class SyncEvidence(BaseModel):
    """Durable declaration of the scope a synchronization result proved."""

    domain: SyncDomain
    authority: SyncAuthority
    selection: SelectionSource | None = None
    generation: int

    @model_validator(mode="after")
    def validate_authority(self) -> Self:
        if self.authority == SyncAuthority.SELECTED:
            if self.selection is None or isinstance(
                self.selection, (AllSelection, WindowSelection)
            ):
                raise ValueError("Selected authority requires a selected-scope source")
        elif self.authority == SyncAuthority.WINDOW:
            if not isinstance(self.selection, WindowSelection):
                raise ValueError("Window authority requires a window selection")
        elif (
            self.authority == SyncAuthority.COMPLETE
            and self.selection is not None
            and not isinstance(self.selection, AllSelection)
        ):
            raise ValueError("Complete authority may only reference an all selection")
        return self


__all__ = ["SyncAuthority", "SyncDomain", "SyncEvidence"]

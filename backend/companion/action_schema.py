"""Typed selection, action-plan, and execution contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from companion.asset_schema import SearchGroup

SelectionMode = Literal["explicit", "all_matching"]
AssetActionIntent = Literal[
    "archive_toggle",
    "favorite_toggle",
    "trash",
    "restore",
    "add_album",
    "add_tag",
    "remove_album",
    "remove_tag",
]
AssetActionOperation = Literal[
    "archive",
    "unarchive",
    "favorite",
    "unfavorite",
    "trash",
    "restore",
    "add_album",
    "add_tag",
    "remove_album",
    "remove_tag",
]
ActionPlanStatus = Literal[
    "planned",
    "running",
    "completed",
    "failed",
    "drifted",
    "expired",
]


class AssetSelectionRequest(BaseModel):
    """An explicit or backend-resolved action target."""

    mode: SelectionMode
    ids: list[UUID] = Field(default_factory=list, max_length=5000)
    expression: SearchGroup | None = None
    excluded_ids: list[UUID] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def validate_mode(self) -> AssetSelectionRequest:
        self.ids = list(dict.fromkeys(self.ids))
        self.excluded_ids = list(dict.fromkeys(self.excluded_ids))
        if self.mode == "explicit":
            if not self.ids:
                raise ValueError("Explicit selection requires at least one asset ID")
            if self.expression is not None or self.excluded_ids:
                raise ValueError("Explicit selection accepts IDs only")
        elif self.expression is None:
            raise ValueError("All-matching selection requires a search expression")
        elif self.ids:
            raise ValueError("All-matching selection does not accept explicit IDs")
        return self


class AssetSelectionSummary(BaseModel):
    """Action-relevant aggregate state for one resolved selection."""

    total: int
    archived: int
    unarchived: int
    favorite: int
    not_favorite: int
    trashed: int
    not_trashed: int
    archive_action: Literal["archive", "unarchive"] | None
    favorite_action: Literal["favorite", "unfavorite"] | None
    can_trash: bool
    can_restore: bool


class AssetSelectionResolution(BaseModel):
    """Exact backend resolution used for previewing and executing actions."""

    ids: list[UUID]
    missing_ids: list[UUID]
    summary: AssetSelectionSummary


class AssetActionPlanRequest(BaseModel):
    """Request a reviewable action plan for a resolved selection."""

    selection: AssetSelectionRequest
    action: AssetActionIntent
    relation_ids: list[UUID] = Field(default_factory=list, min_length=0, max_length=100)

    @model_validator(mode="after")
    def validate_relation(self) -> AssetActionPlanRequest:
        self.relation_ids = list(dict.fromkeys(self.relation_ids))
        relation_action = self.action in {
            "add_album",
            "add_tag",
            "remove_album",
            "remove_tag",
        }
        if relation_action != bool(self.relation_ids):
            raise ValueError("Album and tag actions require one or more relation IDs")
        return self


class AssetActionRelationPlan(BaseModel):
    """Per-relation applicability included in a reviewed plan."""

    relation_id: UUID
    applicable_count: int
    skipped_count: int


class AssetActionPlan(BaseModel):
    """Persisted immutable preview shown before an action is executed."""

    id: UUID
    action: AssetActionIntent
    operation: AssetActionOperation
    relation_ids: list[UUID]
    relations: list[AssetActionRelationPlan]
    target_count: int
    applicable_count: int
    skipped_count: int
    missing_ids: list[UUID]
    destructive: bool
    status: ActionPlanStatus
    expires_at: datetime


class AssetActionExecuteRequest(BaseModel):
    """Explicit confirmation for one reviewed plan."""

    plan_id: UUID
    confirm: bool

    @model_validator(mode="after")
    def require_confirmation(self) -> AssetActionExecuteRequest:
        if not self.confirm:
            raise ValueError("Action execution requires explicit confirmation")
        return self


class AssetActionRelationResult(BaseModel):
    """Verified outcome for one album or tag in a multi-relation action."""

    relation_id: UUID
    applied_ids: list[UUID]
    skipped_ids: list[UUID]
    failed_ids: list[UUID]


class AssetActionResult(BaseModel):
    """Final synchronous action outcome."""

    plan_id: UUID
    operation: AssetActionOperation
    target_count: int
    applied_count: int
    skipped_count: int
    applied_ids: list[UUID]
    skipped_ids: list[UUID]
    failed_ids: list[UUID]
    relation_results: list[AssetActionRelationResult] = Field(default_factory=list)
    verified: bool
    status: ActionPlanStatus

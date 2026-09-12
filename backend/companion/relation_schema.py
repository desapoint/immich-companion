"""Public contracts for relation management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AlbumManagementItem(BaseModel):
    id: UUID
    name: str
    description: str = ""
    album_thumbnail_asset_id: UUID | None = None
    asset_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TagManagementItem(BaseModel):
    id: UUID
    name: str
    color: str | None = None
    parent_id: UUID | None = None
    parent_path: list[str] = Field(default_factory=list)
    asset_count: int = 0
    child_count: int = 0
    real_tag_ids: list[UUID] = Field(default_factory=list)
    children: list[TagManagementItem] = Field(default_factory=list)


class RelationPage[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class AlbumCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class AlbumUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    color: str | None = Field(default=None, max_length=32)
    parent_id: UUID | None = None


class TagUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str | None = Field(default=None, max_length=32)


class RelationBatchDeleteRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=10000)


class RelationSelectionMembersRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=2000)
    selected: bool
    revision: int = Field(ge=0)


class RelationSelectionMembershipRequest(BaseModel):
    ids: list[UUID] = Field(default_factory=list, max_length=2000)


class RelationSelectAllRequest(BaseModel):
    query: str = Field(default="", max_length=255)
    include_hierarchy: bool = False


class RelationMatchingSelectionRequest(RelationSelectAllRequest):
    selected: bool
    revision: int = Field(ge=0)


class RelationMatchingSelectionState(BaseModel):
    matching_count: int
    selected_matching_count: int


class CollectionDeletePlanRequest(BaseModel):
    selection_id: UUID


class CollectionDeleteExecuteRequest(BaseModel):
    plan_id: UUID


class CollectionDeleteItemResult(BaseModel):
    id: UUID
    status: Literal["completed", "skipped", "failed"]
    reason: str | None = None


class CollectionDeletePlan(BaseModel):
    id: UUID
    entity_kind: Literal["album", "tag"]
    selection_id: UUID
    target_digest: str
    target_count: int
    applicable_count: int
    skipped_count: int
    status: Literal["planned", "running", "partial", "completed", "failed", "expired"]
    expires_at: datetime
    results: list[CollectionDeleteItemResult] = Field(default_factory=list)

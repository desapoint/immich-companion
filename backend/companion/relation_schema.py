"""Public contracts for relation management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AlbumManagementItem(BaseModel):
    id: UUID
    name: str
    description: str = ""
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
    name: str | None = Field(default=None, min_length=1, max_length=255)
    color: str | None = Field(default=None, max_length=32)
    parent_id: UUID | None = None


class RelationBatchDeleteRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=10000)

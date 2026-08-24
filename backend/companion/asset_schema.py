"""Typed public contracts for asset sync, search, cards, and details."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from companion.immich import ImmichAsset
from companion.models import AssetRecord


class AssetSearchQuery(BaseModel):
    """Validated SQL search criteria."""

    query: str | None = Field(default=None, max_length=500)
    asset_type: Literal["IMAGE", "VIDEO", "AUDIO", "OTHER"] | None = None
    taken_after: datetime | None = None
    taken_before: datetime | None = None
    min_width: int | None = Field(default=None, ge=1)
    max_width: int | None = Field(default=None, ge=1)
    min_height: int | None = Field(default=None, ge=1)
    max_height: int | None = Field(default=None, ge=1)
    min_aspect_ratio: float | None = Field(default=None, gt=0)
    max_aspect_ratio: float | None = Field(default=None, gt=0)
    favorite: bool | None = None
    archived: bool | None = None
    trashed: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=48, ge=1, le=200)


SearchField = Literal[
    "filename",
    "type",
    "taken_at",
    "width",
    "height",
    "aspect_ratio",
    "favorite",
    "archived",
    "trashed",
    "album",
]
SearchOperator = Literal[
    "contains",
    "equals",
    "not_equals",
    "after",
    "before",
    "at_least",
    "at_most",
    "in_album",
    "not_in_album",
]


class SearchCondition(BaseModel):
    """One allow-listed leaf in a structured asset search."""

    kind: Literal["condition"] = "condition"
    field: SearchField
    operator: SearchOperator
    value: str | int | float | bool

    @model_validator(mode="after")
    def validate_field_operator_value(self) -> SearchCondition:
        allowed: dict[str, set[str]] = {
            "filename": {"contains", "equals", "not_equals"},
            "type": {"equals", "not_equals"},
            "taken_at": {"after", "before"},
            "width": {"equals", "at_least", "at_most"},
            "height": {"equals", "at_least", "at_most"},
            "aspect_ratio": {"equals", "at_least", "at_most"},
            "favorite": {"equals"},
            "archived": {"equals"},
            "trashed": {"equals"},
            "album": {"in_album", "not_in_album"},
        }
        if self.operator not in allowed[self.field]:
            raise ValueError(f"Operator {self.operator!r} is not valid for {self.field!r}")
        if self.field in {"favorite", "archived", "trashed"} and not isinstance(
            self.value, bool
        ):
            raise ValueError(f"{self.field!r} requires a boolean value")
        if self.field in {"width", "height"} and (
            isinstance(self.value, bool)
            or not isinstance(self.value, int)
            or self.value < 1
        ):
            raise ValueError(f"{self.field!r} requires a positive integer")
        if self.field == "aspect_ratio":
            if isinstance(self.value, bool) or not isinstance(self.value, int | float):
                raise ValueError("'aspect_ratio' requires a positive number")
            if float(self.value) <= 0:
                raise ValueError("'aspect_ratio' requires a positive number")
        if self.field == "taken_at":
            if not isinstance(self.value, str):
                raise ValueError("'taken_at' requires an ISO date-time string")
            try:
                datetime.fromisoformat(self.value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("'taken_at' requires an ISO date-time string") from error
        if self.field == "album":
            if not isinstance(self.value, str):
                raise ValueError("'album' requires an album UUID")
            try:
                UUID(self.value)
            except ValueError as error:
                raise ValueError("'album' requires an album UUID") from error
        if self.field == "type" and self.value not in {"IMAGE", "VIDEO", "AUDIO", "OTHER"}:
            raise ValueError("'type' requires a supported media type")
        if self.field == "filename" and (
            not isinstance(self.value, str) or not self.value.strip()
        ):
            raise ValueError("'filename' requires non-empty text")
        return self


class SearchGroup(BaseModel):
    """Recursive boolean search group."""

    kind: Literal["group"] = "group"
    operator: Literal["and", "or"] = "and"
    negate: bool = False
    children: list[SearchNode] = Field(default_factory=list, max_length=100)


SearchNode = Annotated[SearchCondition | SearchGroup, Field(discriminator="kind")]
SearchGroup.model_rebuild()


class StructuredAssetSearchQuery(BaseModel):
    """Recursive search request with stable pagination."""

    expression: SearchGroup = Field(default_factory=SearchGroup)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=48, ge=1, le=200)


class AlbumOption(BaseModel):
    """Compact album choice for search controls."""

    id: UUID
    name: str
    asset_count: int


class AssetSummary(BaseModel):
    """Compact asset representation consumed by cards and the viewer footer."""

    id: UUID
    type: str
    original_file_name: str
    original_mime_type: str | None
    width: int | None
    height: int | None
    duration: int | None
    taken_at: datetime
    file_modified_at: datetime
    is_favorite: bool
    is_archived: bool
    is_trashed: bool
    is_offline: bool
    is_edited: bool
    visibility: str | None
    has_metadata: bool
    live_photo_video_id: str | None
    file_size_bytes: int | None
    people_count: int
    tag_count: int
    stack_count: int

    @classmethod
    def from_record(cls, asset: AssetRecord) -> AssetSummary:
        exif = asset.exif_info or {}
        file_size = exif.get("fileSizeInByte")
        stack = asset.stack or {}
        stack_assets = stack.get("assets", [])
        stack_asset_count = stack.get("assetCount")
        if not isinstance(stack_asset_count, int):
            stack_asset_count = len(stack_assets) if isinstance(stack_assets, list) else 0
        return cls(
            id=asset.id,
            type=asset.asset_type,
            original_file_name=asset.original_file_name,
            original_mime_type=asset.original_mime_type,
            width=asset.width,
            height=asset.height,
            duration=asset.duration,
            taken_at=asset.file_created_at,
            file_modified_at=asset.file_modified_at,
            is_favorite=asset.is_favorite,
            is_archived=asset.is_archived,
            is_trashed=asset.is_trashed,
            is_offline=asset.is_offline,
            is_edited=asset.is_edited,
            visibility=asset.visibility,
            has_metadata=asset.has_metadata,
            live_photo_video_id=asset.live_photo_video_id,
            file_size_bytes=file_size if isinstance(file_size, int) else None,
            people_count=len(asset.people or []),
            tag_count=len(asset.tags or []),
            stack_count=stack_asset_count,
        )


class AssetSearchResponse(BaseModel):
    """Stable page of SQL-backed asset summaries."""

    items: list[AssetSummary]
    total: int
    page: int
    page_size: int
    pages: int


class AssetDetail(BaseModel):
    """Live Immich details used by the fullscreen viewer."""

    id: UUID
    owner_id: UUID | None
    library_id: UUID | None
    type: str
    original_file_name: str
    original_path: str | None
    original_mime_type: str | None
    width: int | None
    height: int | None
    duration: int | None
    taken_at: datetime
    file_modified_at: datetime
    created_at: datetime | None
    updated_at: datetime | None
    is_favorite: bool
    is_archived: bool
    is_trashed: bool
    is_offline: bool
    is_edited: bool
    visibility: str | None
    live_photo_video_id: str | None
    exif_info: dict[str, Any] | None
    people: list[dict[str, Any]]
    tags: list[dict[str, Any]]
    stack: dict[str, Any] | None
    immich_url: str | None

    @classmethod
    def from_immich(cls, asset: ImmichAsset, immich_url: str | None) -> AssetDetail:
        return cls(
            id=asset.id,
            owner_id=asset.owner_id,
            library_id=asset.library_id,
            type=asset.asset_type,
            original_file_name=asset.original_file_name,
            original_path=asset.original_path,
            original_mime_type=asset.original_mime_type,
            width=asset.width,
            height=asset.height,
            duration=asset.duration,
            taken_at=asset.file_created_at,
            file_modified_at=asset.file_modified_at,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            is_favorite=asset.is_favorite,
            is_archived=asset.is_archived,
            is_trashed=asset.is_trashed,
            is_offline=asset.is_offline,
            is_edited=asset.is_edited,
            visibility=asset.visibility,
            live_photo_video_id=asset.live_photo_video_id,
            exif_info=asset.exif_info,
            people=asset.people,
            tags=asset.tags,
            stack=asset.stack,
            immich_url=immich_url,
        )


class AssetSyncResult(BaseModel):
    """Result of one complete asset reconciliation."""

    seen: int
    created: int
    updated: int
    removed: int
    completed_at: datetime

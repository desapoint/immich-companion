"""Typed public contracts for asset sync, search, cards, and details."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from companion.immich import ImmichAsset
from companion.models import AssetRecord

AssetSortField = Literal[
    "taken_at",
    "filename",
    "created_at",
    "modified_at",
    "width",
    "height",
]
AssetSortDirection = Literal["asc", "desc"]


def parse_aspect_ratio(value: str | int | float) -> float:
    """Parse a positive decimal or fraction without accepting partial values."""

    if isinstance(value, bool):
        raise ValueError("'aspect_ratio' requires a positive decimal or fraction")
    parts = [str(part).strip() for part in str(value).strip().split("/")]
    if len(parts) not in {1, 2} or any(
        re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", part) is None for part in parts
    ):
        raise ValueError("'aspect_ratio' requires a positive decimal or fraction")
    try:
        numbers = [Decimal(part) for part in parts]
    except InvalidOperation as error:
        raise ValueError("'aspect_ratio' requires a positive decimal or fraction") from error
    if any(not number.is_finite() or number <= 0 for number in numbers):
        raise ValueError("'aspect_ratio' requires a positive decimal or fraction")
    if len(numbers) == 2:
        return float(numbers[0] / numbers[1])
    return float(numbers[0])


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
    sort_field: AssetSortField = "taken_at"
    sort_direction: AssetSortDirection = "desc"
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
    "tag",
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
    "in_any",
    "in_all",
    "not_in_any",
    "has_none",
]


class SearchCondition(BaseModel):
    """One allow-listed leaf in a structured asset search."""

    kind: Literal["condition"] = "condition"
    field: SearchField
    operator: SearchOperator
    value: str | int | float | bool | list[str] | None = None

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
            "album": {
                "in_album",
                "not_in_album",
                "in_any",
                "in_all",
                "not_in_any",
                "has_none",
            },
            "tag": {"in_any", "in_all", "not_in_any", "has_none"},
        }
        if self.operator not in allowed[self.field]:
            raise ValueError(f"Operator {self.operator!r} is not valid for {self.field!r}")
        if self.field in {"album", "tag"}:
            if self.operator == "has_none":
                if self.value not in (None, []):
                    raise ValueError(f"{self.field!r} with 'has_none' does not accept values")
                self.value = []
                return self
            if self.operator in {"in_album", "not_in_album"}:
                if self.field != "album" or not isinstance(self.value, str):
                    raise ValueError("Legacy album membership requires one album UUID")
                values = [self.value]
                self.operator = "in_any" if self.operator == "in_album" else "not_in_any"
            elif isinstance(self.value, list):
                values = self.value
            else:
                raise ValueError(f"{self.field!r} requires a list of UUIDs")
            if not values or len(values) > 100:
                raise ValueError(f"{self.field!r} requires between 1 and 100 UUIDs")
            normalized: list[str] = []
            for item in values:
                try:
                    identifier = str(UUID(item))
                except (TypeError, ValueError) as error:
                    raise ValueError(f"{self.field!r} requires valid UUIDs") from error
                if identifier not in normalized:
                    normalized.append(identifier)
            self.value = normalized
            return self
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
            self.value = parse_aspect_ratio(self.value)
        if self.field == "taken_at":
            if not isinstance(self.value, str):
                raise ValueError("'taken_at' requires an ISO date-time string")
            try:
                datetime.fromisoformat(self.value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("'taken_at' requires an ISO date-time string") from error
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
    sort_field: AssetSortField = "taken_at"
    sort_direction: AssetSortDirection = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=48, ge=1, le=200)


class AlbumOption(BaseModel):
    """Compact album choice for search controls."""

    id: UUID
    name: str
    asset_count: int


class TagOption(BaseModel):
    """Compact tag choice for search controls."""

    id: UUID
    name: str
    color: str | None
    asset_count: int


class AssetAlbumSummary(BaseModel):
    """Album membership displayed on an asset card."""

    id: UUID
    name: str


class AssetTagSummary(BaseModel):
    """Compact Immich tag displayed on an asset card."""

    id: str
    name: str
    color: str | None = None


class AssetStackMemberSummary(BaseModel):
    """Compact stack member sufficient for thumbnails and fullscreen comparison."""

    id: UUID
    type: str
    original_file_name: str
    original_mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    taken_at: datetime | None = None


class AssetStackSummary(BaseModel):
    """Current stack identity and previewable member list."""

    id: UUID
    primary_asset_id: UUID
    asset_count: int
    assets: list[AssetStackMemberSummary]


class AssetSourceSummary(BaseModel):
    """Safe source metadata used to distinguish external-library assets."""

    kind: Literal["upload", "external"]
    library_id: UUID | None
    original_path: str | None


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
    albums: list[AssetAlbumSummary]
    tags: list[AssetTagSummary]
    stack: AssetStackSummary | None
    source: AssetSourceSummary
    immich_url: str | None = None

    @classmethod
    def from_record(
        cls,
        asset: AssetRecord,
        albums: list[AssetAlbumSummary] | None = None,
    ) -> AssetSummary:
        exif = asset.exif_info or {}
        file_size = exif.get("fileSizeInByte")
        stack = asset.stack or {}
        stack_assets = stack.get("assets", [])
        stack_asset_count = stack.get("assetCount")
        if not isinstance(stack_asset_count, int):
            stack_asset_count = len(stack_assets) if isinstance(stack_assets, list) else 0
        compact_tags: list[AssetTagSummary] = []
        for index, tag in enumerate(asset.tags or []):
            if not isinstance(tag, dict):
                continue
            name = tag.get("name") or tag.get("value")
            if not isinstance(name, str) or not name.strip():
                continue
            identifier = tag.get("id")
            compact_tags.append(
                AssetTagSummary(
                    id=str(identifier) if identifier is not None else f"tag-{index}-{name}",
                    name=name,
                    color=tag.get("color") if isinstance(tag.get("color"), str) else None,
                )
            )

        compact_stack: AssetStackSummary | None = None
        stack_id = stack.get("id")
        primary_asset_id = stack.get("primaryAssetId")
        if stack_id and primary_asset_id:
            compact_members: list[AssetStackMemberSummary] = []
            if isinstance(stack_assets, list):
                for member in stack_assets:
                    if not isinstance(member, dict):
                        continue
                    member_id = member.get("id")
                    filename = member.get("originalFileName")
                    if not member_id or not isinstance(filename, str):
                        continue
                    compact_members.append(
                        AssetStackMemberSummary(
                            id=member_id,
                            type=str(member.get("type") or "IMAGE"),
                            original_file_name=filename,
                            original_mime_type=(
                                member.get("originalMimeType")
                                if isinstance(member.get("originalMimeType"), str)
                                else None
                            ),
                            width=(
                                member.get("width")
                                if isinstance(member.get("width"), int)
                                else None
                            ),
                            height=(
                                member.get("height")
                                if isinstance(member.get("height"), int)
                                else None
                            ),
                            taken_at=member.get("fileCreatedAt"),
                        )
                    )
            compact_stack = AssetStackSummary(
                id=stack_id,
                primary_asset_id=primary_asset_id,
                asset_count=max(stack_asset_count, len(compact_members)),
                assets=compact_members,
            )
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
            tag_count=len(compact_tags),
            stack_count=compact_stack.asset_count if compact_stack else stack_asset_count,
            albums=albums or [],
            tags=compact_tags,
            stack=compact_stack,
            source=AssetSourceSummary(
                kind="external" if asset.library_id is not None else "upload",
                library_id=asset.library_id,
                original_path=(
                    asset.original_path if asset.library_id is not None else None
                ),
            ),
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

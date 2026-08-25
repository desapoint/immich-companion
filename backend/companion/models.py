"""SQLAlchemy models owned exclusively by Immich Companion."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for companion-owned tables."""


class AssetRecord(Base):
    """Synchronized, searchable Immich asset metadata."""

    __tablename__ = "assets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    library_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(24), index=True)
    original_file_name: Mapped[str] = mapped_column(Text)
    original_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    thumbhash: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    file_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_date_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    immich_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    immich_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_trashed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_offline: Mapped[bool] = mapped_column(Boolean, default=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    has_metadata: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    live_photo_video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exif_info: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    people: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    tags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    stack: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("ix_assets_original_file_name_lower", func.lower(original_file_name)),
        Index("ix_assets_dimensions", width, height),
    )


class AlbumRecord(Base):
    """Synchronized Immich album metadata."""

    __tablename__ = "albums"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    album_name: Mapped[str] = mapped_column(Text, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    album_thumbnail_asset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    immich_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    immich_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AlbumAssetRecord(Base):
    """Current many-to-many Immich album membership."""

    __tablename__ = "album_assets"

    album_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("albums.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )


class TagRecord(Base):
    """Synchronized Immich tag metadata used by relation search."""

    __tablename__ = "tags"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tag_name: Mapped[str] = mapped_column(Text, index=True)
    tag_value: Mapped[str] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TagAssetRecord(Base):
    """Current many-to-many Immich tag membership."""

    __tablename__ = "tag_assets"

    tag_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )


class ActionPlanRecord(Base):
    """Immutable reviewed action target plus its execution audit."""

    __tablename__ = "action_plans"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    action: Mapped[str] = mapped_column(String(32), index=True)
    operation: Mapped[str] = mapped_column(String(32), index=True)
    relation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    selection: Mapped[dict[str, Any]] = mapped_column(JSON)
    target_ids: Mapped[list[str]] = mapped_column(JSON)
    target_digest: Mapped[str] = mapped_column(String(64))
    applicable_ids: Mapped[list[str]] = mapped_column(JSON)
    skipped_ids: Mapped[list[str]] = mapped_column(JSON)
    missing_ids: Mapped[list[str]] = mapped_column(JSON)
    destructive: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="planned", index=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

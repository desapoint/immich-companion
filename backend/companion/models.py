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
    sync_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sync_generation: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    stack_generation: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
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
    sync_generation: Mapped[int] = mapped_column(BigInteger, default=0, index=True)


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
    sync_generation: Mapped[int] = mapped_column(BigInteger, default=0, index=True)


class TagRecord(Base):
    """Synchronized Immich tag metadata used by relation search."""

    __tablename__ = "tags"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tag_name: Mapped[str] = mapped_column(Text, index=True)
    tag_value: Mapped[str] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sync_generation: Mapped[int] = mapped_column(BigInteger, default=0, index=True)


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
    sync_generation: Mapped[int] = mapped_column(BigInteger, default=0, index=True)


class SyncCoordinatorRecord(Base):
    """Singleton durable sync lease, queue, and successful checkpoints."""

    __tablename__ = "sync_coordinator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    lease_owner: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    pending_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    generation_counter: Mapped[int] = mapped_column(BigInteger, default=0)
    authoritative_generation: Mapped[int] = mapped_column(BigInteger, default=0)
    successful_watermark: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SyncRunRecord(Base):
    """Persisted staged sync progress that survives reloads and restarts."""

    __tablename__ = "sync_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    phase: Mapped[str] = mapped_column(String(32), index=True)
    generation: Mapped[int] = mapped_column(BigInteger, index=True)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    owner_token: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskLaneRecord(Base):
    """Durable concurrency configuration for one coordinator lane."""

    __tablename__ = "task_lanes"

    lane_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskRecord(Base):
    """Generic durable unit of work claimed by a coordinator worker."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    deduplication_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lane_key: Mapped[str] = mapped_column(String(128), index=True)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    counters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    lease_owner: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tasks_claimable", status, next_attempt_at, priority, created_at),
        Index("ix_tasks_dedupe", task_type, deduplication_key, status),
    )


class TaskAttemptRecord(Base):
    """One durable execution attempt for a generic task."""

    __tablename__ = "task_attempts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(24), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskEventRecord(Base):
    """Append-only task lifecycle and checkpoint event."""

    __tablename__ = "task_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class TaskScheduleRecord(Base):
    """Database-backed recurring task schedule."""

    __tablename__ = "task_schedules"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(128), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    task_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    deduplication_policy: Mapped[str] = mapped_column(String(32), default="window")
    blocked_by: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SyncRuntimeSettingsRecord(Base):
    """Singleton, user-editable pacing settings for global synchronization."""

    __tablename__ = "sync_runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    full_batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    full_min_batch_delay_seconds: Mapped[float] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ActionPlanRecord(Base):
    """Immutable reviewed action target plus its execution audit."""

    __tablename__ = "action_plans"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    action: Mapped[str] = mapped_column(String(32), index=True)
    operation: Mapped[str] = mapped_column(String(32), index=True)
    relation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    relation_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    relation_work: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
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
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SelectionSetRecord(Base):
    """Server-owned selection metadata; members are stored in separate rows."""

    __tablename__ = "selection_sets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    selected_count: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SelectionSetMemberRecord(Base):
    """One selected asset in a server-owned selection set."""

    __tablename__ = "selection_set_members"

    selection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("selection_sets.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

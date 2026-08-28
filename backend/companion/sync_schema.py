"""Public and internal contracts for staged synchronization."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SyncMode = Literal["incremental", "full"]
SyncStatus = Literal["queued", "running", "completed", "failed", "recovering", "retrying"]
SyncPhase = Literal[
    "queued",
    "catalogs",
    "assets",
    "stacks",
    "relationships",
    "finalizing",
    "completed",
    "failed",
]


class SyncStartRequest(BaseModel):
    """Administrator request for routine or full staged synchronization."""

    mode: SyncMode = "incremental"


class SyncCapabilities(BaseModel):
    """Supported remote change inputs discovered from Immich."""

    stream: bool = False
    acknowledgements: bool = False
    bounded_updates: bool = True


class SyncEvent(BaseModel):
    """One typed, deduplicable change received from an Immich stream."""

    id: str
    kind: Literal["asset", "asset_deleted", "album_membership", "tag_membership", "stack", "reset"]
    entity_id: UUID | None = None
    version: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SyncMemorySnapshot(BaseModel):
    """Optional process-memory diagnostics captured at a durable checkpoint."""

    rss_bytes: int = Field(ge=0)
    rss_peak_bytes: int = Field(ge=0)
    python_bytes: int | None = Field(default=None, ge=0)
    python_peak_bytes: int | None = Field(default=None, ge=0)
    elapsed_seconds: float = Field(ge=0)
    batch: int | None = Field(default=None, ge=0)
    batch_size: int = Field(ge=1)


class SyncProgress(BaseModel):
    """User-facing progress for the active synchronization phase."""

    phase: SyncPhase
    completed: int = 0
    total: int | None = None
    percent: float | None = None
    detail: str | None = None
    memory: SyncMemorySnapshot | None = None


class SyncRunStatus(BaseModel):
    """Reload-safe progress for one durable sync run."""

    id: UUID
    task_id: UUID | None = None
    full_batch_size: int | None = Field(default=None, ge=1, le=500)
    mode: SyncMode
    status: SyncStatus
    phase: SyncPhase
    generation: int
    window_start: datetime | None
    window_end: datetime
    cursor: str | None
    counters: dict[str, int] = Field(default_factory=dict)
    attempts: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    heartbeat_at: datetime | None
    completed_at: datetime | None
    retry_at: datetime | None = None
    source: Literal["window", "stream", "mixed", "full"] = "window"
    progress: SyncProgress = Field(default_factory=lambda: SyncProgress(phase="queued"))


class SyncCoordinatorStatus(BaseModel):
    """Current run, queued follow-up, and latest terminal outcomes."""

    active: SyncRunStatus | None
    pending: SyncRunStatus | None
    last_success: SyncRunStatus | None
    last_failure: SyncRunStatus | None = None
    successful_watermark: datetime | None
    authoritative_generation: int
    capabilities: SyncCapabilities = Field(default_factory=SyncCapabilities)

"""Public and internal contracts for staged synchronization."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SyncMode = Literal["incremental", "full"]
SyncStatus = Literal["queued", "running", "completed", "failed", "recovering"]
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


class SyncRunStatus(BaseModel):
    """Reload-safe progress for one durable sync run."""

    id: UUID
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


class SyncCoordinatorStatus(BaseModel):
    """Current run, queued follow-up, and last successful checkpoint."""

    active: SyncRunStatus | None
    pending: SyncRunStatus | None
    last_success: SyncRunStatus | None
    successful_watermark: datetime | None
    authoritative_generation: int

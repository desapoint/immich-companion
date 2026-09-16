"""V2-owned typed contracts for durable task coordination."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

TaskStatus = Literal[
    "queued",
    "running",
    "retrying",
    "recovering",
    "pause_requested",
    "paused",
    "cancel_requested",
    "cancelled",
    "completed",
    "failed",
]


class TaskResult(BaseModel):
    status: Literal["completed", "failed"] = "completed"
    summary: dict[str, Any] = Field(default_factory=dict)
    counters: dict[str, int] = Field(default_factory=dict)


class TaskRetry(BaseModel):
    retryable: bool
    next_attempt_at: datetime | None = None
    reason: str | None = None


class TaskEvent(BaseModel):
    id: UUID
    task_id: UUID
    attempt: int
    kind: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TaskStatusView(BaseModel):
    """Frontend-facing durable V2 task snapshot."""

    id: UUID
    task_type: str
    status: TaskStatus
    priority: int
    deduplication_key: str | None
    lane_key: str
    payload: dict[str, Any]
    checkpoint: dict[str, Any]
    counters: dict[str, int]
    progress: dict[str, Any]
    result: TaskResult | None
    error: dict[str, Any] | None
    attempt: int
    next_attempt_at: datetime | None
    lease_owner: UUID | None
    lease_expires_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    heartbeat_at: datetime | None
    completed_at: datetime | None


class TaskScheduleView(BaseModel):
    id: UUID
    name: str
    enabled: bool
    interval_seconds: int
    cron_expression: str | None = None
    deduplication_policy: str = "window"
    blocked_by: list[str] = Field(default_factory=list)
    next_run_at: datetime
    task_type: str
    payload: dict[str, Any]
    priority: int


class TaskScheduleUpdate(BaseModel):
    enabled: bool
    cron_expression: str = Field(min_length=1, max_length=128)

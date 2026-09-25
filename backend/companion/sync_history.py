"""Durable synchronization history and performance projections."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select

from companion.database import DatabaseManager
from companion.models import TaskEventRecord, TaskRecord
from companion.sync_settings import SyncRuntimeSettings
from companion.sync_telemetry import SYNC_PHASES, TELEMETRY_PREFIX, telemetry_key

SyncHistoryMode = Literal["all", "full", "incremental"]


class SyncPhaseTelemetry(BaseModel):
    phase: str
    duration_seconds: float
    processed_items: int
    api_requests: int
    api_retries: int
    rate_limits: int
    wait_seconds: float
    checkpoints: int
    counters: dict[str, int] = Field(default_factory=dict)


class SyncHistoryItem(BaseModel):
    id: UUID
    mode: Literal["full", "incremental"]
    status: str
    generation: int
    attempts: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    queue_seconds: float | None
    duration_seconds: float | None
    throughput_per_second: float | None
    api_requests: int
    api_retries: int
    rate_limits: int
    wait_seconds: float
    checkpoints: int
    counters: dict[str, int] = Field(default_factory=dict)
    settings: SyncRuntimeSettings | None = None
    phases: list[SyncPhaseTelemetry] = Field(default_factory=list)
    error: str | None = None
    telemetry_available: bool = False


class SyncHistoryPage(BaseModel):
    items: list[SyncHistoryItem]
    total: int
    offset: int
    limit: int


def _integer_counters(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, int) and not isinstance(item, bool)
    }


def _visible_counters(counters: dict[str, int]) -> dict[str, int]:
    return {key: value for key, value in counters.items() if not key.startswith(TELEMETRY_PREFIX)}


def _nonnegative_integer(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _metric(counters: dict[str, int], scope: str, metric: str) -> int:
    return max(0, counters.get(telemetry_key(scope, metric), 0))


def _processed_for_phase(phase: str, counters: dict[str, int]) -> int:
    if phase == "catalogs":
        return counters.get("albums_seen", 0) + counters.get("tags_seen", 0)
    if phase == "assets":
        return counters.get("assets_seen", 0)
    if phase == "stacks":
        return counters.get("stacks_seen", 0)
    if phase == "relationships":
        return counters.get("album_memberships", 0) + counters.get("tag_memberships", 0)
    if phase == "finalizing":
        return sum(value for key, value in counters.items() if key.endswith("_removed"))
    return 0


def _event_phase(event: TaskEventRecord) -> str | None:
    details = event.details or {}
    checkpoint = details.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return None
    phase = checkpoint.get("phase") or checkpoint.get("step")
    return str(phase) if phase in SYNC_PHASES else None


def _fallback_phase_durations(
    record: TaskRecord, events: list[TaskEventRecord], now: datetime
) -> dict[str, float]:
    durations: dict[str, float] = defaultdict(float)
    current_phase: str | None = None
    current_started = record.started_at or record.created_at
    for event in events:
        phase = _event_phase(event)
        if phase is None:
            continue
        if current_phase is None:
            current_phase = phase
            current_started = record.started_at or event.created_at
        elif phase != current_phase:
            durations[current_phase] += max(
                0.0, (event.created_at - current_started).total_seconds()
            )
            current_phase = phase
            current_started = event.created_at
    if current_phase is not None:
        end = record.completed_at or record.heartbeat_at or now
        durations[current_phase] += max(0.0, (end - current_started).total_seconds())
    return durations


def _phase_counter_deltas(events: list[TaskEventRecord]) -> dict[str, dict[str, int]]:
    baselines: dict[str, dict[str, int]] = {}
    latest: dict[str, dict[str, int]] = {}
    previous: dict[str, int] = {}
    for event in events:
        phase = _event_phase(event)
        if phase is None:
            continue
        counters = _visible_counters(_integer_counters((event.details or {}).get("counters")))
        if not counters:
            continue
        baselines.setdefault(phase, dict(previous))
        latest[phase] = counters
        previous = counters
    return {
        phase: {
            key: value - baselines[phase].get(key, 0)
            for key, value in values.items()
            if value - baselines[phase].get(key, 0) > 0
        }
        for phase, values in latest.items()
    }


def build_sync_history_item(
    record: TaskRecord,
    events: list[TaskEventRecord],
    *,
    now: datetime | None = None,
) -> SyncHistoryItem:
    now = now or datetime.now(UTC)
    result = record.result or {}
    result_counters = _integer_counters(result.get("counters"))
    counters = result_counters or _integer_counters(record.counters)
    visible_counters = _visible_counters(counters)
    raw_settings = (record.payload or {}).get("runtime_settings")
    settings = None
    if isinstance(raw_settings, dict):
        try:
            settings = SyncRuntimeSettings.model_validate(raw_settings)
        except ValidationError:
            # Historical task payloads must never make the complete history unavailable.
            settings = None
    mode = "full" if (record.payload or {}).get("mode") == "full" else "incremental"
    end = record.completed_at or (now if record.started_at is not None else record.heartbeat_at)
    duration_seconds = (
        max(0.0, (end - record.started_at).total_seconds())
        if record.started_at is not None and end is not None
        else None
    )
    queue_seconds = (
        max(0.0, (record.started_at - record.created_at).total_seconds())
        if record.started_at is not None
        else None
    )
    fallback_durations = _fallback_phase_durations(record, events, now)
    phase_deltas = _phase_counter_deltas(events)
    phases = [
        SyncPhaseTelemetry(
            phase=phase,
            duration_seconds=round(
                _metric(counters, phase, "duration_ms") / 1000
                or fallback_durations.get(phase, 0.0),
                3,
            ),
            processed_items=_processed_for_phase(phase, visible_counters),
            api_requests=_metric(counters, phase, "api_requests"),
            api_retries=_metric(counters, phase, "api_retries"),
            rate_limits=_metric(counters, phase, "rate_limits"),
            wait_seconds=round(_metric(counters, phase, "wait_ms") / 1000, 3),
            checkpoints=_metric(counters, phase, "checkpoints"),
            counters=phase_deltas.get(phase, {}),
        )
        for phase in SYNC_PHASES
    ]
    error = record.error or {}
    assets_seen = visible_counters.get("assets_seen", 0)
    return SyncHistoryItem(
        id=record.id,
        mode=mode,
        status=record.status,
        generation=_nonnegative_integer((record.payload or {}).get("generation")),
        attempts=_nonnegative_integer(record.attempt),
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        queue_seconds=round(queue_seconds, 3) if queue_seconds is not None else None,
        duration_seconds=round(duration_seconds, 3) if duration_seconds is not None else None,
        throughput_per_second=(
            round(assets_seen / duration_seconds, 2)
            if duration_seconds is not None and duration_seconds > 0
            else None
        ),
        api_requests=_metric(counters, "global", "api_requests"),
        api_retries=_metric(counters, "global", "api_retries"),
        rate_limits=_metric(counters, "global", "rate_limits"),
        wait_seconds=round(_metric(counters, "global", "wait_ms") / 1000, 3),
        checkpoints=_metric(counters, "global", "checkpoints"),
        counters=visible_counters,
        settings=settings,
        phases=phases,
        error=str(error.get("message") or error.get("type")) if error else None,
        telemetry_available=any(key.startswith(TELEMETRY_PREFIX) for key in counters),
    )


class SyncHistoryRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def list(
        self,
        *,
        mode: SyncHistoryMode = "all",
        offset: int = 0,
        limit: int = 25,
    ) -> SyncHistoryPage:
        filters = [TaskRecord.task_type == "asset_sync"]
        if mode != "all":
            filters.append(TaskRecord.payload["mode"].as_string() == mode)
        async with self._database.sessions() as session:
            total = int(
                await session.scalar(select(func.count(TaskRecord.id)).where(*filters)) or 0
            )
            records = list(
                (
                    await session.scalars(
                        select(TaskRecord)
                        .where(*filters)
                        .order_by(TaskRecord.created_at.desc(), TaskRecord.id.desc())
                        .offset(offset)
                        .limit(limit)
                    )
                ).all()
            )
            task_ids = [record.id for record in records]
            events = (
                list(
                    (
                        await session.scalars(
                            select(TaskEventRecord)
                            .where(TaskEventRecord.task_id.in_(task_ids))
                            .order_by(TaskEventRecord.created_at, TaskEventRecord.id)
                        )
                    ).all()
                )
                if task_ids
                else []
            )
        events_by_task: dict[UUID, list[TaskEventRecord]] = defaultdict(list)
        for event in events:
            events_by_task[event.task_id].append(event)
        return SyncHistoryPage(
            items=[
                build_sync_history_item(record, events_by_task[record.id]) for record in records
            ],
            total=total,
            offset=offset,
            limit=limit,
        )

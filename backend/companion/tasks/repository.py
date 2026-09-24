"""PostgreSQL persistence for durable tasks, attempts, events, and schedules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from croniter import croniter
from sqlalchemy import delete, func, select, text

from companion.database import DatabaseManager
from companion.models import (
    TaskAttemptRecord,
    TaskEventRecord,
    TaskLaneRecord,
    TaskRecord,
    TaskScheduleRecord,
)
from companion.tasks.contracts import (
    TaskErrorEvent,
    TaskEvent,
    TaskResult,
    TaskScheduleView,
    TaskStatusView,
)
from companion.tasks.errors import (
    TaskAlreadyActiveError,
    TaskCancelledError,
    TaskLeaseLostError,
)

TASK_UPDATE_CHANNEL = "companion_task_updates"

def _public(record: TaskRecord | None) -> TaskStatusView | None:
    if record is None:
        return None
    return TaskStatusView(
        id=record.id,
        task_type=record.task_type,
        status=record.status,
        priority=record.priority,
        deduplication_key=record.deduplication_key,
        lane_key=record.lane_key,
        payload=record.payload or {},
        checkpoint=record.checkpoint or {},
        counters={
            str(key): int(value)
            for key, value in (record.counters or {}).items()
            if isinstance(value, int)
        },
        progress=record.progress or {},
        result=TaskResult.model_validate(record.result) if record.result else None,
        error=record.error,
        attempt=record.attempt,
        next_attempt_at=record.next_attempt_at,
        lease_owner=record.lease_owner,
        lease_expires_at=record.lease_expires_at,
        created_at=record.created_at,
        started_at=record.started_at,
        heartbeat_at=record.heartbeat_at,
        completed_at=record.completed_at,
    )


def _public_schedule(record: TaskScheduleRecord) -> TaskScheduleView:
    return TaskScheduleView(
        id=record.id,
        name=record.name,
        enabled=record.enabled,
        interval_seconds=record.interval_seconds,
        cron_expression=record.cron_expression,
        deduplication_policy=record.deduplication_policy,
        blocked_by=record.blocked_by or [],
        next_run_at=record.next_run_at,
        last_run_at=record.last_run_at,
        task_type=record.task_type,
        payload=record.payload or {},
        priority=record.priority,
    )


def _public_event(record: TaskEventRecord) -> TaskEvent:
    return TaskEvent(
        id=record.id,
        task_id=record.task_id,
        attempt=record.attempt,
        kind=record.kind,
        details=record.details or {},
        created_at=record.created_at,
    )


def _shutdown_release_state(status: str) -> tuple[str, str, str, bool]:
    """Map an owned active task to its durable shutdown state."""

    if status == "cancel_requested":
        return "cancelled", "cancelled", "cancelled", False
    if status == "pause_requested":
        return "paused", "paused", "paused", False
    return "recovering", "failed", "recovering", True


class TaskRepository:
    """Atomic persistence boundary for tasks and their execution history."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def control_state(self, task_id: UUID, worker_id: UUID) -> str:
        async with self._database.sessions() as session:
            record = await session.get(TaskRecord, task_id)
            if record is None or record.lease_owner != worker_id:
                raise TaskLeaseLostError("The task lease is no longer owned")
            return record.status

    async def request_pause(self, task_id: UUID) -> TaskStatusView | None:
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None:
                return None
            if record.status in ("queued", "retrying") or (
                record.status == "recovering"
                and (record.lease_expires_at is None or record.lease_expires_at <= now)
            ):
                record.status = "paused"
                record.lease_owner = None
                record.lease_expires_at = None
                record.next_attempt_at = None
            elif record.status in ("running", "recovering"):
                record.status = "pause_requested"
            else:
                return _public(record)
            session.add(
                TaskEventRecord(
                    task_id=task_id,
                    attempt=record.attempt,
                    kind="pause_requested",
                    details={},
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
            )
            return _public(record)

    async def mark_paused(self, task_id: UUID, worker_id: UUID) -> TaskStatusView:
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None or record.lease_owner != worker_id:
                raise TaskLeaseLostError("The task lease is no longer owned")
            if record.status != "pause_requested":
                raise TaskLeaseLostError("The task is no longer awaiting pause")
            record.status = "paused"
            record.lease_owner = None
            record.lease_expires_at = None
            record.next_attempt_at = None
            attempt = await session.scalar(
                select(TaskAttemptRecord)
                .where(
                    TaskAttemptRecord.task_id == task_id,
                    TaskAttemptRecord.attempt == record.attempt,
                )
                .with_for_update()
            )
            if attempt is not None:
                attempt.status = "paused"
                attempt.completed_at = now
            session.add(
                TaskEventRecord(
                    task_id=task_id,
                    attempt=record.attempt,
                    kind="paused",
                    details={"checkpoint": record.checkpoint or {}},
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
            )
            return _public(record)  # type: ignore[return-value]

    async def resume(self, task_id: UUID) -> TaskStatusView | None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None:
                return None
            if record.status != "paused":
                return _public(record)
            record.status = "recovering"
            record.next_attempt_at = datetime.now(UTC)
            record.completed_at = None
            record.error = None
            session.add(
                TaskEventRecord(
                    task_id=task_id,
                    attempt=record.attempt,
                    kind="resumed",
                    details={"checkpoint": record.checkpoint or {}},
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
            )
            return _public(record)

    async def submit(
        self,
        task_type: str,
        payload: dict[str, Any],
        *,
        priority: int,
        deduplication_key: str | None,
        lane_key: str,
        max_concurrency: int,
        task_id: UUID | None = None,
        schedule_name: str | None = None,
    ) -> TaskStatusView:
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            lane = await session.scalar(
                select(TaskLaneRecord).where(TaskLaneRecord.lane_key == lane_key).with_for_update()
            )
            if lane is None:
                lane = TaskLaneRecord(lane_key=lane_key, max_concurrency=max_concurrency)
                session.add(lane)
            else:
                lane.max_concurrency = max(lane.max_concurrency, max_concurrency)
            if deduplication_key is not None:
                # Serialize submissions for the same key across replicas. The
                # lane lock alone cannot prevent two concurrent inserts.
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:dedupe_key))"),
                    {"dedupe_key": f"{task_type}:{deduplication_key}"},
                )
                existing = await session.scalar(
                    select(TaskRecord)
                    .where(
                        TaskRecord.task_type == task_type,
                        TaskRecord.deduplication_key == deduplication_key,
                        TaskRecord.status.in_(
                            (
                                "queued",
                                "running",
                                "retrying",
                                "recovering",
                                "pause_requested",
                                "paused",
                                "cancel_requested",
                            )
                        ),
                    )
                    .with_for_update()
                )
                if existing is not None:
                    if schedule_name is not None:
                        raise TaskAlreadyActiveError(
                            f"Active task already owns {deduplication_key}"
                        )
                    return _public(existing)  # type: ignore[return-value]
            record = TaskRecord(
                id=task_id or uuid4(),
                task_type=task_type,
                payload=dict(payload),
                priority=priority,
                status="queued",
                deduplication_key=deduplication_key,
                schedule_name=schedule_name,
                lane_key=lane_key,
                checkpoint={},
                counters={},
                progress={},
                next_attempt_at=now,
            )
            session.add(record)
            await session.flush()
            return _public(record)  # type: ignore[return-value]

    async def claim(self, worker_id: UUID, *, lease_duration: timedelta) -> TaskStatusView | None:
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            orphaned_requests = list(
                (
                    await session.scalars(
                        select(TaskRecord)
                        .where(
                            TaskRecord.status.in_(("pause_requested", "cancel_requested")),
                            (TaskRecord.lease_expires_at.is_(None))
                            | (TaskRecord.lease_expires_at <= now),
                        )
                        .with_for_update(skip_locked=True)
                        .limit(32)
                    )
                ).all()
            )
            for record in orphaned_requests:
                previous_status = record.status
                target_status, attempt_status, event_kind, _resumable = (
                    _shutdown_release_state(previous_status)
                )
                record.status = target_status
                record.lease_owner = None
                record.lease_expires_at = None
                record.next_attempt_at = None
                record.completed_at = now if target_status == "cancelled" else None
                if target_status == "cancelled":
                    record.error = None
                attempt = await session.scalar(
                    select(TaskAttemptRecord)
                    .where(
                        TaskAttemptRecord.task_id == record.id,
                        TaskAttemptRecord.attempt == record.attempt,
                        TaskAttemptRecord.status == "running",
                    )
                    .with_for_update()
                )
                if attempt is not None:
                    attempt.status = attempt_status
                    attempt.completed_at = now
                    attempt.details = {
                        "type": "worker_lease_expired",
                        "message": f"Recovered orphaned {previous_status} control request",
                    }
                session.add(
                    TaskEventRecord(
                        task_id=record.id,
                        attempt=record.attempt,
                        kind=event_kind,
                        details={"reason": "worker_lease_expired"},
                    )
                )
                await session.execute(
                    text("SELECT pg_notify(:channel, :payload)"),
                    {"channel": TASK_UPDATE_CHANNEL, "payload": str(record.id)},
                )

            candidates = await session.scalars(
                select(TaskRecord)
                .where(
                    # A process can disappear while a task is running. Once its
                    # lease expires, reclaim it and resume from its checkpoint.
                    TaskRecord.status.in_(
                        ("queued", "running", "retrying", "recovering")
                    ),
                    (TaskRecord.next_attempt_at.is_(None)) | (TaskRecord.next_attempt_at <= now),
                    (TaskRecord.lease_expires_at.is_(None)) | (TaskRecord.lease_expires_at <= now),
                )
                .order_by(TaskRecord.priority.desc(), TaskRecord.created_at)
                .with_for_update(skip_locked=True)
                .limit(32)
            )
            for record in candidates:
                lane = await session.scalar(
                    select(TaskLaneRecord)
                    .where(TaskLaneRecord.lane_key == record.lane_key)
                    .with_for_update()
                )
                if lane is None:
                    lane = TaskLaneRecord(lane_key=record.lane_key, max_concurrency=1)
                    session.add(lane)
                    await session.flush()
                active = await session.scalar(
                    select(func.count(TaskRecord.id)).where(
                        TaskRecord.lane_key == record.lane_key,
                        TaskRecord.status.in_(
                            ("running", "recovering", "pause_requested", "cancel_requested")
                        ),
                        TaskRecord.lease_expires_at > now,
                    )
                )
                if int(active or 0) >= lane.max_concurrency:
                    continue
                recovering = record.status in ("running", "recovering")
                record.status = "recovering" if recovering else "running"
                record.lease_owner = worker_id
                record.lease_expires_at = now + lease_duration
                first_start = record.started_at is None
                record.started_at = record.started_at or now
                record.heartbeat_at = now
                record.attempt += 1
                if first_start and record.schedule_name is not None:
                    schedule = await session.scalar(
                        select(TaskScheduleRecord)
                        .where(TaskScheduleRecord.name == record.schedule_name)
                        .with_for_update()
                    )
                    if schedule is not None:
                        schedule.last_run_at = now
                attempt = TaskAttemptRecord(
                    task_id=record.id,
                    attempt=record.attempt,
                    worker_id=worker_id,
                    status="running",
                    details={"recovered": recovering},
                )
                session.add(attempt)
                await session.flush()
                return _public(record)
            return None

    async def heartbeat(self, task_id: UUID, worker_id: UUID, *, lease_duration: timedelta) -> None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None or record.lease_owner != worker_id or record.lease_expires_at is None:
                raise TaskLeaseLostError("The task lease is no longer owned")
            now = datetime.now(UTC)
            record.lease_expires_at = now + lease_duration
            record.heartbeat_at = now

    async def update_payload(
        self, task_id: UUID, worker_id: UUID, payload: dict[str, Any]
    ) -> None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None or record.lease_owner != worker_id:
                raise TaskLeaseLostError("The task lease is no longer owned")
            record.payload = dict(payload)

    async def checkpoint(
        self,
        task_id: UUID,
        worker_id: UUID,
        *,
        checkpoint: dict[str, Any],
        counters: dict[str, int],
        progress: dict[str, Any],
        lease_duration: timedelta,
    ) -> None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None or record.lease_owner != worker_id:
                raise TaskLeaseLostError("The task lease is no longer owned")
            if record.status == "cancel_requested":
                raise TaskCancelledError("The task was cancelled")
            now = datetime.now(UTC)
            record.checkpoint = dict(checkpoint)
            record.counters = dict(counters)
            record.progress = dict(progress)
            record.heartbeat_at = now
            record.lease_expires_at = now + lease_duration
            session.add(
                TaskEventRecord(
                    task_id=task_id,
                    attempt=record.attempt,
                    kind="checkpoint",
                    details={"checkpoint": checkpoint, "progress": progress},
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
            )

    async def is_cancelled(self, task_id: UUID, worker_id: UUID) -> bool:
        async with self._database.sessions() as session:
            record = await session.get(TaskRecord, task_id)
            if record is None or record.lease_owner != worker_id:
                raise TaskLeaseLostError("The task lease is no longer owned")
            return record.status == "cancel_requested"

    async def complete(self, task_id: UUID, worker_id: UUID, result: TaskResult) -> TaskStatusView:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None or record.lease_owner != worker_id:
                raise TaskLeaseLostError("The task lease is no longer owned")
            now = datetime.now(UTC)
            record.status = "failed" if result.status == "failed" else "completed"
            record.result = result.model_dump(mode="json")
            if record.status == "completed":
                progress = dict(record.progress or {})
                total = progress.get("total")
                if isinstance(total, (int, float)) and not isinstance(total, bool):
                    progress["completed"] = total
                progress.update(
                    phase="complete",
                    percent=100.0,
                    detail="Complete.",
                )
                record.progress = progress
            record.error = (
                {"type": "task_result", "message": "One or more task items failed"}
                if result.status == "failed"
                else None
            )
            record.completed_at = now
            record.lease_owner = None
            record.lease_expires_at = None
            attempt = await session.scalar(
                select(TaskAttemptRecord)
                .where(
                    TaskAttemptRecord.task_id == task_id,
                    TaskAttemptRecord.attempt == record.attempt,
                )
                .with_for_update()
            )
            if attempt is not None:
                attempt.status = "completed"
                attempt.completed_at = now
                attempt.details = result.model_dump(mode="json")
            session.add(
                TaskEventRecord(
                    task_id=task_id,
                    attempt=record.attempt,
                    kind=record.status,
                    details=result.model_dump(mode="json"),
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
            )
            return _public(record)  # type: ignore[return-value]

    async def fail(
        self,
        task_id: UUID,
        worker_id: UUID,
        error: Exception,
        *,
        retryable: bool,
        next_attempt_at: datetime | None,
        max_attempts: int,
    ) -> TaskStatusView | None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None or record.lease_owner != worker_id:
                return None
            now = datetime.now(UTC)
            should_retry = retryable and record.attempt < max_attempts
            record.status = (
                "cancelled"
                if isinstance(error, TaskCancelledError)
                else "retrying"
                if should_retry
                else "failed"
            )
            record.next_attempt_at = next_attempt_at if should_retry else None
            record.error = {"type": type(error).__name__, "message": str(error)}
            record.completed_at = None if should_retry else now
            record.lease_owner = None
            record.lease_expires_at = None
            attempt = await session.scalar(
                select(TaskAttemptRecord)
                .where(
                    TaskAttemptRecord.task_id == task_id,
                    TaskAttemptRecord.attempt == record.attempt,
                )
                .with_for_update()
            )
            failure_details = {
                **record.error,
                "retryable": retryable,
                "will_retry": should_retry,
                "max_attempts": max_attempts,
            }
            if attempt is not None:
                attempt.status = record.status
                attempt.completed_at = now
                attempt.details = failure_details
            session.add(
                TaskEventRecord(
                    task_id=task_id,
                    attempt=record.attempt,
                    kind="retry" if should_retry else record.status,
                    details=failure_details,
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
            )
            return _public(record)

    async def cancel(self, task_id: UUID) -> TaskStatusView | None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None:
                return None
            if record.status in ("queued", "retrying", "recovering", "paused"):
                record.status = "cancelled"
                record.completed_at = datetime.now(UTC)
            elif record.status in ("running", "pause_requested"):
                record.status = "cancel_requested"
            session.add(
                TaskEventRecord(
                    task_id=task_id, attempt=record.attempt, kind="cancel_requested", details={}
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
            )
            return _public(record)

    async def get(self, task_id: UUID) -> TaskStatusView | None:
        async with self._database.sessions() as session:
            return _public(await session.get(TaskRecord, task_id))

    async def find_active(self, task_type: str, deduplication_key: str) -> TaskStatusView | None:
        """Find one queued or running task for idempotent submission."""

        async with self._database.sessions() as session:
            record = await session.scalar(
                select(TaskRecord)
                .where(
                    TaskRecord.task_type == task_type,
                    TaskRecord.deduplication_key == deduplication_key,
                    TaskRecord.status.in_(
                        (
                            "queued",
                            "running",
                            "retrying",
                            "recovering",
                            "pause_requested",
                            "paused",
                            "cancel_requested",
                        )
                    ),
                )
                .order_by(TaskRecord.created_at)
            )
            return _public(record)

    async def find_active_by_type(self, task_type: str) -> TaskStatusView | None:
        """Return the oldest active task of a type, regardless of request key."""

        async with self._database.sessions() as session:
            record = await session.scalar(
                select(TaskRecord)
                .where(
                    TaskRecord.task_type == task_type,
                    TaskRecord.status.in_(
                        (
                            "queued",
                            "running",
                            "retrying",
                            "recovering",
                            "pause_requested",
                            "paused",
                            "cancel_requested",
                        )
                    ),
                )
                .order_by(TaskRecord.created_at)
                .limit(1)
            )
            return _public(record)

    async def ensure_schedule(
        self,
        *,
        name: str,
        interval_seconds: int,
        task_type: str,
        payload: dict[str, Any],
        priority: int,
        enabled: bool = True,
        cron_expression: str | None = None,
        deduplication_policy: str = "window",
        blocked_by: list[str] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            schedule = await session.scalar(
                select(TaskScheduleRecord).where(TaskScheduleRecord.name == name).with_for_update()
            )
            if schedule is None:
                next_run_at = (
                    croniter(cron_expression, now).get_next(datetime)
                    if cron_expression
                    else now + timedelta(seconds=interval_seconds)
                )
                session.add(
                    TaskScheduleRecord(
                        name=name,
                        enabled=enabled,
                        interval_seconds=interval_seconds,
                        cron_expression=cron_expression,
                        deduplication_policy=deduplication_policy,
                        blocked_by=list(blocked_by or []),
                        next_run_at=next_run_at,
                        task_type=task_type,
                        payload=dict(payload),
                        priority=priority,
                    )
                )
            else:
                schedule.interval_seconds = interval_seconds
                schedule.task_type = task_type
                schedule.payload = dict(payload)
                schedule.priority = priority
                schedule.deduplication_policy = deduplication_policy
                schedule.blocked_by = list(blocked_by or [])

    async def claim_due_schedules(self) -> list[TaskScheduleRecord]:
        now = datetime.now(UTC)
        claimed: list[TaskScheduleRecord] = []
        async with self._database.sessions() as session, session.begin():
            schedules = await session.scalars(
                select(TaskScheduleRecord)
                .where(TaskScheduleRecord.enabled, TaskScheduleRecord.next_run_at <= now)
                .order_by(TaskScheduleRecord.next_run_at)
                .with_for_update(skip_locked=True)
                .limit(16)
            )
            for schedule in schedules:
                while schedule.next_run_at <= now:
                    if schedule.cron_expression:
                        schedule.next_run_at = croniter(
                            schedule.cron_expression, schedule.next_run_at
                        ).get_next(datetime)
                    else:
                        schedule.next_run_at += timedelta(seconds=schedule.interval_seconds)
                claimed.append(schedule)
        return claimed

    async def defer_schedule(self, name: str, *, retry_seconds: int = 60) -> None:
        """Retry a claimed schedule soon when it could not be dispatched."""

        retry_at = datetime.now(UTC) + timedelta(seconds=retry_seconds)
        async with self._database.sessions() as session, session.begin():
            schedule = await session.scalar(
                select(TaskScheduleRecord)
                .where(TaskScheduleRecord.name == name)
                .with_for_update()
            )
            if schedule is not None and schedule.enabled:
                schedule.next_run_at = min(schedule.next_run_at, retry_at)

    async def list_schedules(self) -> list[TaskScheduleView]:
        async with self._database.sessions() as session:
            records = await session.scalars(
                select(TaskScheduleRecord).order_by(TaskScheduleRecord.name)
            )
            return [_public_schedule(record) for record in records]

    async def update_schedule(
        self,
        name: str,
        *,
        enabled: bool,
        cron_expression: str,
    ) -> TaskScheduleView | None:
        croniter(cron_expression)
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskScheduleRecord).where(TaskScheduleRecord.name == name).with_for_update()
            )
            if record is None:
                return None
            record.enabled = enabled
            record.cron_expression = cron_expression
            record.next_run_at = croniter(cron_expression, now).get_next(datetime)
            return _public_schedule(record)

    async def list(
        self, *, task_type: str | None = None, limit: int = 50, active_only: bool = False
    ) -> list[TaskStatusView]:
        async with self._database.sessions() as session:
            statement = select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit)
            if task_type is not None:
                statement = statement.where(TaskRecord.task_type == task_type)
            if active_only:
                statement = statement.where(TaskRecord.status.in_((
                    "queued", "running", "retrying", "recovering",
                    "pause_requested", "paused", "cancel_requested",
                )))
            records = await session.scalars(statement)
            return [_public(record) for record in records if _public(record) is not None]  # type: ignore[misc]

    async def events(self, task_id: UUID, *, limit: int = 1000) -> list[TaskEvent]:
        """Return durable lifecycle/checkpoint history for diagnostics."""

        async with self._database.sessions() as session:
            records = await session.scalars(
                select(TaskEventRecord)
                .where(TaskEventRecord.task_id == task_id)
                .order_by(TaskEventRecord.created_at, TaskEventRecord.id)
                .limit(limit)
            )
            return [_public_event(record) for record in records]

    async def errors(self, *, limit: int = 100) -> list[TaskErrorEvent]:
        """Return newest task failures without exposing task payloads."""

        async with self._database.sessions() as session:
            rows = await session.execute(
                select(TaskEventRecord, TaskRecord.task_type)
                .join(TaskRecord, TaskRecord.id == TaskEventRecord.task_id)
                .where(TaskEventRecord.kind.in_(("retry", "failed")))
                .order_by(TaskEventRecord.created_at.desc(), TaskEventRecord.id.desc())
                .limit(limit)
            )
            errors: list[TaskErrorEvent] = []
            for event, task_type in rows:
                details = event.details or {}
                retryable = details.get("retryable")
                max_attempts = details.get("max_attempts")
                errors.append(
                    TaskErrorEvent(
                        id=event.id,
                        task_id=event.task_id,
                        task_type=task_type,
                        attempt=event.attempt,
                        outcome="retrying" if event.kind == "retry" else "failed",
                        error_type=str(details.get("type") or "UnknownError"),
                        message=str(details.get("message") or "No error message was recorded."),
                        retryable=retryable if isinstance(retryable, bool) else None,
                        will_retry=event.kind == "retry",
                        max_attempts=max_attempts if isinstance(max_attempts, int) else None,
                        occurred_at=event.created_at,
                    )
                )
            return errors

    async def clear_errors(self) -> int:
        """Remove durable retry/failure events while preserving task records."""

        async with self._database.sessions() as session, session.begin():
            result = await session.execute(
                delete(TaskEventRecord).where(TaskEventRecord.kind.in_(("retry", "failed")))
            )
            return int(result.rowcount or 0)

    async def release_worker_leases(self, worker_id: UUID) -> int:
        """Release or finalize every active lease owned by a shutting-down worker."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            records = list(
                (
                    await session.scalars(
                        select(TaskRecord)
                        .where(
                            TaskRecord.lease_owner == worker_id,
                            TaskRecord.status.in_(
                                (
                                    "running",
                                    "recovering",
                                    "pause_requested",
                                    "cancel_requested",
                                )
                            ),
                        )
                        .with_for_update()
                    )
                ).all()
            )
            for record in records:
                previous_status = record.status
                target_status, attempt_status, event_kind, resumable = _shutdown_release_state(
                    previous_status
                )
                record.status = target_status
                record.lease_owner = None
                record.lease_expires_at = None
                record.next_attempt_at = now if resumable else None
                if target_status == "cancelled":
                    record.completed_at = now
                    record.error = {
                        "type": "worker_shutdown_cancelled",
                        "message": "Cancellation completed while the worker was shutting down",
                    }
                attempt = await session.scalar(
                    select(TaskAttemptRecord)
                    .where(
                        TaskAttemptRecord.task_id == record.id,
                        TaskAttemptRecord.attempt == record.attempt,
                        TaskAttemptRecord.status == "running",
                    )
                    .with_for_update()
                )
                if attempt is not None:
                    attempt.status = attempt_status
                    attempt.completed_at = now
                    attempt.details = {
                        "type": "worker_shutdown",
                        "message": (
                            "Worker stopped before task completion"
                            if resumable
                            else f"Worker shutdown completed {previous_status}"
                        ),
                    }
                session.add(
                    TaskEventRecord(
                        task_id=record.id,
                        attempt=record.attempt,
                        kind=event_kind,
                        details={"reason": "worker_shutdown"},
                    )
                )
            return len(records)

    async def cancel_unfinished(self, task_type: str, *, reason: str) -> int:
        """Cancel unfinished tasks of one type before startup workers can reclaim them."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            records = await session.scalars(
                select(TaskRecord)
                .where(
                    TaskRecord.task_type == task_type,
                    TaskRecord.status.in_(
                        (
                            "queued",
                            "running",
                            "retrying",
                            "recovering",
                            "pause_requested",
                            "paused",
                            "cancel_requested",
                        )
                    ),
                )
                .with_for_update()
            )
            cancelled = 0
            for record in records:
                record.status = "cancelled"
                record.completed_at = now
                record.next_attempt_at = None
                record.lease_owner = None
                record.lease_expires_at = None
                record.error = {"type": "startup_cancelled", "message": reason}
                session.add(
                    TaskEventRecord(
                        task_id=record.id,
                        attempt=record.attempt,
                        kind="cancelled",
                        details={"reason": reason, "source": "startup"},
                    )
                )
                cancelled += 1
            return cancelled

"""Reusable PostgreSQL-backed task coordination and worker lifecycle."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select, text

from companion.database import DatabaseManager
from companion.models import (
    TaskAttemptRecord,
    TaskEventRecord,
    TaskLaneRecord,
    TaskRecord,
    TaskScheduleRecord,
)
from companion.task_schema import TaskResult, TaskStatusView


class RetryableTaskError(RuntimeError):
    """A handler failure that should be retried by the same task."""


class PermanentTaskError(RuntimeError):
    """A handler failure that must not be retried."""


class TaskLeaseLostError(RuntimeError):
    """Raised when a worker attempts to mutate a task it no longer owns."""


class TaskCancelledError(RuntimeError):
    """Raised when a handler observes a cancellation request."""


class TaskHandler(Protocol):
    """Protocol implemented by each domain task type."""

    task_type: str
    lane_key: str
    max_concurrency: int

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        """Execute one immutable task payload."""


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


class TaskRepository:
    """Atomic persistence boundary for tasks and their execution history."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

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
                            ("queued", "running", "retrying", "recovering", "cancel_requested")
                        ),
                    )
                    .with_for_update()
                )
                if existing is not None:
                    return _public(existing)  # type: ignore[return-value]
            record = TaskRecord(
                id=task_id or uuid4(),
                task_type=task_type,
                payload=dict(payload),
                priority=priority,
                status="queued",
                deduplication_key=deduplication_key,
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
            candidates = await session.scalars(
                select(TaskRecord)
                .where(
                    TaskRecord.status.in_(("queued", "retrying", "recovering")),
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
                        TaskRecord.status.in_(("running", "recovering", "cancel_requested")),
                        TaskRecord.lease_expires_at > now,
                    )
                )
                if int(active or 0) >= lane.max_concurrency:
                    continue
                recovering = record.status in ("running", "recovering")
                record.status = "recovering" if recovering else "running"
                record.lease_owner = worker_id
                record.lease_expires_at = now + lease_duration
                record.started_at = record.started_at or now
                record.heartbeat_at = now
                record.attempt += 1
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
            record.status = "completed"
            record.result = result.model_dump(mode="json")
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
                    kind="completed",
                    details=result.model_dump(mode="json"),
                )
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
            if attempt is not None:
                attempt.status = record.status
                attempt.completed_at = now
                attempt.details = record.error
            session.add(
                TaskEventRecord(
                    task_id=task_id,
                    attempt=record.attempt,
                    kind="retry" if should_retry else record.status,
                    details=record.error,
                )
            )
            return _public(record)

    async def cancel(self, task_id: UUID) -> TaskStatusView | None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
            )
            if record is None:
                return None
            if record.status in ("queued", "retrying", "recovering"):
                record.status = "cancelled"
                record.completed_at = datetime.now(UTC)
            elif record.status == "running":
                record.status = "cancel_requested"
            session.add(
                TaskEventRecord(
                    task_id=task_id, attempt=record.attempt, kind="cancel_requested", details={}
                )
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
                        ("queued", "running", "retrying", "recovering", "cancel_requested")
                    ),
                )
                .order_by(TaskRecord.created_at)
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
    ) -> None:
        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            schedule = await session.scalar(
                select(TaskScheduleRecord).where(TaskScheduleRecord.name == name).with_for_update()
            )
            if schedule is None:
                session.add(
                    TaskScheduleRecord(
                        name=name,
                        enabled=True,
                        interval_seconds=interval_seconds,
                        next_run_at=now + timedelta(seconds=interval_seconds),
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
                    schedule.next_run_at += timedelta(seconds=schedule.interval_seconds)
                claimed.append(schedule)
            return claimed

    async def list(self, *, task_type: str | None = None, limit: int = 50) -> list[TaskStatusView]:
        async with self._database.sessions() as session:
            statement = select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit)
            if task_type is not None:
                statement = statement.where(TaskRecord.task_type == task_type)
            records = await session.scalars(statement)
            return [_public(record) for record in records if _public(record) is not None]  # type: ignore[misc]


class TaskContext:
    """Lease-bound handler context for durable progress and cancellation."""

    def __init__(
        self,
        repository: TaskRepository,
        task: TaskStatusView,
        worker_id: UUID,
        lease_duration: timedelta,
    ) -> None:
        self._repository = repository
        self.task = task
        self.worker_id = worker_id
        self._lease_duration = lease_duration

    async def checkpoint(
        self, *, checkpoint: dict[str, Any], counters: dict[str, int], progress: dict[str, Any]
    ) -> None:
        await self._repository.checkpoint(
            self.task.id,
            self.worker_id,
            checkpoint=checkpoint,
            counters=counters,
            progress=progress,
            lease_duration=self._lease_duration,
        )

    async def heartbeat(self) -> None:
        await self._repository.heartbeat(
            self.task.id, self.worker_id, lease_duration=self._lease_duration
        )

    async def update_payload(self, payload: dict[str, Any]) -> None:
        """Persist handler-resolved payload fields used for status and recovery."""

        await self._repository.update_payload(self.task.id, self.worker_id, payload)
        self.task.payload = dict(payload)

    async def ensure_active(self) -> None:
        if await self._repository.is_cancelled(self.task.id, self.worker_id):
            raise TaskCancelledError("The task was cancelled")


class TaskCoordinator:
    """Register handlers and execute durable tasks with independent lanes."""

    def __init__(
        self,
        database: DatabaseManager,
        *,
        lease_seconds: int = 60,
        max_attempts: int = 5,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._repository = TaskRepository(database)
        self._lease_duration = timedelta(seconds=lease_seconds)
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._handlers: dict[str, TaskHandler] = {}
        self._worker: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._running: set[asyncio.Task[None]] = set()
        self._schedule_definitions: list[dict[str, Any]] = []

    def register_handler(self, handler: TaskHandler) -> None:
        self._handlers[handler.task_type] = handler

    def register_schedule(
        self,
        *,
        name: str,
        interval_seconds: int,
        task_type: str,
        payload: dict[str, Any],
        priority: int = 0,
    ) -> None:
        self._schedule_definitions.append(
            {
                "name": name,
                "interval_seconds": interval_seconds,
                "task_type": task_type,
                "payload": dict(payload),
                "priority": priority,
            }
        )

    async def submit(
        self,
        task_type: str,
        payload: dict[str, Any],
        *,
        priority: int = 0,
        deduplication_key: str | None = None,
        lane_key: str | None = None,
        max_concurrency: int | None = None,
        task_id: UUID | None = None,
    ) -> TaskStatusView:
        handler = self._handlers.get(task_type)
        if handler is None:
            raise ValueError(f"No handler registered for task type {task_type}")
        return await self._repository.submit(
            task_type,
            payload,
            priority=priority,
            deduplication_key=deduplication_key,
            lane_key=lane_key or handler.lane_key,
            max_concurrency=max_concurrency or handler.max_concurrency,
            task_id=task_id,
        )

    async def get_status(self, task_id: UUID) -> TaskStatusView | None:
        return await self._repository.get(task_id)

    async def list_tasks(
        self, *, task_type: str | None = None, limit: int = 50
    ) -> list[TaskStatusView]:
        return await self._repository.list(task_type=task_type, limit=limit)

    async def cancel(self, task_id: UUID) -> TaskStatusView | None:
        return await self._repository.cancel(task_id)

    async def wait(self, task_id: UUID, *, poll_seconds: float = 0.25) -> TaskStatusView:
        while True:
            task = await self.get_status(task_id)
            if task is None:
                raise ValueError("The task was not found")
            if task.status in ("completed", "failed", "cancelled"):
                return task
            await asyncio.sleep(poll_seconds)

    async def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._stopping.clear()
            for definition in self._schedule_definitions:
                await self._repository.ensure_schedule(**definition)
            self._worker = asyncio.create_task(self._run(), name="task-coordinator-worker")

    async def stop(self) -> None:
        self._stopping.set()
        if self._worker is not None and not self._worker.done():
            self._worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker
        if self._running:
            await asyncio.gather(*self._running, return_exceptions=True)

    async def _run(self) -> None:
        worker_id = uuid4()
        scheduler = asyncio.create_task(self._schedule(), name="task-coordinator-scheduler")
        try:
            while not self._stopping.is_set():
                if len(self._running) >= 16:
                    done, pending = await asyncio.wait(
                        self._running, return_when=asyncio.FIRST_COMPLETED
                    )
                    self._running = set(pending)
                    for task in done:
                        task.result()
                    continue
                task = await self._repository.claim(worker_id, lease_duration=self._lease_duration)
                if task is None:
                    await asyncio.sleep(0.25)
                    continue
                execution = asyncio.create_task(
                    self._execute(task, worker_id), name=f"task-{task.id}"
                )
                self._running.add(execution)
                execution.add_done_callback(self._running.discard)
        finally:
            scheduler.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler

    async def _schedule(self) -> None:
        while not self._stopping.is_set():
            for schedule in await self._repository.claim_due_schedules():
                dedupe = f"schedule:{schedule.name}:{schedule.next_run_at.isoformat()}"
                try:
                    await self.submit(
                        schedule.task_type,
                        schedule.payload,
                        priority=schedule.priority,
                        deduplication_key=dedupe,
                    )
                except ValueError:
                    # Handler registration may complete just after startup; the
                    # next schedule tick will retry without taking the worker down.
                    continue
            await asyncio.sleep(1)

    async def _execute(self, task: TaskStatusView, worker_id: UUID) -> None:
        handler = self._handlers.get(task.task_type)
        if handler is None:
            await self._repository.fail(
                task.id,
                worker_id,
                ValueError(f"No handler registered for {task.task_type}"),
                retryable=False,
                next_attempt_at=None,
                max_attempts=self._max_attempts,
            )
            return
        context = TaskContext(self._repository, task, worker_id, self._lease_duration)
        heartbeat = asyncio.create_task(self._heartbeat(context), name=f"heartbeat-{task.id}")
        try:
            result = await handler.execute(context, task.payload)
        except TaskCancelledError as error:
            await self._repository.fail(
                task.id,
                worker_id,
                error,
                retryable=False,
                next_attempt_at=None,
                max_attempts=self._max_attempts,
            )
        except RetryableTaskError as error:
            delay = min(self._retry_backoff_seconds * 2 ** max(0, task.attempt - 1), 300)
            await self._repository.fail(
                task.id,
                worker_id,
                error,
                retryable=True,
                next_attempt_at=datetime.now(UTC) + timedelta(seconds=delay),
                max_attempts=self._max_attempts,
            )
        except PermanentTaskError as error:
            await self._repository.fail(
                task.id,
                worker_id,
                error,
                retryable=False,
                next_attempt_at=None,
                max_attempts=self._max_attempts,
            )
        except Exception as error:
            delay = min(self._retry_backoff_seconds * 2 ** max(0, task.attempt - 1), 300)
            await self._repository.fail(
                task.id,
                worker_id,
                error,
                retryable=True,
                next_attempt_at=datetime.now(UTC) + timedelta(seconds=delay),
                max_attempts=self._max_attempts,
            )
        else:
            await self._repository.complete(task.id, worker_id, result)
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    async def _heartbeat(self, context: TaskContext) -> None:
        interval = max(1.0, self._lease_duration.total_seconds() / 3)
        while True:
            await asyncio.sleep(interval)
            await context.heartbeat()

"""V2-owned task coordinator facade.

V2 reuses the proven durable PostgreSQL repository, leases, retries and LISTEN/NOTIFY
transport, but owns the handler execution boundary and checkpoint contract. This keeps the
frontend status behavior compatible while allowing V2 sync semantics to evolve without
editing the preserved coordinator implementation.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text

from companion.database import DatabaseManager
from companion.models import TaskAttemptRecord, TaskEventRecord, TaskRecord
from companion.v2.legacy_task_coordinator import (
    TASK_UPDATE_CHANNEL,
    PermanentTaskError,
    RetryableTaskError,
    TaskCancelledError,
    TaskHandler,
    TaskLeaseLostError,
    _public,
)
from companion.v2.legacy_task_coordinator import TaskContext as _TaskContext
from companion.v2.legacy_task_coordinator import TaskCoordinator as _TaskCoordinator
from companion.v2.legacy_task_coordinator import TaskRepository as _TaskRepository
from companion.v2.task_schema import TaskStatusView


class TaskPausedError(RuntimeError):
    """Raised when a handler reaches a safe boundary after pause was requested."""


class TaskRepository(_TaskRepository):
    """Add cooperative pause/resume transitions to the durable task repository."""

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


class TaskContext(_TaskContext):
    """V2 task context with one standard sync-step checkpoint contract."""

    async def checkpoint(self, **values) -> None:
        await super().checkpoint(**values)
        await self.ensure_active()

    async def ensure_active(self) -> None:
        state = await self._repository.control_state(self.task.id, self.worker_id)
        if state == "cancel_requested":
            raise TaskCancelledError("The task was cancelled")
        if state == "pause_requested":
            raise TaskPausedError("The task was paused")

    async def checkpoint_sync_step(
        self,
        *,
        step: str,
        cursor: str | None,
        counters: dict[str, int],
        completed: int,
        total: int | None,
        detail: str | None = None,
    ) -> None:
        percent = (
            round(min(100.0, max(0, completed) / total * 100), 1)
            if total is not None and total > 0
            else None
        )
        await self.checkpoint(
            checkpoint={"step": step, "phase": step, "cursor": cursor},
            counters=counters,
            progress={
                "phase": step,
                "step": step,
                "completed": max(0, completed),
                "total": total,
                "percent": percent,
                "detail": detail,
            },
        )


class TaskCoordinator(_TaskCoordinator):
    """V2 coordinator using the existing durable transport with a V2 context."""

    def __init__(
        self,
        database: DatabaseManager,
        *,
        lease_seconds: int = 60,
        max_attempts: int = 5,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        super().__init__(
            database,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        self._repository = TaskRepository(database)

    async def _execute(self, task: TaskStatusView, worker_id) -> None:
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

        context = TaskContext(
            self._repository,
            task,
            worker_id,
            self._lease_duration,
            notify=lambda: self._publish(task.id),
        )
        heartbeat = asyncio.create_task(self._heartbeat(context), name=f"heartbeat-{task.id}")
        try:
            result = await handler.execute(context, task.payload)
        except TaskPausedError:
            await self._repository.mark_paused(task.id, worker_id)
            await self._publish(task.id)
        except TaskCancelledError as error:
            await self._repository.fail(
                task.id,
                worker_id,
                error,
                retryable=False,
                next_attempt_at=None,
                max_attempts=self._max_attempts,
            )
            await self._publish(task.id)
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
            await self._publish(task.id)
        except PermanentTaskError as error:
            await self._repository.fail(
                task.id,
                worker_id,
                error,
                retryable=False,
                next_attempt_at=None,
                max_attempts=self._max_attempts,
            )
            await self._publish(task.id)
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
            await self._publish(task.id)
        else:
            await self._repository.complete(task.id, worker_id, result)
            await self._publish(task.id)
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    async def pause(self, task_id: UUID) -> TaskStatusView | None:
        current = await self.get_status(task_id)
        if current is None:
            return None
        handler = self._handlers.get(current.task_type)
        if handler is None or not getattr(handler, "supports_pause", False):
            raise ValueError(f"Task type {current.task_type} does not support pausing")
        task = await self._repository.request_pause(task_id)
        if task is not None:
            await self._publish(task_id)
        return task

    async def resume(self, task_id: UUID) -> TaskStatusView | None:
        current = await self.get_status(task_id)
        if current is None:
            return None
        handler = self._handlers.get(current.task_type)
        if handler is None or not getattr(handler, "supports_pause", False):
            raise ValueError(f"Task type {current.task_type} does not support resuming")
        task = await self._repository.resume(task_id)
        if task is not None:
            await self._publish(task_id)
        return task


__all__ = [
    "PermanentTaskError",
    "RetryableTaskError",
    "TaskCancelledError",
    "TaskPausedError",
    "TaskContext",
    "TaskCoordinator",
    "TaskHandler",
    "TaskLeaseLostError",
    "TaskRepository",
]

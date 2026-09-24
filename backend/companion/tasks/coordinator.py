"""Task execution, scheduling, streaming, and handler lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from companion.database import DatabaseManager
from companion.runtime_metrics import reclaim_process_memory
from companion.tasks.contracts import (
    TaskErrorEvent,
    TaskEvent,
    TaskResult,
    TaskScheduleView,
    TaskStatusView,
)
from companion.tasks.errors import (
    PermanentTaskError,
    RetryableTaskError,
    TaskCancelledError,
    TaskLeaseLostError,
    TaskPausedError,
)
from companion.tasks.repository import TaskRepository
from companion.tasks.scheduling import TaskScheduler
from companion.tasks.streaming import TaskUpdateBroker

logger = logging.getLogger("uvicorn.error")


class TaskHandler(Protocol):
    """Protocol implemented by each domain task type."""

    task_type: str
    lane_key: str
    max_concurrency: int

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        """Execute one immutable task payload."""


class TaskContext:
    """Lease-bound handler context for durable progress and cancellation."""

    def __init__(
        self,
        repository: TaskRepository,
        task: TaskStatusView,
        worker_id: UUID,
        lease_duration: timedelta,
        notify: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self.task = task
        self.worker_id = worker_id
        self._lease_duration = lease_duration
        self._notify = notify

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
        if self._notify is not None:
            await self._notify()
        await self.ensure_active()

    async def heartbeat(self) -> None:
        await self._repository.heartbeat(
            self.task.id, self.worker_id, lease_duration=self._lease_duration
        )

    async def update_payload(self, payload: dict[str, Any]) -> None:
        """Persist handler-resolved payload fields used for status and recovery."""

        await self._repository.update_payload(self.task.id, self.worker_id, payload)
        self.task.payload = dict(payload)
        if self._notify is not None:
            await self._notify()

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
        self._scheduler = TaskScheduler()
        self._updates = TaskUpdateBroker()
        self._database = database
        self._listener: asyncio.Task[None] | None = None
        self._worker_id: UUID | None = None

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
        enabled: bool = True,
        cron_expression: str | None = None,
        deduplication_policy: str = "window",
        blocked_by: list[str] | None = None,
    ) -> None:
        self._scheduler.register(
            name=name,
            interval_seconds=interval_seconds,
            task_type=task_type,
            payload=payload,
            priority=priority,
            enabled=enabled,
            cron_expression=cron_expression,
            deduplication_policy=deduplication_policy,
            blocked_by=blocked_by,
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
        schedule_name: str | None = None,
    ) -> TaskStatusView:
        handler = self._handlers.get(task_type)
        if handler is None:
            raise ValueError(f"No handler registered for task type {task_type}")
        task = await self._repository.submit(
            task_type,
            payload,
            priority=priority,
            deduplication_key=deduplication_key,
            lane_key=lane_key or handler.lane_key,
            max_concurrency=max_concurrency or handler.max_concurrency,
            task_id=task_id,
            schedule_name=schedule_name,
        )
        await self._publish(task.id)
        return task

    async def get_status(self, task_id: UUID) -> TaskStatusView | None:
        return await self._repository.get(task_id)

    async def stream(self, task_id: UUID) -> AsyncIterator[TaskStatusView]:
        """Yield an initial snapshot and coordinator-published task changes."""

        async for task in self._updates.stream(task_id, self.get_status):
            yield task

    async def stream_all(self) -> AsyncIterator[TaskStatusView]:
        """Yield every committed task update, including newly submitted tasks."""

        async for task in self._updates.stream_all():
            yield task

    async def _publish(self, task_id: UUID) -> None:
        await self._updates.publish(task_id, self.get_status)

    async def find_active(
        self, task_type: str, deduplication_key: str
    ) -> TaskStatusView | None:
        """Find an active task for idempotent domain submissions."""

        return await self._repository.find_active(task_type, deduplication_key)

    async def find_active_by_type(self, task_type: str) -> TaskStatusView | None:
        """Find active work before accepting incompatible domain submissions."""

        return await self._repository.find_active_by_type(task_type)

    async def list_tasks(
        self, *, task_type: str | None = None, limit: int = 50, active_only: bool = False
    ) -> list[TaskStatusView]:
        return await self._repository.list(
            task_type=task_type, limit=limit, active_only=active_only
        )

    async def task_events(self, task_id: UUID, *, limit: int = 1000) -> list[TaskEvent]:
        return await self._repository.events(task_id, limit=limit)

    async def task_errors(self, *, limit: int = 100) -> list[TaskErrorEvent]:
        return await self._repository.errors(limit=limit)

    async def cancel(self, task_id: UUID) -> TaskStatusView | None:
        return await self._repository.cancel(task_id)

    async def cancel_unfinished(self, task_type: str, *, reason: str) -> int:
        """Prevent selected durable work from resuming merely because the process started."""

        return await self._repository.cancel_unfinished(task_type, reason=reason)

    async def list_schedules(self) -> list[TaskScheduleView]:
        return await self._repository.list_schedules()

    async def update_schedule(
        self, name: str, *, enabled: bool, cron_expression: str
    ) -> TaskScheduleView | None:
        return await self._repository.update_schedule(
            name, enabled=enabled, cron_expression=cron_expression
        )

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
            await self._scheduler.initialize(self._repository)
            self._listener = asyncio.create_task(
                self._updates.listen(self._database, self._stopping, self.get_status),
                name="task-coordinator-listener",
            )
            self._worker = asyncio.create_task(self._run(), name="task-coordinator-worker")

    async def stop(self) -> None:
        self._stopping.set()
        if self._worker is not None and not self._worker.done():
            self._worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker
        if self._listener is not None and not self._listener.done():
            self._listener.cancel()
            with suppress(asyncio.CancelledError):
                await self._listener
        running = tuple(self._running)
        for execution in running:
            execution.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        if self._worker_id is not None:
            await self._repository.release_worker_leases(self._worker_id)
            self._worker_id = None

    async def _run(self) -> None:
        worker_id = uuid4()
        self._worker_id = worker_id
        scheduler = asyncio.create_task(
            self._scheduler.run(self._repository, self.submit, self._stopping),
            name="task-coordinator-scheduler",
        )
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
                await self._publish(task.id)
                execution = asyncio.create_task(
                    self._execute(task, worker_id), name=f"task-{task.id}"
                )
                self._running.add(execution)
                execution.add_done_callback(self._running.discard)
        finally:
            scheduler.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler

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
        context = TaskContext(
            self._repository,
            task,
            worker_id,
            self._lease_duration,
            notify=lambda: self._publish(task.id),
        )
        heartbeat = asyncio.create_task(self._heartbeat(context), name=f"heartbeat-{task.id}")
        memory_reclaimed = False
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
            await self._repository.fail(
                task.id,
                worker_id,
                error,
                retryable=False,
                next_attempt_at=None,
                max_attempts=self._max_attempts,
            )
            await self._publish(task.id)
        else:
            reclaim = reclaim_process_memory()
            memory_reclaimed = True
            if reclaim is not None:
                result = result.model_copy(
                    update={
                        "counters": {
                            **result.counters,
                            "rss_after_task_bytes": reclaim.before_rss_bytes,
                            "rss_after_cleanup_bytes": reclaim.after_rss_bytes,
                            "rss_peak_bytes": reclaim.peak_rss_bytes,
                            "memory_released_bytes": reclaim.released_bytes,
                            "memory_collected_objects": reclaim.collected_objects,
                            "allocator_trim_attempted": int(
                                reclaim.allocator_trim_attempted
                            ),
                        }
                    }
                )
                logger.info(
                    "Task memory cleanup: task_type=%s task_id=%s before_rss=%s "
                    "after_rss=%s released=%s peak_rss=%s collected=%s allocator_trim=%s",
                    task.task_type,
                    task.id,
                    reclaim.before_rss_bytes,
                    reclaim.after_rss_bytes,
                    reclaim.released_bytes,
                    reclaim.peak_rss_bytes,
                    reclaim.collected_objects,
                    reclaim.allocator_trim_attempted,
                )
            await self._repository.complete(task.id, worker_id, result)
            await self._publish(task.id)
        finally:
            if not memory_reclaimed:
                reclaim = reclaim_process_memory()
                if reclaim is not None:
                    logger.info(
                        "Task memory cleanup after non-success: task_type=%s task_id=%s "
                        "before_rss=%s after_rss=%s released=%s peak_rss=%s collected=%s "
                        "allocator_trim=%s",
                        task.task_type,
                        task.id,
                        reclaim.before_rss_bytes,
                        reclaim.after_rss_bytes,
                        reclaim.released_bytes,
                        reclaim.peak_rss_bytes,
                        reclaim.collected_objects,
                        reclaim.allocator_trim_attempted,
                    )
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

    async def _heartbeat(self, context: TaskContext) -> None:
        interval = max(1.0, self._lease_duration.total_seconds() / 3)
        while True:
            await asyncio.sleep(interval)
            await context.heartbeat()

__all__ = [
    "PermanentTaskError",
    "RetryableTaskError",
    "TaskCancelledError",
    "TaskContext",
    "TaskCoordinator",
    "TaskHandler",
    "TaskLeaseLostError",
    "TaskPausedError",
    "TaskRepository",
]

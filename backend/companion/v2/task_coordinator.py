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

from companion.v2.legacy_task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskCancelledError,
    TaskContext as _TaskContext,
    TaskCoordinator as _TaskCoordinator,
    TaskHandler,
    TaskLeaseLostError,
    TaskRepository,
)
from companion.v2.task_schema import TaskStatusView


class TaskContext(_TaskContext):
    """V2 task context with one standard sync-step checkpoint contract."""

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


__all__ = [
    "PermanentTaskError",
    "RetryableTaskError",
    "TaskCancelledError",
    "TaskContext",
    "TaskCoordinator",
    "TaskHandler",
    "TaskLeaseLostError",
    "TaskRepository",
]

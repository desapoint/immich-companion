"""V2-owned task coordinator facade.

The durable PostgreSQL implementation is inherited from the existing coordinator so V2
keeps the same persisted tasks, LISTEN/NOTIFY updates, retry/lease semantics, and frontend
stream behavior. V2-specific checkpoint helpers live here and can evolve without changing
V1 imports.
"""

from __future__ import annotations

from typing import Any

from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskCancelledError,
    TaskContext as _TaskContext,
    TaskCoordinator as _TaskCoordinator,
    TaskHandler,
    TaskLeaseLostError,
    TaskRepository,
)


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
    """V2 coordinator type.

    It intentionally preserves the existing durable storage and notification semantics.
    The distinct V2 import path prevents future V2-only coordinator changes from requiring
    edits to the V1 module.
    """

    pass


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

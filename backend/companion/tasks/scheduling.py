"""Recurring task schedule registration and dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from companion.tasks.contracts import TaskStatusView
from companion.tasks.errors import TaskAlreadyActiveError
from companion.tasks.repository import TaskRepository

SubmitTask = Callable[..., Awaitable[TaskStatusView]]


class TaskScheduler:
    """Own recurring schedule definitions and durable dispatch decisions."""

    def __init__(self) -> None:
        self._definitions: list[dict[str, Any]] = []

    def register(
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
        self._definitions.append(
            {
                "name": name,
                "interval_seconds": interval_seconds,
                "task_type": task_type,
                "payload": dict(payload),
                "priority": priority,
                "enabled": enabled,
                "cron_expression": cron_expression,
                "deduplication_policy": deduplication_policy,
                "blocked_by": list(blocked_by or []),
            }
        )

    async def initialize(self, repository: TaskRepository) -> None:
        for definition in self._definitions:
            await repository.ensure_schedule(**definition)

    async def run(
        self,
        repository: TaskRepository,
        submit: SubmitTask,
        stopping: asyncio.Event,
    ) -> None:
        while not stopping.is_set():
            for schedule in await repository.claim_due_schedules():
                dedupe = self._deduplication_key(schedule)
                if await self._is_blocked(repository, schedule):
                    await repository.defer_schedule(schedule.name)
                    continue
                try:
                    await submit(
                        schedule.task_type,
                        schedule.payload,
                        priority=schedule.priority,
                        deduplication_key=dedupe,
                        schedule_name=schedule.name,
                    )
                except (TaskAlreadyActiveError, ValueError):
                    await repository.defer_schedule(schedule.name)
            await asyncio.sleep(1)

    @staticmethod
    def _deduplication_key(schedule) -> str:
        if schedule.deduplication_policy != "coalesce":
            return f"schedule:{schedule.name}:{schedule.next_run_at.isoformat()}"
        if schedule.task_type == "asset_sync" and isinstance(schedule.payload.get("mode"), str):
            return f"asset-sync:{schedule.payload['mode']}"
        return f"schedule:{schedule.name}"

    @staticmethod
    async def _is_blocked(repository: TaskRepository, schedule) -> bool:
        for blocked_key in schedule.blocked_by or []:
            if await repository.find_active(schedule.task_type, blocked_key):
                return True
        return False

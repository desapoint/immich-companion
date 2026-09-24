"""In-process and PostgreSQL-backed task update distribution."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from uuid import UUID

from companion.database import DatabaseManager
from companion.tasks.contracts import TaskStatusView
from companion.tasks.repository import TASK_UPDATE_CHANNEL

GetTask = Callable[[UUID], Awaitable[TaskStatusView | None]]


class TaskUpdateBroker:
    """Own task subscribers and sanitize global status broadcasts."""

    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[TaskStatusView]]] = {}
        self._global_subscribers: set[asyncio.Queue[TaskStatusView]] = set()

    async def stream(self, task_id: UUID, get_task: GetTask) -> AsyncIterator[TaskStatusView]:
        queue: asyncio.Queue[TaskStatusView] = asyncio.Queue(maxsize=8)
        subscribers = self._subscribers.setdefault(task_id, set())
        subscribers.add(queue)
        try:
            current = await get_task(task_id)
            if current is None:
                return
            yield current
            if current.status in ("completed", "failed", "cancelled"):
                return
            while True:
                try:
                    current = await asyncio.wait_for(queue.get(), timeout=5)
                except TimeoutError:
                    current = await get_task(task_id)
                    if current is None:
                        return
                yield current
                if current.status in ("completed", "failed", "cancelled"):
                    return
        finally:
            subscribers = self._subscribers.get(task_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(task_id, None)

    async def stream_all(self) -> AsyncIterator[TaskStatusView]:
        queue: asyncio.Queue[TaskStatusView] = asyncio.Queue(maxsize=32)
        self._global_subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._global_subscribers.discard(queue)

    async def publish(self, task_id: UUID, get_task: GetTask) -> None:
        queues = tuple(self._subscribers.get(task_id, ()))
        global_queues = tuple(self._global_subscribers)
        if not queues and not global_queues:
            return
        task = await get_task(task_id)
        if task is None:
            return
        global_result = task.result
        if global_result is not None:
            global_result = global_result.model_copy(
                update={
                    "summary": {
                        key: value
                        for key, value in global_result.summary.items()
                        if key not in {"failed_ids", "missing_ids"}
                    }
                }
            )
        global_task = task.model_copy(
            update={"payload": {}, "checkpoint": {}, "result": global_result}
        )
        for queue in (*queues, *global_queues):
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(task if queue in queues else global_task)

    async def listen(
        self,
        database: DatabaseManager,
        stopping: asyncio.Event,
        get_task: GetTask,
    ) -> None:
        while not stopping.is_set():
            try:
                async for payload in database.listen(TASK_UPDATE_CHANNEL):
                    if stopping.is_set():
                        return
                    try:
                        await self.publish(UUID(payload), get_task)
                    except ValueError:
                        continue
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(1)

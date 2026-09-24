"""Task status, event, and schedule route registration."""

from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from companion.task_coordinator import TaskCoordinator
from companion.task_schema import TaskErrorEvent, TaskEvent, TaskScheduleView, TaskStatusView


def register_task_routes(app: FastAPI, task_coordinator: TaskCoordinator | None) -> None:
    """Register durable task inspection and websocket routes."""

    @app.get("/api/tasks/{task_id}", response_model=TaskStatusView)
    async def task_status(task_id: UUID) -> TaskStatusView:
        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        task = await task_coordinator.get_status(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="The task was not found."
            )
        return task

    @app.get("/api/tasks/{task_id}/events", response_model=list[TaskEvent])
    async def task_events(
        task_id: UUID,
        limit: int = Query(default=1000, ge=1, le=5000),
    ) -> list[TaskEvent]:
        """Expose durable checkpoints, including opt-in sync memory snapshots."""

        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        if await task_coordinator.get_status(task_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="The task was not found."
            )
        return await task_coordinator.task_events(task_id, limit=limit)

    @app.websocket("/api/tasks/stream")
    async def task_updates_stream(websocket: WebSocket) -> None:
        """Stream task creation and progress updates before task IDs are known."""

        origin = websocket.headers.get("origin")
        host = websocket.headers.get("host")
        if origin and host and urlsplit(origin).netloc != host:
            await websocket.close(code=1008, reason="WebSocket origin is not allowed")
            return
        await websocket.accept()
        if task_coordinator is None:
            await websocket.close(code=1011, reason="Task coordinator unavailable")
            return
        try:
            async for task in task_coordinator.stream_all():
                await websocket.send_json(task.model_dump(mode="json"))
        except WebSocketDisconnect:
            return

    @app.websocket("/api/tasks/{task_id}/stream")
    async def task_stream(websocket: WebSocket, task_id: UUID) -> None:
        """Stream task snapshots from the central coordinator event channel."""

        origin = websocket.headers.get("origin")
        host = websocket.headers.get("host")
        if origin and host and urlsplit(origin).netloc != host:
            await websocket.close(code=1008, reason="WebSocket origin is not allowed")
            return
        await websocket.accept()
        try:
            if task_coordinator is None:
                await websocket.send_json({"error": "The task coordinator is unavailable."})
                return
            async for task in task_coordinator.stream(task_id):
                await websocket.send_json(task.model_dump(mode="json"))
        except WebSocketDisconnect:
            return

    @app.get("/api/tasks", response_model=list[TaskStatusView])
    async def list_tasks(
        task_type: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=50, ge=1, le=200),
        active_only: bool = Query(default=False),
    ) -> list[TaskStatusView]:
        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return await task_coordinator.list_tasks(
            task_type=task_type, limit=limit, active_only=active_only
        )

    @app.get("/api/errors", response_model=list[TaskErrorEvent])
    async def list_task_errors(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[TaskErrorEvent]:
        """List durable task failures for operator diagnosis."""

        if task_coordinator is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return await task_coordinator.task_errors(limit=limit)

    @app.get("/api/settings/sync", response_model=list[TaskScheduleView])
    async def sync_schedule_settings() -> list[TaskScheduleView]:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return await task_coordinator.list_schedules()

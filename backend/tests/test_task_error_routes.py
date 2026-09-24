"""Tests for Error Hub task-history routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.task_routes import register_task_routes


class ErrorCoordinator:
    def __init__(self) -> None:
        self.clear_calls = 0

    async def task_errors(self, *, limit: int):
        assert limit == 100
        return []

    async def clear_task_errors(self) -> int:
        self.clear_calls += 1
        return 6


def test_clear_task_errors_returns_removed_event_count() -> None:
    coordinator = ErrorCoordinator()
    app = FastAPI()
    register_task_routes(app, coordinator)  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.delete("/api/errors")

    assert response.status_code == 200
    assert response.json() == {"cleared": 6}
    assert coordinator.clear_calls == 1


def test_clear_task_errors_requires_database_coordinator() -> None:
    app = FastAPI()
    register_task_routes(app, None)

    with TestClient(app) as client:
        response = client.delete("/api/errors")

    assert response.status_code == 503

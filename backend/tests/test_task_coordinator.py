"""Coordinator lifecycle behavior that does not require a live PostgreSQL server."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion.task_coordinator import PermanentTaskError, RetryableTaskError, TaskCoordinator
from companion.task_schema import TaskResult, TaskStatusView

TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WORKER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def task() -> TaskStatusView:
    now = datetime.now(UTC)
    return TaskStatusView(
        id=TASK_ID,
        task_type="test",
        status="running",
        priority=0,
        deduplication_key=None,
        lane_key="test",
        payload={"value": 3},
        checkpoint={},
        counters={},
        progress={},
        result=None,
        error=None,
        attempt=1,
        next_attempt_at=None,
        lease_owner=WORKER_ID,
        lease_expires_at=now,
        created_at=now,
        started_at=now,
        heartbeat_at=now,
        completed_at=None,
    )


class FakeRepository:
    def __init__(self) -> None:
        self.failures: list[dict[str, object]] = []
        self.completed: list[TaskResult] = []

    async def fail(self, _task_id, _worker_id, error, **kwargs):
        self.failures.append({"error": error, **kwargs})
        return None

    async def complete(self, _task_id, _worker_id, result):
        self.completed.append(result)

    async def heartbeat(self, *_args, **_kwargs):
        raise AssertionError("the immediate test handler should not need a heartbeat")

    async def is_cancelled(self, *_args, **_kwargs):
        return False


class RetryHandler:
    task_type = "test"
    lane_key = "test"
    max_concurrency = 1

    async def execute(self, _context, _payload):
        raise RetryableTaskError("temporary")


class PermanentHandler(RetryHandler):
    async def execute(self, _context, _payload):
        raise PermanentTaskError("invalid")


@pytest.mark.asyncio
async def test_retryable_handler_keeps_task_id_and_persists_backoff() -> None:
    coordinator = TaskCoordinator(None)  # type: ignore[arg-type]
    repository = FakeRepository()
    coordinator._repository = repository  # type: ignore[assignment]
    coordinator.register_handler(RetryHandler())

    await coordinator._execute(task(), WORKER_ID)

    assert len(repository.failures) == 1
    failure = repository.failures[0]
    assert isinstance(failure["error"], RetryableTaskError)
    assert failure["retryable"] is True
    assert failure["max_attempts"] == 5
    assert failure["next_attempt_at"] is not None


@pytest.mark.asyncio
async def test_permanent_handler_is_not_retried() -> None:
    coordinator = TaskCoordinator(None)  # type: ignore[arg-type]
    repository = FakeRepository()
    coordinator._repository = repository  # type: ignore[assignment]
    coordinator.register_handler(PermanentHandler())

    await coordinator._execute(task(), WORKER_ID)

    failure = repository.failures[0]
    assert isinstance(failure["error"], PermanentTaskError)
    assert failure["retryable"] is False
    assert failure["next_attempt_at"] is None

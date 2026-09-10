"""Coordinator lifecycle behavior that does not require a live PostgreSQL server."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
    TaskPausedError,
)
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
        self.cancelled_types: list[tuple[str, str]] = []
        self.paused: list[tuple[UUID, UUID]] = []
        self.pause_requests: list[UUID] = []
        self.resume_requests: list[UUID] = []
        self.control = "running"
        self.saved_checkpoints: list[dict[str, object]] = []

    async def fail(self, _task_id, _worker_id, error, **kwargs):
        self.failures.append({"error": error, **kwargs})
        return None

    async def complete(self, _task_id, _worker_id, result):
        self.completed.append(result)

    async def heartbeat(self, *_args, **_kwargs):
        raise AssertionError("the immediate test handler should not need a heartbeat")

    async def is_cancelled(self, *_args, **_kwargs):
        return False

    async def cancel_unfinished(self, task_type, *, reason):
        self.cancelled_types.append((task_type, reason))
        return 2

    async def mark_paused(self, task_id, worker_id):
        self.paused.append((task_id, worker_id))
        return None

    async def get(self, _task_id):
        return task()

    async def request_pause(self, task_id):
        self.pause_requests.append(task_id)
        return task().model_copy(update={"status": "pause_requested"})

    async def resume(self, task_id):
        self.resume_requests.append(task_id)
        return task().model_copy(update={"status": "recovering"})

    async def checkpoint(self, _task_id, _worker_id, **values):
        self.saved_checkpoints.append(values)

    async def control_state(self, _task_id, _worker_id):
        return self.control


class RetryHandler:
    task_type = "test"
    lane_key = "test"
    max_concurrency = 1

    async def execute(self, _context, _payload):
        raise RetryableTaskError("temporary")


class PermanentHandler(RetryHandler):
    async def execute(self, _context, _payload):
        raise PermanentTaskError("invalid")


class PausedHandler(RetryHandler):
    supports_pause = True

    async def execute(self, _context, _payload):
        raise TaskPausedError("paused")


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


@pytest.mark.asyncio
async def test_paused_handler_releases_its_attempt_without_failure() -> None:
    coordinator = TaskCoordinator(None)  # type: ignore[arg-type]
    repository = FakeRepository()
    coordinator._repository = repository  # type: ignore[assignment]
    coordinator.register_handler(PausedHandler())

    await coordinator._execute(task(), WORKER_ID)

    assert repository.paused == [(TASK_ID, WORKER_ID)]
    assert repository.failures == []
    assert repository.completed == []


@pytest.mark.asyncio
async def test_pause_and_resume_are_exposed_only_for_capable_handlers() -> None:
    coordinator = TaskCoordinator(None)  # type: ignore[arg-type]
    repository = FakeRepository()
    coordinator._repository = repository  # type: ignore[assignment]
    coordinator.register_handler(PausedHandler())

    assert (await coordinator.pause(TASK_ID)).status == "pause_requested"  # type: ignore[union-attr]
    assert (await coordinator.resume(TASK_ID)).status == "recovering"  # type: ignore[union-attr]
    assert repository.pause_requests == [TASK_ID]
    assert repository.resume_requests == [TASK_ID]

    coordinator.register_handler(PermanentHandler())
    with pytest.raises(ValueError, match="does not support pausing"):
        await coordinator.pause(TASK_ID)


@pytest.mark.asyncio
async def test_checkpoint_is_durable_before_pause_stops_the_handler() -> None:
    repository = FakeRepository()
    repository.control = "pause_requested"
    context = TaskContext(repository, task(), WORKER_ID, timedelta(seconds=60))  # type: ignore[arg-type]

    with pytest.raises(TaskPausedError):
        await context.checkpoint(
            checkpoint={"phase": "candidate_index", "candidate_assets_processed": 1_000},
            counters={"candidate_assets_processed": 1_000},
            progress={"completed": 1_000},
        )

    assert repository.saved_checkpoints[0]["checkpoint"] == {
        "phase": "candidate_index",
        "candidate_assets_processed": 1_000,
    }


@pytest.mark.asyncio
async def test_startup_fence_cancels_only_requested_unfinished_task_type() -> None:
    coordinator = TaskCoordinator(None)  # type: ignore[arg-type]
    repository = FakeRepository()
    coordinator._repository = repository  # type: ignore[assignment]

    cancelled = await coordinator.cancel_unfinished(
        "asset_sync",
        reason="Do not resume library sync at startup.",
    )

    assert cancelled == 2
    assert repository.cancelled_types == [
        ("asset_sync", "Do not resume library sync at startup.")
    ]

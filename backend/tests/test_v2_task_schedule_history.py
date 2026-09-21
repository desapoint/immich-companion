from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from companion.models import TaskLaneRecord, TaskRecord, TaskScheduleRecord
from companion.v2.legacy_task_coordinator import (
    TaskAlreadyActiveError,
    TaskCoordinator,
    TaskRepository,
    _public_schedule,
)


class _Context:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _Database:
    def __init__(self, session) -> None:
        self.session = session

    def sessions(self):
        return self.session


def _schedule(*, next_run_at: datetime, last_run_at: datetime | None = None):
    return TaskScheduleRecord(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        name="asset-sync-full",
        enabled=True,
        interval_seconds=3600,
        cron_expression="0 * * * *",
        deduplication_policy="coalesce",
        blocked_by=[],
        next_run_at=next_run_at,
        last_run_at=last_run_at,
        task_type="asset_sync",
        payload={"mode": "full"},
        priority=100,
    )


def test_schedule_view_uses_persisted_schedule_history() -> None:
    actual_start = datetime(2026, 9, 18, 2, 45, tzinfo=UTC)

    result = _public_schedule(
        _schedule(
            next_run_at=datetime(2026, 9, 18, 3, 0, tzinfo=UTC),
            last_run_at=actual_start,
        )
    )

    assert result.last_run_at == actual_start


@pytest.mark.asyncio
async def test_startup_preserves_existing_overdue_schedule() -> None:
    overdue = datetime.now(UTC) - timedelta(minutes=10)
    schedule = _schedule(next_run_at=overdue)

    class Session(_Context):
        def begin(self):
            return _Context()

        async def scalar(self, _statement):
            return schedule

    repository = TaskRepository(_Database(Session()))  # type: ignore[arg-type]

    await repository.ensure_schedule(
        name=schedule.name,
        interval_seconds=schedule.interval_seconds,
        task_type=schedule.task_type,
        payload=schedule.payload,
        priority=schedule.priority,
        enabled=schedule.enabled,
        cron_expression=schedule.cron_expression,
        deduplication_policy=schedule.deduplication_policy,
        blocked_by=schedule.blocked_by,
    )

    assert schedule.next_run_at == overdue


@pytest.mark.asyncio
async def test_schedule_history_updates_when_scheduled_task_first_starts() -> None:
    schedule = _schedule(next_run_at=datetime.now(UTC) + timedelta(hours=1))
    task = TaskRecord(
        id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        task_type="asset_sync",
        payload={"mode": "full"},
        priority=100,
        status="queued",
        deduplication_key="asset-sync:full",
        schedule_name=schedule.name,
        lane_key="asset_sync",
        checkpoint={},
        counters={},
        progress={},
        attempt=0,
        next_attempt_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    lane = TaskLaneRecord(lane_key="asset_sync", max_concurrency=1)

    class ScalarRows:
        def __init__(self, rows) -> None:
            self.rows = rows

        def all(self):
            return self.rows

        def __iter__(self):
            return iter(self.rows)

    class Session(_Context):
        def __init__(self) -> None:
            self.scalar_values = iter((lane, 0, schedule))
            self.scalars_values = iter((ScalarRows([]), ScalarRows([task])))

        def begin(self):
            return _Context()

        async def scalar(self, _statement):
            return next(self.scalar_values)

        async def scalars(self, _statement):
            return next(self.scalars_values)

        def add(self, _record) -> None:
            return None

        async def flush(self) -> None:
            return None

    repository = TaskRepository(_Database(Session()))  # type: ignore[arg-type]

    claimed = await repository.claim(
        UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        lease_duration=timedelta(seconds=60),
    )

    assert claimed is not None
    assert claimed.started_at is not None
    assert schedule.last_run_at == claimed.started_at


@pytest.mark.asyncio
async def test_blocked_schedule_is_deferred_for_retry() -> None:
    original_next_run = datetime.now(UTC) + timedelta(minutes=15)
    schedule = _schedule(next_run_at=original_next_run)

    class Session(_Context):
        def begin(self):
            return _Context()

        async def scalar(self, _statement):
            return schedule

    repository = TaskRepository(_Database(Session()))  # type: ignore[arg-type]

    await repository.defer_schedule(schedule.name, retry_seconds=60)

    assert datetime.now(UTC) < schedule.next_run_at < original_next_run


@pytest.mark.asyncio
async def test_scheduler_defers_a_tick_while_its_blocker_is_active(
    monkeypatch,
) -> None:
    schedule = _schedule(next_run_at=datetime.now(UTC))
    schedule.blocked_by = ["asset-sync:full"]
    coordinator = TaskCoordinator(None)  # type: ignore[arg-type]

    class Repository:
        def __init__(self) -> None:
            self.deferred: list[str] = []

        async def claim_due_schedules(self):
            return [schedule]

        async def find_active(self, _task_type, _deduplication_key):
            return object()

        async def defer_schedule(self, name):
            self.deferred.append(name)

    repository = Repository()
    coordinator._repository = repository  # type: ignore[assignment]

    async def stop_after_iteration(_seconds):
        coordinator._stopping.set()

    monkeypatch.setattr(
        "companion.v2.legacy_task_coordinator.asyncio.sleep",
        stop_after_iteration,
    )

    await coordinator._schedule()

    assert repository.deferred == [schedule.name]


@pytest.mark.asyncio
async def test_scheduler_labels_submitted_work_with_its_schedule(monkeypatch) -> None:
    schedule = _schedule(next_run_at=datetime.now(UTC))
    coordinator = TaskCoordinator(None)  # type: ignore[arg-type]
    submissions: list[dict[str, object]] = []

    class Repository:
        async def claim_due_schedules(self):
            return [schedule]

        async def find_active(self, _task_type, _deduplication_key):
            return None

    coordinator._repository = Repository()  # type: ignore[assignment]

    async def submit(_task_type, _payload, **kwargs):
        submissions.append(kwargs)

    async def stop_after_iteration(_seconds):
        coordinator._stopping.set()

    monkeypatch.setattr(coordinator, "submit", submit)
    monkeypatch.setattr(
        "companion.v2.legacy_task_coordinator.asyncio.sleep",
        stop_after_iteration,
    )

    await coordinator._schedule()

    assert submissions[0]["schedule_name"] == schedule.name
    assert submissions[0]["deduplication_key"] == "asset-sync:full"


@pytest.mark.asyncio
async def test_scheduled_submission_defers_instead_of_reusing_active_manual_task() -> None:
    lane = TaskLaneRecord(lane_key="asset_sync", max_concurrency=1)
    existing = TaskRecord(
        id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        task_type="asset_sync",
        payload={"mode": "full"},
        priority=100,
        status="running",
        deduplication_key="asset-sync:full",
        schedule_name=None,
        lane_key="asset_sync",
        checkpoint={},
        counters={},
        progress={},
        attempt=1,
        created_at=datetime.now(UTC),
    )

    class Session(_Context):
        def __init__(self) -> None:
            self.scalar_values = iter((lane, existing))

        def begin(self):
            return _Context()

        async def scalar(self, _statement):
            return next(self.scalar_values)

        async def execute(self, _statement, _parameters):
            return None

    repository = TaskRepository(_Database(Session()))  # type: ignore[arg-type]

    with pytest.raises(TaskAlreadyActiveError):
        await repository.submit(
            "asset_sync",
            {"mode": "full"},
            priority=100,
            deduplication_key="asset-sync:full",
            lane_key="asset_sync",
            max_concurrency=1,
            schedule_name="asset-sync-full",
        )

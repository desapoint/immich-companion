from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion.task_schema import TaskScheduleView
from companion.v2.task_coordinator import TaskRepository


class Session:
    def __init__(self, last_run_at: datetime) -> None:
        self.last_run_at = last_run_at
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def scalar(self, statement):
        self.statement = statement
        return self.last_run_at


class Database:
    def __init__(self, session: Session) -> None:
        self.session = session

    def sessions(self):
        return self.session


@pytest.mark.asyncio
async def test_schedule_history_uses_actual_matching_task_start(monkeypatch) -> None:
    schedule = TaskScheduleView(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        name="asset-sync-full",
        enabled=True,
        interval_seconds=3600,
        cron_expression="0 * * * *",
        deduplication_policy="coalesce",
        blocked_by=[],
        next_run_at=datetime(2026, 9, 18, 3, 0, tzinfo=UTC),
        task_type="asset_sync",
        payload={"mode": "full"},
        priority=100,
    )
    actual_start = datetime(2026, 9, 18, 2, 45, tzinfo=UTC)
    session = Session(actual_start)

    async def legacy_schedules(_self):
        return [schedule]

    monkeypatch.setattr(
        "companion.v2.legacy_task_coordinator.TaskRepository.list_schedules",
        legacy_schedules,
    )

    result = await TaskRepository(Database(session)).list_schedules()  # type: ignore[arg-type]

    assert result[0].last_run_at == actual_start
    assert session.statement is not None
    compiled = str(session.statement)
    assert "tasks.started_at" in compiled
    assert "tasks.task_type" in compiled

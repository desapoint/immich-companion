"""Tests for V2 duplicate policy state."""

from types import SimpleNamespace

import pytest

from companion.v2_duplicate_review_state import (
    V2_DUPLICATE_POLICY_REFRESH_TASK_TYPE,
    V2DuplicateReviewStateRefreshService,
    V2DuplicateReviewStateRefreshTaskHandler,
    v2_policy_state,
)


def group(*, eligible=True, status="exact", offline=False, auto_selected=False):
    return SimpleNamespace(
        eligible=eligible,
        status=status,
        members=[SimpleNamespace(is_offline=offline)],
        auto_selected=auto_selected,
    )


def test_policy_state_keeps_auto_ready_distinct_from_actionable() -> None:
    assert v2_policy_state(group(eligible=False, auto_selected=True)) == "blocked"
    assert v2_policy_state(group(status="ineligible")) == "blocked"
    assert v2_policy_state(group(offline=True)) == "needs_review"
    assert v2_policy_state(group(auto_selected=True)) == "auto_ready"
    assert v2_policy_state(group()) == "needs_review"


@pytest.mark.asyncio
async def test_policy_refresh_handler_propagates_refresh_failure() -> None:
    class Service:
        async def refresh(self):
            raise RuntimeError("policy refresh failed")

    class Context:
        async def checkpoint(self, **_kwargs):
            return None

    with pytest.raises(RuntimeError, match="policy refresh failed"):
        await V2DuplicateReviewStateRefreshTaskHandler(Service()).execute(Context(), {})


@pytest.mark.asyncio
async def test_policy_refresh_service_waits_for_durable_child_completion() -> None:
    task_id = SimpleNamespace(id="task-id")

    class Tasks:
        async def submit(self, task_type, payload, **kwargs):
            assert task_type == V2_DUPLICATE_POLICY_REFRESH_TASK_TYPE
            assert payload == {}
            assert "deduplication_key" not in kwargs
            return task_id

        async def start(self):
            return None

        async def wait(self, _task_id):
            return SimpleNamespace(status="completed")

    completed = await V2DuplicateReviewStateRefreshService(Tasks()).refresh_after_change()
    assert completed.status == "completed"


@pytest.mark.asyncio
async def test_policy_refresh_service_reports_terminal_child_failure() -> None:
    class Tasks:
        async def submit(self, *_args, **_kwargs):
            return SimpleNamespace(id="task-id")

        async def start(self):
            return None

        async def wait(self, _task_id):
            return SimpleNamespace(status="failed")

    with pytest.raises(RuntimeError, match="did not complete"):
        await V2DuplicateReviewStateRefreshService(Tasks()).refresh_after_change()


@pytest.mark.asyncio
async def test_policy_refresh_submissions_do_not_coalesce_across_parent_commits() -> None:
    submitted: list[dict[str, object]] = []

    class Tasks:
        next_id = 0

        async def submit(self, task_type, payload, **kwargs):
            self.next_id += 1
            submitted.append({"task_type": task_type, "payload": payload, **kwargs})
            return SimpleNamespace(id=f"task-{self.next_id}")

        async def start(self):
            return None

        async def wait(self, task_id):
            return SimpleNamespace(id=task_id, status="completed")

    service = V2DuplicateReviewStateRefreshService(Tasks())
    first = await service.refresh_after_change()
    second = await service.refresh_after_change()

    assert first.id == "task-1"
    assert second.id == "task-2"
    assert all("deduplication_key" not in item for item in submitted)

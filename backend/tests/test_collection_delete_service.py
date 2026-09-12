"""Restartable collection deletion over the Immich API."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.collection_delete_service import CollectionDeleteService, tag_delete_targets
from companion.immich import ImmichApiError, ImmichTag

FIRST = UUID("11111111-1111-4111-8111-111111111111")
SECOND = UUID("22222222-2222-4222-8222-222222222222")
THIRD = UUID("33333333-3333-4333-8333-333333333333")
PLAN = UUID("44444444-4444-4444-8444-444444444444")
SELECTION = UUID("55555555-5555-4555-8555-555555555555")


def test_tag_plan_deletes_selected_descendants_before_parents() -> None:
    tags = [
        ImmichTag(id=FIRST, name="parent", value="parent"),
        ImmichTag(id=SECOND, name="child", value="child", parentId=FIRST),
        ImmichTag(id=THIRD, name="grandchild", value="grandchild", parentId=SECOND),
    ]

    assert tag_delete_targets([FIRST, SECOND, THIRD], tags) == (
        [THIRD, SECOND, FIRST], []
    )
    assert tag_delete_targets([FIRST, SECOND], tags) == ([], [FIRST, SECOND])


class FakeActions:
    def __init__(self, applicable_ids: list[UUID]) -> None:
        self.record = SimpleNamespace(
            id=PLAN,
            action="delete_albums",
            operation="delete_relation",
            status="planned",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            relation_work={"selection_id": str(SELECTION)},
            applicable_ids=[str(identifier) for identifier in applicable_ids],
            skipped_ids=[],
            result={"items": []},
        )
        self.fail_checkpoint_once = False

    async def get_plan(self, _plan_id):
        return self.record

    async def claim_collection_delete_plan(self, _plan_id):
        if self.record.status not in {"planned", "failed", "partial"}:
            return None
        self.record.status = "running"
        return self.record

    async def start_collection_delete_pass(self, _plan_id, work_ids):
        self.record.result = {**self.record.result, "work_ids": work_ids, "work_index": 0}

    async def record_collection_delete_item_result(self, _plan_id, item, *, next_index=None):
        if self.fail_checkpoint_once:
            self.fail_checkpoint_once = False
            raise RuntimeError("checkpoint unavailable")
        items = [value for value in self.record.result["items"] if value["id"] != item["id"]]
        self.record.result = {
            **self.record.result,
            "items": [*items, item],
            "work_index": (
                next_index
                if next_index is not None
                else self.record.result.get("work_index", 0)
            ),
        }

    async def finish_collection_delete_plan(self, _plan_id, status):
        self.record.status = status


class FakeSelections:
    def __init__(self, selected: list[UUID]) -> None:
        self.selected = set(selected)

    async def remove(self, _selection_id, identifiers):
        self.selected.difference_update(identifiers)


class FakeImmich:
    def __init__(self, identifiers: list[UUID]) -> None:
        self.existing = set(identifiers)
        self.calls: list[UUID] = []
        self.fail_once: set[UUID] = set()

    async def delete_album(self, identifier):
        self.calls.append(identifier)
        if identifier in self.fail_once:
            self.fail_once.remove(identifier)
            raise ImmichApiError("delete album", 503)
        if identifier not in self.existing:
            raise ImmichApiError("delete album", 404)
        self.existing.remove(identifier)

    async def list_album_catalog(self):
        return [SimpleNamespace(id=identifier) for identifier in self.existing]


@pytest.mark.asyncio
async def test_failed_items_retry_without_replaying_completed_deletions() -> None:
    actions = FakeActions([FIRST, SECOND])
    selections = FakeSelections([FIRST, SECOND])
    immich = FakeImmich([FIRST, SECOND])
    immich.fail_once.add(SECOND)
    service = CollectionDeleteService(
        actions, selections, immich, allow_destructive_actions=True
    )

    first = await service.execute("album", PLAN)
    assert first.status == "failed"
    assert selections.selected == {SECOND}
    assert [item["status"] for item in first.result["items"]] == ["completed", "failed"]

    second = await service.execute("album", PLAN)
    assert second.status == "completed"
    assert selections.selected == set()
    assert immich.calls == [FIRST, SECOND, SECOND]
    await service.execute("album", PLAN)
    assert immich.calls == [FIRST, SECOND, SECOND]


@pytest.mark.asyncio
async def test_uncheckpointed_api_success_is_reconciled_as_already_missing() -> None:
    actions = FakeActions([FIRST])
    actions.fail_checkpoint_once = True
    selections = FakeSelections([FIRST])
    immich = FakeImmich([FIRST])
    service = CollectionDeleteService(
        actions, selections, immich, allow_destructive_actions=True
    )

    with pytest.raises(RuntimeError, match="checkpoint unavailable"):
        await service.execute("album", PLAN)
    assert actions.record.status == "failed"
    assert selections.selected == {FIRST}

    resumed = await service.execute("album", PLAN)
    assert resumed.status == "completed"
    assert resumed.result["items"] == [
        {"id": str(FIRST), "status": "skipped", "reason": "Already missing."}
    ]
    assert selections.selected == set()


@pytest.mark.asyncio
async def test_large_plan_runs_in_bounded_resumable_passes() -> None:
    identifiers = [UUID(int=index + 10) for index in range(101)]
    actions = FakeActions(identifiers)
    selections = FakeSelections(identifiers)
    immich = FakeImmich(identifiers)
    service = CollectionDeleteService(
        actions, selections, immich, allow_destructive_actions=True
    )

    first = await service.execute("album", PLAN)
    assert first.status == "partial"
    assert len(immich.calls) == 100
    assert first.result["work_index"] == 100

    resumed = await service.execute("album", PLAN)
    assert resumed.status == "completed"
    assert len(immich.calls) == 101
    assert selections.selected == set()

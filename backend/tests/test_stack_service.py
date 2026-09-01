"""Shared stack planning and execution regression coverage."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.stack_service import StackService

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ASSET_THREE = UUID("33333333-3333-4333-8333-333333333333")
STACK_ID = UUID("44444444-4444-4444-8444-444444444444")


def member(asset_id: UUID):
    return SimpleNamespace(id=asset_id)


def stack(*asset_ids: UUID, primary: UUID = ASSET_ONE):
    return SimpleNamespace(
        id=STACK_ID,
        primary_asset_id=primary,
        assets=[member(asset_id) for asset_id in asset_ids],
    )


class FakeImmich:
    def __init__(self, stacks=None) -> None:
        self.stacks = list(stacks or [])
        self.calls: list[tuple[str, UUID | None, list[UUID]]] = []

    async def list_stacks(self):
        return self.stacks

    async def create_stack(self, asset_ids):
        self.calls.append(("create", None, asset_ids))
        self.stacks = [stack(*asset_ids, primary=asset_ids[0])]

    async def delete_stack(self, stack_id):
        self.calls.append(("delete", stack_id, []))

    async def update_stack_primary(self, stack_id, asset_id):
        self.calls.append(("primary", stack_id, [asset_id]))

    async def remove_asset_from_stack(self, stack_id, asset_id):
        self.calls.append(("remove", stack_id, [asset_id]))


class FakeAssets:
    async def stack_asset_ids(self, asset_id):
        return [asset_id]


class FakeSync:
    def __init__(self) -> None:
        self.repairs: list[tuple[list[UUID], bool]] = []

    async def reconcile_targets(self, asset_ids, *, include_stacks=False):
        self.repairs.append((asset_ids, include_stacks))


def service(immich: FakeImmich, sync: FakeSync | None = None) -> StackService:
    return StackService(immich, FakeAssets(), sync or FakeSync())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_conflicts_report_selected_and_unselected_members() -> None:
    workflow = service(FakeImmich([stack(ASSET_ONE, ASSET_TWO, ASSET_THREE)]))

    conflicts = await workflow.conflicts([ASSET_ONE, ASSET_TWO])

    assert len(conflicts) == 1
    assert conflicts[0].selected_count == 2
    assert conflicts[0].member_count == 3
    assert conflicts[0].includes_unselected is True


@pytest.mark.asyncio
async def test_move_selected_preserves_unselected_stack_with_new_primary() -> None:
    immich = FakeImmich([stack(ASSET_ONE, ASSET_THREE, primary=ASSET_ONE)])
    workflow = service(immich)

    preparation = await workflow.prepare([ASSET_ONE, ASSET_TWO], "move_selected")

    assert preparation.asset_ids == [ASSET_ONE, ASSET_TWO]
    assert preparation.affected_ids == [ASSET_ONE, ASSET_TWO, ASSET_THREE]
    assert immich.calls == [
        ("primary", STACK_ID, [ASSET_THREE]),
        ("remove", STACK_ID, [ASSET_ONE]),
    ]


@pytest.mark.asyncio
async def test_include_existing_expands_and_removes_old_stack() -> None:
    immich = FakeImmich([stack(ASSET_ONE, ASSET_THREE)])
    workflow = service(immich)

    preparation = await workflow.prepare([ASSET_ONE, ASSET_TWO], "include_existing")

    assert preparation.asset_ids == [ASSET_ONE, ASSET_TWO, ASSET_THREE]
    assert immich.calls == [("delete", STACK_ID, [])]


@pytest.mark.asyncio
async def test_execute_creates_repairs_and_verifies_prepared_stack() -> None:
    immich = FakeImmich()
    sync = FakeSync()
    workflow = service(immich, sync)
    preparation = await workflow.prepare([ASSET_ONE, ASSET_TWO], "move_selected")

    verified = await workflow.execute(preparation)

    assert verified is True
    assert immich.calls == [("create", None, [ASSET_ONE, ASSET_TWO])]
    assert sync.repairs == [([ASSET_ONE, ASSET_TWO], True)]

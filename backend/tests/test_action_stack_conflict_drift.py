"""Regression coverage for reviewed stack conflict safety."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from companion.action_schema import (
    AssetActionExecuteRequest,
    AssetActionPlanRequest,
    AssetSelectionRequest,
    AssetSelectionResolution,
    AssetSelectionSummary,
)
from companion.action_service import ActionPlanConflictError, AssetActionService
from companion.config import Settings
from companion.models import ActionPlanRecord
from companion.stack_service import StackSelectionError, StackService

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ASSET_THREE = UUID("33333333-3333-4333-8333-333333333333")
ASSET_FOUR = UUID("44444444-4444-4444-8444-444444444444")
STACK_ID = UUID("55555555-5555-4555-8555-555555555555")
STACK_TWO_ID = UUID("66666666-6666-4666-8666-666666666666")


def selection_resolution() -> AssetSelectionResolution:
    return AssetSelectionResolution(
        ids=[ASSET_ONE, ASSET_TWO],
        missing_ids=[],
        summary=AssetSelectionSummary(
            total=2,
            archived=0,
            unarchived=2,
            favorite=0,
            not_favorite=2,
            trashed=0,
            not_trashed=2,
            archive_action="archive",
            favorite_action="favorite",
            can_trash=True,
            can_restore=False,
        ),
    )


def stack(*member_ids: UUID):
    return SimpleNamespace(
        id=STACK_ID,
        primary_asset_id=ASSET_ONE,
        assets=[SimpleNamespace(id=asset_id) for asset_id in member_ids],
    )


def second_stack(*member_ids: UUID):
    return SimpleNamespace(
        id=STACK_TWO_ID,
        primary_asset_id=ASSET_TWO,
        assets=[SimpleNamespace(id=asset_id) for asset_id in member_ids],
    )


class FakeAssets:
    async def resolve_selection(self, *_args, **_kwargs):
        return selection_resolution()

    async def applicable_action_ids(self, *_args, **_kwargs):
        return {ASSET_ONE, ASSET_TWO}


class FakeActions:
    def __init__(self) -> None:
        self.record: ActionPlanRecord | None = None
        self.finished: tuple[str, dict[str, object]] | None = None

    async def create_plan(
        self,
        request,
        current,
        operation,
        applicable_ids,
        skipped_ids,
        relation_work,
        target_digest,
        expires_at,
    ):
        self.record = ActionPlanRecord(
            id=uuid4(),
            action=request.action,
            operation=operation,
            relation_id=None,
            relation_ids=[],
            relation_work=relation_work,
            selection=request.selection.model_dump(mode="json"),
            target_ids=[str(identifier) for identifier in current.ids],
            target_digest=target_digest,
            applicable_ids=[str(identifier) for identifier in applicable_ids],
            skipped_ids=[str(identifier) for identifier in skipped_ids],
            missing_ids=[],
            destructive=False,
            status="planned",
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        return self.record

    async def get_plan(self, _plan_id):
        return self.record

    async def finish_plan(self, _plan_id, status, result):
        assert self.record is not None
        self.record.status = status
        self.finished = (status, result)

    async def claim_plan(self, _plan_id):
        raise AssertionError("A drifted stack plan must fail before it is claimed")


class FakeImmich:
    def __init__(self) -> None:
        self.stacks = [stack(ASSET_ONE, ASSET_THREE)]
        self.mutations: list[str] = []

    async def list_stacks(self):
        return self.stacks

    async def create_stack(self, _ids):
        self.mutations.append("create")

    async def delete_stack(self, _stack_id):
        self.mutations.append("delete")

    async def update_stack_primary(self, _stack_id, _asset_id):
        self.mutations.append("primary")

    async def remove_asset_from_stack(self, _stack_id, _asset_id):
        self.mutations.append("remove")


class FakeSync:
    async def synchronize(self):
        return None


@pytest.mark.asyncio
async def test_assets_stack_execution_rejects_source_topology_changed_after_review() -> None:
    assets = FakeAssets()
    actions = FakeActions()
    immich = FakeImmich()
    service = AssetActionService(
        Settings(),
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        FakeSync(),  # type: ignore[arg-type]
    )
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])

    preview = await service.plan(
        AssetActionPlanRequest(
            selection=selection,
            action="stack",
            stack_primary_asset_id=ASSET_TWO,
        )
    )
    assert preview.stack_conflicts[0].member_asset_ids == [ASSET_ONE, ASSET_THREE]

    reviewed = await service.plan(
        AssetActionPlanRequest(
            selection=selection,
            action="stack",
            stack_primary_asset_id=ASSET_TWO,
            stack_resolution={str(STACK_ID): "move_selected"},
        )
    )
    immich.stacks = [stack(ASSET_ONE, ASSET_FOUR)]

    with pytest.raises(ActionPlanConflictError, match="stack membership changed"):
        await service.execute(AssetActionExecuteRequest(plan_id=reviewed.id, confirm=True))

    assert actions.finished is not None
    assert actions.finished[0] == "drifted"
    assert actions.finished[1]["error"] == "stack_topology_drift"
    assert immich.mutations == []


@pytest.mark.asyncio
async def test_incomplete_per_stack_resolution_fails_before_any_source_stack_mutation() -> None:
    immich = FakeImmich()
    immich.stacks = [
        stack(ASSET_ONE, ASSET_THREE),
        second_stack(ASSET_TWO, ASSET_FOUR),
    ]
    workflow = StackService(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        FakeSync(),  # type: ignore[arg-type]
    )

    with pytest.raises(StackSelectionError, match="needs a reviewed resolution"):
        await workflow.prepare(
            [ASSET_ONE, ASSET_TWO],
            {str(STACK_ID): "include_existing"},
            ASSET_TWO,
        )

    assert immich.mutations == []

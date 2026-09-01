"""Action planning, skip, execution, and safety regression coverage."""

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
from companion.action_service import (
    ActionPlanConflictError,
    AssetActionService,
    DestructiveActionsDisabledError,
)
from companion.config import Settings
from companion.models import ActionPlanRecord
from companion.sync_settings import SyncRuntimeSettings

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
RELATION_ID = UUID("44444444-4444-4444-8444-444444444444")
RELATION_TWO = UUID("55555555-5555-4555-8555-555555555555")


def resolution(*, archived: int = 0, favorite: int = 0, trashed: int = 0):
    total = 2
    return AssetSelectionResolution(
        ids=[ASSET_ONE, ASSET_TWO],
        missing_ids=[],
        summary=AssetSelectionSummary(
            total=total,
            archived=archived,
            unarchived=total - archived,
            favorite=favorite,
            not_favorite=total - favorite,
            trashed=trashed,
            not_trashed=total - trashed,
            archive_action="archive" if archived < total else "unarchive",
            favorite_action="favorite" if favorite < total else "unfavorite",
            can_trash=trashed < total,
            can_restore=trashed > 0,
        ),
    )


class FakeAssets:
    def __init__(
        self,
        current: AssetSelectionResolution,
        applicability: list[set[UUID]],
    ) -> None:
        self.current = current
        self.applicability = applicability
        self.relation_deltas: list[tuple[str, UUID, UUID, bool]] = []
        self.removed_batches: list[list[UUID]] = []

    async def resolve_selection(self, *_args, **_kwargs):
        return self.current

    async def applicable_action_ids(self, *_args, **_kwargs):
        return self.applicability.pop(0)

    async def stack_asset_ids(self, asset_id):
        return [asset_id]

    async def apply_membership_event(
        self, relation: str, relation_id: UUID, asset_id: UUID, present: bool
    ) -> None:
        self.relation_deltas.append((relation, relation_id, asset_id, present))

    async def remove_assets(self, asset_ids: list[UUID]) -> int:
        self.removed_batches.append(asset_ids)
        return len(asset_ids)


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
            relation_id=request.relation_ids[0] if len(request.relation_ids) == 1 else None,
            relation_ids=[str(identifier) for identifier in request.relation_ids],
            relation_work=relation_work,
            selection=request.selection.model_dump(mode="json"),
            target_ids=[str(identifier) for identifier in current.ids],
            target_digest=target_digest,
            applicable_ids=[str(identifier) for identifier in applicable_ids],
            skipped_ids=[str(identifier) for identifier in skipped_ids],
            missing_ids=[],
            destructive=operation == "trash",
            status="planned",
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        return self.record

    async def get_plan(self, _plan_id):
        return self.record

    async def claim_plan(self, _plan_id):
        assert self.record is not None
        if self.record.status != "planned":
            return None
        self.record.status = "running"
        return self.record

    async def finish_plan(self, _plan_id, status, result):
        assert self.record is not None
        self.record.status = status
        self.finished = (status, result)


class FakeImmich:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID | None, list[UUID]]] = []

    async def remove_assets_from_album(self, relation_id, ids):
        self.calls.append(("remove_album", relation_id, ids))

    async def add_assets_to_album(self, relation_id, ids):
        self.calls.append(("add_album", relation_id, ids))

    async def remove_assets_from_tag(self, relation_id, ids):
        self.calls.append(("remove_tag", relation_id, ids))

    async def add_assets_to_tag(self, relation_id, ids):
        self.calls.append(("add_tag", relation_id, ids))

    async def set_assets_archived(self, ids, value):
        self.calls.append(("archive" if value else "unarchive", None, ids))

    async def set_assets_favorite(self, ids, value):
        self.calls.append(("favorite" if value else "unfavorite", None, ids))

    async def trash_assets(self, ids):
        self.calls.append(("trash", None, ids))

    async def restore_assets(self, ids):
        self.calls.append(("restore", None, ids))

    async def list_stacks(self):
        return []

    async def create_stack(self, ids):
        self.calls.append(("stack", None, ids))

    async def delete_stack(self, stack_id):
        self.calls.append(("remove_stack", stack_id, []))


@pytest.mark.asyncio
async def test_stack_verification_retries_until_immich_indexes_the_primary(monkeypatch) -> None:
    class DelayedStackImmich(FakeImmich):
        def __init__(self) -> None:
            super().__init__()
            self.stack_round = 0

        async def list_stacks(self):
            self.stack_round += 1
            if self.stack_round < 3:
                return []
            return [SimpleNamespace(primary_asset_id=ASSET_ONE)]

    instance, _, _, _ = service(resolution(), [])
    instance._stacks._immich = DelayedStackImmich()  # type: ignore[assignment]
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("companion.stack_service.asyncio.sleep", sleep)

    assert await instance._stacks._creation_visible(ASSET_ONE) is True
    assert sleeps == [0.2, 0.2]


@pytest.mark.asyncio
async def test_stack_creation_accepts_filtered_children_after_primary_verification() -> None:
    class StackImmich(FakeImmich):
        primary_asset_id: UUID | None = None

        async def create_stack(self, ids):
            await super().create_stack(ids)
            self.primary_asset_id = ids[0]

        async def list_stacks(self):
            if self.primary_asset_id is None:
                return []
            # Immich may omit archived or trashed children from this response.
            return [SimpleNamespace(primary_asset_id=self.primary_asset_id, assets=[])]

    instance, actions, _, _ = service(
        resolution(),
        [{ASSET_ONE, ASSET_TWO}, {ASSET_ONE, ASSET_TWO}],
    )
    stack_immich = StackImmich()
    instance._immich = stack_immich  # type: ignore[assignment]
    instance._stacks._immich = stack_immich  # type: ignore[assignment]
    plan = await instance.plan(
        AssetActionPlanRequest(
            selection=AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO]),
            action="stack",
            stack_primary_asset_id=ASSET_TWO,
        )
    )

    assert plan.stack_primary_asset_id == ASSET_TWO
    result = await instance.execute(AssetActionExecuteRequest(plan_id=plan.id, confirm=True))

    assert result.status == "completed"
    assert result.applied_ids == [ASSET_TWO, ASSET_ONE]
    assert stack_immich.calls[0] == ("stack", None, [ASSET_TWO, ASSET_ONE])
    assert actions.finished is not None
    assert actions.finished[0] == "completed"


@pytest.mark.asyncio
async def test_stack_plan_rejects_a_primary_outside_the_resolved_selection() -> None:
    instance, _, _, _ = service(
        resolution(),
        [{ASSET_ONE, ASSET_TWO}],
    )

    with pytest.raises(ActionPlanConflictError, match="not part of the resolved selection"):
        await instance.plan(
            AssetActionPlanRequest(
                selection=AssetSelectionRequest(
                    mode="explicit",
                    ids=[ASSET_ONE, ASSET_TWO],
                ),
                action="stack",
                stack_primary_asset_id=RELATION_ID,
            )
        )


class FakeSync:
    def __init__(self) -> None:
        self.calls = 0

    async def synchronize(self):
        self.calls += 1


class RuntimeSettings:
    def __init__(self, batch_size: int = 50, delay: float = 0.2) -> None:
        self.value = SyncRuntimeSettings(
            full_batch_size=batch_size,
            full_min_batch_delay_seconds=delay,
        )

    async def get(self) -> SyncRuntimeSettings:
        return self.value


def service(current, applicability, *, destructive=True, runtime=None, sync=None):
    assets = FakeAssets(current, applicability)
    actions = FakeActions()
    immich = FakeImmich()
    sync = sync or FakeSync()
    instance = AssetActionService(
        Settings(allow_destructive_actions=destructive),
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        sync,  # type: ignore[arg-type]
        runtime,
    )
    return instance, actions, immich, sync


@pytest.mark.asyncio
async def test_large_actions_use_runtime_batches_and_pause_between_them(monkeypatch) -> None:
    asset_ids = [UUID(f"{index:08x}-0000-4000-8000-000000000000") for index in range(1, 52)]
    current = resolution().model_copy(update={"ids": asset_ids})
    all_ids = set(asset_ids)
    instance, _, immich, _ = service(
        current,
        [all_ids, all_ids, set()],
        runtime=RuntimeSettings(),
    )
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("companion.action_service.perf_counter", lambda: 3.0)
    monkeypatch.setattr("companion.action_service.asyncio.sleep", sleep)
    plan = await instance.plan(
        AssetActionPlanRequest(
            selection=AssetSelectionRequest(mode="explicit", ids=asset_ids),
            action="archive_toggle",
        )
    )

    result = await instance.execute(AssetActionExecuteRequest(plan_id=plan.id, confirm=True))

    assert [len(ids) for _, _, ids in immich.calls] == [50, 1]
    assert sleeps == [0.2]
    assert result.applied_count == 51


@pytest.mark.asyncio
async def test_mixed_state_chooses_only_archive_and_favorite_directions() -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])
    instance, _, _, _ = service(resolution(archived=1, favorite=1), [{ASSET_TWO}, {ASSET_TWO}])

    archive = await instance.plan(
        AssetActionPlanRequest(selection=selection, action="archive_toggle")
    )
    favorite = await instance.plan(
        AssetActionPlanRequest(selection=selection, action="favorite_toggle")
    )

    assert archive.operation == "archive"
    assert favorite.operation == "favorite"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    ["add_album", "add_tag", "remove_album", "remove_tag"],
)
async def test_relation_action_skips_assets_already_in_the_requested_state(
    action: str,
) -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])
    instance, actions, immich, sync = service(
        resolution(),
        [{ASSET_ONE}, {ASSET_ONE}, set()],
    )
    plan = await instance.plan(
        AssetActionPlanRequest(
            selection=selection,
            action=action,
            relation_ids=[RELATION_ID],
        )
    )

    assert plan.applicable_count == 1
    assert plan.skipped_count == 1
    result = await instance.execute(AssetActionExecuteRequest(plan_id=plan.id, confirm=True))

    assert immich.calls == [(action, RELATION_ID, [ASSET_ONE])]
    assert sync.calls == 1
    assert result.applied_count == 1
    assert result.skipped_count == 1
    assert result.applied_ids == [ASSET_ONE]
    assert result.skipped_ids == [ASSET_TWO]
    assert result.verified is True
    assert actions.finished is not None


@pytest.mark.asyncio
async def test_remove_stack_keeps_original_selection_digest_after_expansion() -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])
    instance, actions, _, sync = service(
        resolution(),
        [{ASSET_ONE, ASSET_TWO}, {ASSET_ONE, ASSET_TWO}, set()],
    )

    plan = await instance.plan(
        AssetActionPlanRequest(selection=selection, action="remove_stack")
    )
    result = await instance.execute(AssetActionExecuteRequest(plan_id=plan.id, confirm=True))

    assert result.verified is True
    assert actions.finished is not None
    assert sync.calls == 1
    assert actions.finished[0] == "completed"


@pytest.mark.asyncio
async def test_multi_relation_action_reports_and_verifies_each_relation() -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])
    instance, _, immich, sync = service(
        resolution(),
        [
            {ASSET_ONE},
            {ASSET_TWO},
            {ASSET_ONE},
            {ASSET_TWO},
            set(),
            set(),
        ],
    )
    plan = await instance.plan(
        AssetActionPlanRequest(
            selection=selection,
            action="add_album",
            relation_ids=[RELATION_ID, RELATION_TWO],
        )
    )

    assert plan.target_count == 2
    assert plan.applicable_count == 2
    assert plan.skipped_count == 2
    assert [relation.relation_id for relation in plan.relations] == [
        RELATION_ID,
        RELATION_TWO,
    ]

    result = await instance.execute(AssetActionExecuteRequest(plan_id=plan.id, confirm=True))

    assert immich.calls == [
        ("add_album", RELATION_ID, [ASSET_ONE]),
        ("add_album", RELATION_TWO, [ASSET_TWO]),
    ]
    assert sync.calls == 1
    assert result.applied_count == 2
    assert result.skipped_count == 2
    assert result.failed_ids == []
    assert len(result.relation_results) == 2


@pytest.mark.asyncio
async def test_uniform_true_state_chooses_only_unarchive_and_unfavorite() -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])
    instance, _, _, _ = service(
        resolution(archived=2, favorite=2),
        [{ASSET_ONE, ASSET_TWO}, {ASSET_ONE, ASSET_TWO}],
    )

    archive = await instance.plan(
        AssetActionPlanRequest(selection=selection, action="archive_toggle")
    )
    favorite = await instance.plan(
        AssetActionPlanRequest(selection=selection, action="favorite_toggle")
    )

    assert archive.operation == "unarchive"
    assert favorite.operation == "unfavorite"


@pytest.mark.asyncio
async def test_trash_is_rejected_when_destructive_actions_are_disabled() -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])
    instance, _, _, _ = service(resolution(), [], destructive=False)

    with pytest.raises(DestructiveActionsDisabledError):
        await instance.plan(AssetActionPlanRequest(selection=selection, action="trash"))


@pytest.mark.asyncio
async def test_successful_trash_removes_local_assets_without_targeted_sync() -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_TWO])
    selected = {ASSET_ONE, ASSET_TWO}
    instance, actions, immich, sync = service(
        resolution(),
        [selected, selected, set()],
    )

    plan = await instance.plan(AssetActionPlanRequest(selection=selection, action="trash"))
    result = await instance.execute(AssetActionExecuteRequest(plan_id=plan.id, confirm=True))

    assert immich.calls == [("trash", None, [ASSET_ONE, ASSET_TWO])]
    assert instance._assets.removed_batches == [[ASSET_ONE, ASSET_TWO]]
    assert sync.calls == 0
    assert result.applied_ids == [ASSET_ONE, ASSET_TWO]
    assert result.verified is True
    assert actions.finished is not None
    assert actions.finished[0] == "completed"

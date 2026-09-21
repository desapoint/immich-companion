"""Permanent trash deletion planning, execution, and verification regressions."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from companion.config import Settings
from companion.immich import ImmichApiError
from companion.trash_purge_service import (
    TrashPurgeExecuteRequest,
    TrashPurgeSelection,
    TrashPurgeService,
)

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")


class FakeImmich:
    def __init__(self) -> None:
        self.trashed = {ASSET_ONE, ASSET_TWO}
        self.permanent_calls: list[list[UUID]] = []
        self.empty_calls = 0

    async def iter_trashed_assets(self):
        for asset_id in sorted(self.trashed):
            yield SimpleNamespace(id=asset_id, is_trashed=True)

    async def get_asset(self, asset_id: UUID):
        if asset_id not in self.trashed:
            raise ImmichApiError("get asset", 404)
        return SimpleNamespace(id=asset_id, is_trashed=True)

    async def permanently_delete_assets(self, asset_ids: list[UUID]) -> None:
        self.permanent_calls.append(list(asset_ids))
        self.trashed.difference_update(asset_ids)

    async def empty_trash(self) -> int:
        self.empty_calls += 1
        count = len(self.trashed)
        self.trashed.clear()
        return count


class FakeActions:
    def __init__(self) -> None:
        self.record = None
        self.finished: list[tuple[str, dict[str, object]]] = []

    async def create_trash_purge_plan(self, **values):
        self.record = SimpleNamespace(
            id=uuid4(),
            operation="purge_trash",
            status="planned",
            expires_at=values["expires_at"],
            relation_work={
                "mode": values["mode"],
                "target_count": values["target_count"],
            },
            target_ids=[str(value) for value in values["target_ids"]],
            target_digest=values["target_digest"],
            result=None,
            executed_at=None,
        )
        return self.record

    async def get_plan(self, _plan_id):
        return self.record

    async def claim_trash_purge_plan(self, _plan_id):
        if self.record is None or self.record.status not in {"planned", "running"}:
            return None
        now = datetime.now(UTC)
        if self.record.status == "running" and (
            self.record.executed_at is None
            or self.record.executed_at > now - timedelta(minutes=5)
        ):
            return None
        self.record.status = "running"
        self.record.executed_at = now
        self.record.result = {
            **(self.record.result or {}),
            "purge_lease_token": str(uuid4()),
        }
        return self.record

    async def checkpoint_trash_purge_plan(self, _plan_id, result, *, lease_token):
        if lease_token != self.record.result.get("purge_lease_token"):
            raise ValueError("stale lease")
        self.record.result = {**(self.record.result or {}), **result}
        self.record.executed_at = datetime.now(UTC)

    async def finish_trash_purge_plan(self, _plan_id, status, result, *, lease_token):
        if self.record.result.get("purge_lease_token") != lease_token:
            return False
        await self.finish_plan(_plan_id, status, result)
        return True

    async def finish_plan(self, _plan_id, status, result):
        assert self.record is not None
        self.record.status = status
        self.finished.append((status, result))


def settings() -> Settings:
    return Settings(
        allow_destructive_actions=True,
        action_plan_ttl_seconds=900,
        action_max_targets=100,
        sync_full_batch_size=50,
    )


@pytest.mark.asyncio
async def test_selected_trash_assets_are_force_deleted_and_verified() -> None:
    immich = FakeImmich()
    actions = FakeActions()
    service = TrashPurgeService(immich, actions, settings())

    plan = await service.plan(TrashPurgeSelection(ids=[ASSET_ONE]))
    result = await service.execute(
        TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True)
    )

    assert plan.mode == "selected"
    assert immich.permanent_calls == [[ASSET_ONE]]
    assert result.deleted_ids == [ASSET_ONE]
    assert result.deleted == 1
    assert result.verified is True
    assert ASSET_TWO in immich.trashed


@pytest.mark.asyncio
async def test_complete_trash_uses_immich_empty_endpoint_after_drift_check() -> None:
    immich = FakeImmich()
    actions = FakeActions()
    service = TrashPurgeService(immich, actions, settings())

    plan = await service.plan(TrashPurgeSelection(all=True))
    result = await service.execute(
        TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True)
    )

    assert plan.mode == "empty_all"
    assert plan.target_count == 2
    assert len(actions.record.target_digest) == 64
    assert immich.empty_calls == 1
    assert result.deleted == 2
    assert result.verified is True
    assert result.deleted_ids == []


@pytest.mark.asyncio
async def test_selective_all_with_exclusions_uses_force_delete() -> None:
    immich = FakeImmich()
    actions = FakeActions()
    service = TrashPurgeService(immich, actions, settings())

    plan = await service.plan(
        TrashPurgeSelection(all=True, excluded_ids=[ASSET_TWO])
    )
    await service.execute(TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True))

    assert plan.mode == "selected"
    assert immich.permanent_calls == [[ASSET_ONE]]
    assert immich.trashed == {ASSET_TWO}


@pytest.mark.asyncio
async def test_successful_force_delete_does_not_depend_on_follow_up_asset_reads() -> None:
    class NoPostDeleteReadsImmich(FakeImmich):
        async def get_asset(self, asset_id: UUID):
            if self.permanent_calls:
                raise AssertionError("successful deletion must not require a follow-up read")
            return await super().get_asset(asset_id)

    immich = NoPostDeleteReadsImmich()
    actions = FakeActions()
    service = TrashPurgeService(immich, actions, settings())

    plan = await service.plan(TrashPurgeSelection(ids=[ASSET_ONE, ASSET_TWO]))
    result = await service.execute(
        TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True)
    )

    assert result.deleted_ids == [ASSET_ONE, ASSET_TWO]
    assert result.failed_ids == []
    assert result.deleted == 2
    assert result.verified is True


@pytest.mark.asyncio
async def test_failed_force_delete_is_verified_for_partial_provider_success() -> None:
    class PartiallyDeletingImmich(FakeImmich):
        async def permanently_delete_assets(self, asset_ids: list[UUID]) -> None:
            self.permanent_calls.append(list(asset_ids))
            self.trashed.discard(asset_ids[0])
            raise ImmichApiError("permanently delete assets", 500)

    immich = PartiallyDeletingImmich()
    actions = FakeActions()
    service = TrashPurgeService(immich, actions, settings())

    plan = await service.plan(TrashPurgeSelection(ids=[ASSET_ONE, ASSET_TWO]))
    result = await service.execute(
        TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True)
    )

    assert result.deleted_ids == [ASSET_ONE]
    assert result.failed_ids == [ASSET_TWO]
    assert result.deleted == 1
    assert result.verified is False
    assert result.status == "partial"


@pytest.mark.asyncio
async def test_resume_reconciles_mutation_that_crashed_before_checkpoint() -> None:
    immich = FakeImmich()
    actions = FakeActions()
    service = TrashPurgeService(immich, actions, settings())
    plan = await service.plan(TrashPurgeSelection(ids=[ASSET_ONE, ASSET_TWO]))

    original_checkpoint = actions.checkpoint_trash_purge_plan
    calls = 0

    async def crash_after_provider_mutation(plan_id, result, *, lease_token):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("crash before durable checkpoint")
        await original_checkpoint(plan_id, result, lease_token=lease_token)

    actions.checkpoint_trash_purge_plan = crash_after_provider_mutation
    with pytest.raises(RuntimeError):
        await service.execute(TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True))

    actions.checkpoint_trash_purge_plan = original_checkpoint
    actions.record.executed_at = datetime.now(UTC) - timedelta(minutes=6)
    result = await service.execute(
        TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True)
    )

    assert result.deleted_ids == [ASSET_ONE, ASSET_TWO]
    assert immich.permanent_calls == [[ASSET_ONE, ASSET_TWO]]


@pytest.mark.asyncio
async def test_resume_reconciles_after_verification_interruption() -> None:
    class VerificationCrashImmich(FakeImmich):
        async def permanently_delete_assets(self, asset_ids: list[UUID]) -> None:
            self.permanent_calls.append(list(asset_ids))
            self.trashed.difference_update(asset_ids)
            raise ImmichApiError("provider timeout", 500)

        async def get_asset(self, asset_id: UUID):
            if self.permanent_calls and not self.trashed:
                raise RuntimeError("verification interrupted")
            return await super().get_asset(asset_id)

    immich = VerificationCrashImmich()
    actions = FakeActions()
    service = TrashPurgeService(immich, actions, settings())
    plan = await service.plan(TrashPurgeSelection(ids=[ASSET_ONE, ASSET_TWO]))
    with pytest.raises(RuntimeError):
        await service.execute(TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True))

    actions.record.executed_at = datetime.now(UTC) - timedelta(minutes=6)
    # The provider mutation happened despite verification failing; resume reads state
    # before retrying and therefore does not issue a second mutation.
    immich.get_asset = FakeImmich.get_asset.__get__(immich, VerificationCrashImmich)
    result = await service.execute(TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True))
    assert result.deleted == 2
    assert immich.permanent_calls == [[ASSET_ONE, ASSET_TWO]]


@pytest.mark.asyncio
async def test_resume_reconstructs_result_after_finalization_interruption() -> None:
    class FinalizationCrashActions(FakeActions):
        def __init__(self) -> None:
            super().__init__()
            self.fail_finish = True

        async def finish_plan(self, plan_id, status, result):
            if self.fail_finish:
                self.fail_finish = False
                raise RuntimeError("finalization interrupted")
            await super().finish_plan(plan_id, status, result)

    immich = FakeImmich()
    actions = FinalizationCrashActions()
    service = TrashPurgeService(immich, actions, settings())
    plan = await service.plan(TrashPurgeSelection(ids=[ASSET_ONE, ASSET_TWO]))
    with pytest.raises(RuntimeError):
        await service.execute(TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True))

    actions.record.executed_at = datetime.now(UTC) - timedelta(minutes=6)
    result = await service.execute(TrashPurgeExecuteRequest(plan_id=plan.id, confirm=True))
    assert result.deleted_ids == [ASSET_ONE, ASSET_TWO]
    assert immich.permanent_calls == [[ASSET_ONE, ASSET_TWO]]


@pytest.mark.asyncio
async def test_running_claim_requires_a_stale_lease() -> None:
    actions = FakeActions()
    actions.record = SimpleNamespace(
        id=uuid4(),
        operation="purge_trash",
        status="running",
        executed_at=datetime.now(UTC),
        result={"purge_lease_token": "old"},
    )
    assert await actions.claim_trash_purge_plan(actions.record.id) is None
    actions.record.executed_at = datetime.now(UTC) - timedelta(minutes=6)
    claimed = await actions.claim_trash_purge_plan(actions.record.id)
    assert claimed is actions.record
    new_token = actions.record.result["purge_lease_token"]
    with pytest.raises(ValueError):
        await actions.checkpoint_trash_purge_plan(
            actions.record.id, {}, lease_token="old"
        )
    assert await actions.finish_trash_purge_plan(
        actions.record.id, "completed", {}, lease_token="old"
    ) is False
    await actions.checkpoint_trash_purge_plan(
        actions.record.id, {}, lease_token=new_token
    )

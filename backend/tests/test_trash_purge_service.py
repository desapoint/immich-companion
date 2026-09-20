"""Permanent trash deletion planning, execution, and verification regressions."""

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
        )
        return self.record

    async def get_plan(self, _plan_id):
        return self.record

    async def claim_trash_purge_plan(self, _plan_id):
        if self.record is None or self.record.status != "planned":
            return None
        self.record.status = "running"
        return self.record

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

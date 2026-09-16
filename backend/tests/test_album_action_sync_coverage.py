"""Album action coverage tests for global-sync-aware reconciliation."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from companion.action_service import AssetActionService
from companion.config import Settings

ALBUM_ID = UUID("44444444-4444-4444-8444-444444444444")
ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ASSET_THREE = UUID("33333333-3333-4333-8333-333333333333")


class FakeImmich:
    def __init__(self) -> None:
        self.added: list[list[UUID]] = []

    async def add_assets_to_album(self, _album_id: UUID, asset_ids: list[UUID]) -> None:
        self.added.append(asset_ids)


class FakeAssets:
    def __init__(self, members: set[UUID] | None = None) -> None:
        self.members = set(members or set())
        self.membership_events: list[tuple[str, UUID, UUID, bool]] = []

    async def applicable_action_ids(
        self,
        operation: str,
        target_ids: list[UUID],
        _relation_id: UUID | None = None,
    ) -> set[UUID]:
        if operation == "add_album":
            return {asset_id for asset_id in target_ids if asset_id not in self.members}
        if operation == "remove_album":
            return {asset_id for asset_id in target_ids if asset_id in self.members}
        return set(target_ids)

    async def apply_membership_event(
        self,
        relation: str,
        relation_id: UUID,
        asset_id: UUID,
        present: bool,
    ) -> None:
        self.membership_events.append((relation, relation_id, asset_id, present))
        if present:
            self.members.add(asset_id)
        else:
            self.members.discard(asset_id)


class FakeActions:
    def __init__(self) -> None:
        self.finished = None

    async def finish_plan(self, _plan_id, status, result) -> None:
        self.finished = (status, result)


class CoveringSync:
    def __init__(self, covered: bool) -> None:
        self.covered = covered
        self.repair_calls: list[tuple[list[UUID], list[tuple[str, UUID]] | None]] = []

    async def album_reconciliation_will_cover(self, _album_ids: list[UUID]) -> bool:
        return self.covered

    async def reconcile_targets(
        self,
        asset_ids: list[UUID],
        relations: list[tuple[str, UUID]] | None = None,
        include_stacks: bool = False,
    ) -> None:
        assert include_stacks is False
        self.repair_calls.append((asset_ids, relations))


class FakeRuntime:
    async def get(self):
        return SimpleNamespace(full_batch_size=50, full_min_batch_delay_seconds=0)


def make_service(assets: FakeAssets, sync: CoveringSync):
    actions = FakeActions()
    immich = FakeImmich()
    service = AssetActionService(
        Settings(),
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        actions,  # type: ignore[arg-type]
        sync,  # type: ignore[arg-type]
        FakeRuntime(),
    )
    return service, actions, immich


def record(target_ids: list[UUID]):
    return SimpleNamespace(
        id=uuid4(),
        relation_ids=[str(ALBUM_ID)],
        target_ids=[str(asset_id) for asset_id in target_ids],
    )


@pytest.mark.asyncio
async def test_upcoming_global_album_pass_applies_local_delta_without_extra_repair() -> None:
    assets = FakeAssets()
    sync = CoveringSync(True)
    service, actions, immich = make_service(assets, sync)

    result = await service._execute_relations(
        record([ASSET_ONE, ASSET_TWO]),
        "add_album",
        [ASSET_ONE, ASSET_TWO],
        batch_size=50,
        throttle=False,
    )

    assert immich.added == [[ASSET_ONE, ASSET_TWO]]
    assert assets.membership_events == [
        ("album", ALBUM_ID, ASSET_ONE, True),
        ("album", ALBUM_ID, ASSET_TWO, True),
    ]
    assert sync.repair_calls == []
    assert result.status == "completed"
    assert result.verified is True
    assert actions.finished is not None


@pytest.mark.asyncio
async def test_fallback_repair_receives_only_assets_that_actually_changed() -> None:
    assets = FakeAssets({ASSET_THREE})
    sync = CoveringSync(False)
    service, _, immich = make_service(assets, sync)

    await service._execute_relations(
        record([ASSET_ONE, ASSET_TWO, ASSET_THREE]),
        "add_album",
        [ASSET_ONE, ASSET_TWO, ASSET_THREE],
        batch_size=50,
        throttle=False,
    )

    assert immich.added == [[ASSET_ONE, ASSET_TWO]]
    assert sync.repair_calls == [
        ([ASSET_ONE, ASSET_TWO], [("album", ALBUM_ID)])
    ]

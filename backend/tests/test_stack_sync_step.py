"""First-class stack synchronization step behavior."""

from uuid import UUID

import pytest

from companion.immich import ImmichStack, ImmichStackAsset
from companion.synchronization.evidence import SyncAuthority
from companion.synchronization.scopes import StackScope
from companion.synchronization.selections import (
    AffectedAssetsSelection,
    AllSelection,
    ExplicitIdsSelection,
)
from companion.synchronization.steps import (
    StackSyncStep,
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
)

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
STACK_ONE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
STACK_TWO = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
STACK_THREE = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def stack_asset(identifier: UUID, filename: str) -> ImmichStackAsset:
    return ImmichStackAsset.model_validate(
        {
            "id": str(identifier),
            "type": "IMAGE",
            "originalFileName": filename,
            "originalMimeType": "image/jpeg",
            "width": 100,
            "height": 80,
            "fileCreatedAt": "2026-09-25T10:00:00Z",
        }
    )


def stack(identifier: UUID, primary: UUID, *members: UUID) -> ImmichStack:
    return ImmichStack(
        id=identifier,
        primaryAssetId=primary,
        assets=[stack_asset(member, f"{member}.jpg") for member in members],
    )


class FakeImmich:
    def __init__(self, stacks: list[ImmichStack]) -> None:
        self.stacks = stacks
        self.stream_calls = 0
        self.list_calls = 0

    async def iter_stacks(self):
        self.stream_calls += 1
        for current in self.stacks:
            yield current

    async def list_stacks(self):
        self.list_calls += 1
        return self.stacks


class ListOnlyImmich:
    def __init__(self, stacks: list[ImmichStack]) -> None:
        self.stacks = stacks
        self.list_calls = 0

    async def list_stacks(self):
        self.list_calls += 1
        return self.stacks


class FakeAssets:
    def __init__(self) -> None:
        self.batches: list[list[tuple[dict[str, object], list[UUID]]]] = []
        self.generations: list[int] = []

    async def apply_stack_batch(self, batch, generation):
        self.batches.append(list(batch))
        self.generations.append(generation)
        return sum(len(asset_ids) for _, asset_ids in batch)


class CountingStackStep(StackSyncStep):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.paces = 0

    async def pace(self, _context, _started) -> None:
        self.paces += 1


@pytest.mark.asyncio
async def test_manual_all_stack_scope_streams_batches_and_emits_complete_evidence() -> None:
    stacks = [
        stack(STACK_ONE, ASSET_ONE, ASSET_ONE),
        stack(STACK_TWO, ASSET_TWO, ASSET_TWO),
        stack(STACK_THREE, ASSET_ONE, ASSET_ONE),
    ]
    immich = FakeImmich(stacks)
    assets = FakeAssets()
    checkpoints = []

    async def checkpoint(cursor, _counters, progress):
        checkpoints.append((cursor, progress.completed, progress.total, progress.detail))

    step = CountingStackStep(immich, assets)  # type: ignore[arg-type]
    result = await step.run(
        SyncStepContext(
            mode="full",
            generation=31,
            config=SyncStepConfig(
                batch_size=2,
                conditionals=SyncStepConditionals(enabled=False),
            ),
            manual=True,
            respect_conditionals=False,
            checkpoint_callback=checkpoint,
        ),
        StackScope(selection=AllSelection()),
    )

    assert result.completed == 3
    assert result.total is None
    assert result.counters == {"stacks_seen": 3, "stack_members": 3}
    assert result.evidence[0].domain == "stacks"
    assert result.evidence[0].authority == SyncAuthority.COMPLETE
    assert result.evidence[0].selection == AllSelection()
    assert immich.stream_calls == 1
    assert immich.list_calls == 0
    assert [len(batch) for batch in assets.batches] == [2, 1]
    assert assets.generations == [31, 31]
    assert step.paces == 1
    assert [item[0] for item in checkpoints] == [None, "stacks:1", "stacks:2"]
    assert all(item[2] is None for item in checkpoints)


@pytest.mark.asyncio
async def test_stack_step_resumes_from_existing_batch_cursor() -> None:
    stacks = [
        stack(STACK_ONE, ASSET_ONE, ASSET_ONE),
        stack(STACK_TWO, ASSET_TWO, ASSET_TWO),
        stack(STACK_THREE, ASSET_ONE, ASSET_ONE),
    ]
    immich = FakeImmich(stacks)
    assets = FakeAssets()

    result = await StackSyncStep(
        immich,
        assets,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="full",
            generation=32,
            config=SyncStepConfig(batch_size=1),
            counters={"stacks_seen": 1, "stack_members": 1},
            cursor="stacks:1",
        ),
        StackScope(selection=AllSelection()),
    )

    assert result.completed == 3
    assert [batch[0][0]["id"] for batch in assets.batches] == [
        str(STACK_TWO),
        str(STACK_THREE),
    ]


@pytest.mark.asyncio
async def test_stack_step_preserves_list_stacks_compatibility_fallback() -> None:
    immich = ListOnlyImmich([stack(STACK_ONE, ASSET_ONE, ASSET_ONE)])
    assets = FakeAssets()

    result = await StackSyncStep(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="full",
            generation=33,
            config=SyncStepConfig(batch_size=10),
        ),
        StackScope(selection=AllSelection()),
    )

    assert result.completed == 1
    assert immich.list_calls == 1
    assert len(assets.batches) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selection",
    [
        ExplicitIdsSelection(ids=[STACK_ONE]),
        AffectedAssetsSelection(
            assets=ExplicitIdsSelection(ids=[ASSET_ONE]),
        ),
    ],
)
async def test_targeted_stack_scopes_are_rejected_until_remote_semantics_are_safe(
    selection,
) -> None:
    immich = FakeImmich([])
    assets = FakeAssets()

    with pytest.raises(ValueError, match="complete stack traversal"):
        await StackSyncStep(
            immich,
            assets,  # type: ignore[arg-type]
        ).run(
            SyncStepContext(
                mode="full",
                generation=34,
                config=SyncStepConfig(batch_size=10),
                manual=True,
                respect_conditionals=False,
            ),
            StackScope(selection=selection),
        )

    assert immich.stream_calls == 0
    assert assets.batches == []


def test_stack_payload_excludes_trashed_members_but_keeps_observed_ids() -> None:
    active = stack_asset(ASSET_ONE, "active.jpg")
    trashed = stack_asset(ASSET_TWO, "trashed.jpg").model_copy(
        update={"is_trashed": True}
    )

    payload, observed_ids = StackSyncStep.stack_payload_from_members(
        STACK_ONE,
        ASSET_ONE,
        [active, trashed],
    )

    assert payload["assetCount"] == 1
    assert payload["assets"] == [
        {
            "id": str(ASSET_ONE),
            "type": "IMAGE",
            "originalFileName": "active.jpg",
            "originalMimeType": "image/jpeg",
            "width": 100,
            "height": 80,
            "fileCreatedAt": active.file_created_at.isoformat(),
        }
    ]
    assert observed_ids == [ASSET_ONE, ASSET_TWO]

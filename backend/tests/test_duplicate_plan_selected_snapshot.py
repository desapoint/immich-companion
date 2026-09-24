from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from companion.action_service import ActionPlanConflictError
from companion.duplicate_schema import DuplicateAnalysisOptions, DuplicateResolutionPlanRequest
from companion.duplicate_service import CrossSourceDuplicateService


class _Reviews:
    def __init__(
        self,
        asset_ids: list[object],
        dispositions: list[str] | None = None,
    ) -> None:
        dispositions = dispositions or ["keep"] * len(asset_ids)
        self._record = SimpleNamespace(
            member_fingerprint="fingerprint",
            member_decisions=[
                {
                    "asset_id": str(asset_id),
                    "disposition": disposition,
                    "source": "manual",
                    "status": "completed",
                }
                for asset_id, disposition in zip(asset_ids, dispositions, strict=True)
            ],
            stack_primary_asset_id=None,
            stack_resolution="move_selected",
            metadata_keeper_asset_id=None,
        )

    async def get_many(self, _source: str, keys: list[str]):
        return {key: self._record for key in keys}


class _Actions:
    async def create_duplicate_plan(
        self,
        *,
        groups: list[dict[str, object]],
        options: dict[str, object],
        target_digest: str,
        expires_at: datetime,
    ):
        return SimpleNamespace(
            id=uuid4(),
            status="planned",
            relation_work={"groups": groups, "options": options},
            target_digest=target_digest,
            expires_at=expires_at,
            destructive=False,
        )


def _service(
    group_ids: list[str],
    *,
    dispositions: list[str] | None = None,
    offline_member: bool = False,
    eligible: bool = True,
    status: str = "exact",
    discovery_source: str = "immich_duplicate",
    provider_group_id: str | None = None,
) -> tuple[CrossSourceDuplicateService, list[object]]:
    asset_count = len(dispositions) if dispositions is not None else 2
    asset_ids = [uuid4() for _ in range(asset_count)]
    members = [
        SimpleNamespace(id=asset_id, is_offline=offline_member and index == 1)
        for index, asset_id in enumerate(asset_ids)
    ]
    group = SimpleNamespace(
        group_id=group_ids[0],
        auto_resolvable=False,
        discovery_source=discovery_source,
        stable_group_key="stable-key",
        member_set_key="member-set-key",
        member_fingerprint="fingerprint",
        provider_group_id=(
            provider_group_id
            if provider_group_id is not None
            else str(uuid4())
            if discovery_source == "immich_duplicate"
            else None
        ),
        members=members,
        eligible=eligible,
        status=status,
        effective_action="none",
        effective_primary_asset_id=None,
        keeper_asset_id=None,
    )

    service = CrossSourceDuplicateService.__new__(CrossSourceDuplicateService)
    service._reviews = _Reviews(asset_ids, dispositions)
    service._actions = _Actions()
    service._settings = SimpleNamespace(action_plan_ttl_seconds=300)
    service._stacks = None
    service._groups_by_ids = AsyncMock(return_value=[SimpleNamespace(group_id=group_ids[0])])
    service._snapshot_groups = AsyncMock(
        return_value=([], {}, {}, SimpleNamespace(groups=[group]))
    )
    service._relation_snapshot = AsyncMock(return_value=({}, "relations"))
    service.result = AsyncMock(
        side_effect=AssertionError("selected-group planning hydrated the full duplicate universe")
    )
    service.workspace = AsyncMock(
        return_value=SimpleNamespace(selected_group_ids=list(group_ids))
    )
    return service, asset_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("workspace_selected", [False, True])
async def test_plan_hydrates_only_selected_groups(workspace_selected: bool) -> None:
    group_id = "immich:review-target"
    service, _ = _service([group_id])
    request = DuplicateResolutionPlanRequest(
        options=DuplicateAnalysisOptions(analyze_automatically=False),
        group_ids=[] if workspace_selected else [group_id],
        workspace_selected=workspace_selected,
    )

    plan = await service.plan(request)

    service._groups_by_ids.assert_awaited_once_with([group_id])
    service._snapshot_groups.assert_awaited_once()
    service.result.assert_not_awaited()
    assert plan.group_count == 1
    assert plan.groups[0].group_id == group_id
    assert {member.disposition for member in plan.groups[0].members} == {"keep"}


@pytest.mark.asyncio
async def test_reviewed_immich_delete_allows_offline_member() -> None:
    group_id = "immich:offline-review-target"
    service, asset_ids = _service(
        [group_id],
        dispositions=["keep", "delete"],
        offline_member=True,
        eligible=False,
        status="unverified",
    )

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            options=DuplicateAnalysisOptions(analyze_automatically=False),
            group_ids=[group_id],
        )
    )

    assert plan.group_count == 1
    assert plan.groups[0].keep_asset_ids == [asset_ids[0]]
    assert plan.groups[0].trash_asset_ids == [asset_ids[1]]


@pytest.mark.asyncio
async def test_reviewed_delete_allows_similarity_only_group_without_provider_id() -> None:
    group_id = "similarity:review-target"
    service, asset_ids = _service(
        [group_id],
        dispositions=["keep", "delete"],
        eligible=True,
        status="unverified",
        discovery_source="companion_similarity",
    )

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            options=DuplicateAnalysisOptions(analyze_automatically=False),
            group_ids=[group_id],
        )
    )

    assert plan.group_count == 1
    assert plan.groups[0].provider_group_id is None
    assert plan.groups[0].keep_asset_ids == [asset_ids[0]]
    assert plan.groups[0].trash_asset_ids == [asset_ids[1]]


@pytest.mark.asyncio
async def test_workspace_plan_preserves_multiple_saved_stack_partitions() -> None:
    group_id = "immich:multi-stack-review"
    service, asset_ids = _service(
        [group_id],
        dispositions=["stack", "stack", "stack", "stack"],
    )
    decisions = service._reviews._record.member_decisions
    for index, decision in enumerate(decisions):
        decision["stack_id"] = "pending-1" if index < 2 else "pending-2"
        decision["stack_primary"] = index in {0, 2}
        decision["stack_resolution"] = (
            "move_selected" if index == 0
            else "include_existing" if index == 2
            else None
        )

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            options=DuplicateAnalysisOptions(analyze_automatically=False),
            workspace_selected=True,
        )
    )

    assert len(plan.groups[0].follow_ups) == 2
    first, second = plan.groups[0].follow_ups
    assert set(first.member_asset_ids) == set(asset_ids[:2])
    assert first.primary_asset_id == asset_ids[0]
    assert first.resolution == "move_selected"
    assert set(second.member_asset_ids) == set(asset_ids[2:])
    assert second.primary_asset_id == asset_ids[2]
    assert second.resolution == "include_existing"


@pytest.mark.asyncio
async def test_workspace_plan_rejects_saved_incomplete_pending_stack() -> None:
    group_id = "immich:incomplete-stack-review"
    service, _ = _service(
        [group_id],
        dispositions=["stack", "keep"],
    )
    decision = service._reviews._record.member_decisions[0]
    decision.update(
        {
            "stack_id": "pending-1",
            "stack_primary": True,
            "stack_resolution": "move_selected",
        }
    )

    with pytest.raises(ActionPlanConflictError, match="fewer than two images"):
        await service.plan(
            DuplicateResolutionPlanRequest(
                options=DuplicateAnalysisOptions(analyze_automatically=False),
                workspace_selected=True,
            )
        )

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from companion.duplicate_schema import DuplicateAnalysisOptions, DuplicateResolutionPlanRequest
from companion.duplicate_service import CrossSourceDuplicateService


class _Reviews:
    def __init__(self, asset_ids: list[object]) -> None:
        self._record = SimpleNamespace(
            member_fingerprint="fingerprint",
            member_decisions=[
                {
                    "asset_id": str(asset_id),
                    "disposition": "keep",
                    "source": "manual",
                    "status": "completed",
                }
                for asset_id in asset_ids
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


def _service(group_ids: list[str]) -> tuple[CrossSourceDuplicateService, list[object]]:
    asset_ids = [uuid4(), uuid4()]
    members = [SimpleNamespace(id=asset_id, is_offline=False) for asset_id in asset_ids]
    group = SimpleNamespace(
        group_id=group_ids[0],
        auto_resolvable=False,
        discovery_source="immich_duplicate",
        stable_group_key="stable-key",
        member_set_key="member-set-key",
        member_fingerprint="fingerprint",
        provider_group_id=str(uuid4()),
        members=members,
        eligible=True,
        effective_action="none",
        effective_primary_asset_id=None,
        keeper_asset_id=None,
    )

    service = CrossSourceDuplicateService.__new__(CrossSourceDuplicateService)
    service._reviews = _Reviews(asset_ids)
    service._actions = _Actions()
    service._settings = SimpleNamespace(action_plan_ttl_seconds=300)
    service._stacks = None
    service._groups_by_ids = AsyncMock(return_value=[SimpleNamespace(group_id=group_ids[0])])
    service._snapshot_groups = AsyncMock(
        return_value=([], {}, {}, SimpleNamespace(groups=[group]))
    )
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

"""Frozen duplicate action-plan contract regressions."""

from copy import deepcopy
from uuid import UUID

import pytest

from companion.duplicate_schema import DuplicateResolutionPlanGroup

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")
D = UUID("44444444-4444-4444-8444-444444444444")


def mixed_plan_group() -> dict[str, object]:
    return {
        "group_id": "immich:test",
        "stable_group_key": "immich_duplicate:frozen-members",
        "member_set_key": "frozen-members",
        "discovery_source": "immich_duplicate",
        "provider_group_id": "55555555-5555-4555-8555-555555555555",
        "action": "mixed",
        "keeper_asset_id": str(A),
        "member_asset_ids": [str(A), str(B), str(C), str(D)],
        "keep_asset_ids": [str(A), str(B), str(C)],
        "trash_asset_ids": [str(D)],
        "follow_up": {
            "type": "stack",
            "primary_asset_id": str(B),
            "member_asset_ids": [str(B), str(C)],
        },
        "member_fingerprint": "frozen-members",
        "members": [
            {"asset_id": str(A), "disposition": "keep", "primary": True},
            {"asset_id": str(B), "disposition": "stack", "primary": True},
            {"asset_id": str(C), "disposition": "stack", "primary": False},
            {"asset_id": str(D), "disposition": "delete", "primary": False},
        ],
    }


def test_complete_member_partition_and_stack_follow_up_are_accepted() -> None:
    group = DuplicateResolutionPlanGroup.model_validate(mixed_plan_group())

    assert {member.asset_id for member in group.members} == {A, B, C, D}
    assert group.follow_up is not None
    assert set(group.follow_up.member_asset_ids) == {B, C}


def test_plan_requires_exactly_one_decision_for_every_frozen_member() -> None:
    payload = mixed_plan_group()
    payload["members"] = payload["members"][:-1]  # type: ignore[index]

    with pytest.raises(ValueError, match="one decision per frozen member"):
        DuplicateResolutionPlanGroup.model_validate(payload)


@pytest.mark.parametrize("invalid_disposition", ["keep", "no_change"])
def test_member_decisions_must_match_the_frozen_partition(
    invalid_disposition: str,
) -> None:
    payload = mixed_plan_group()
    payload["members"][-1]["disposition"] = invalid_disposition  # type: ignore[index]

    with pytest.raises(ValueError, match="match the frozen resolution partition"):
        DuplicateResolutionPlanGroup.model_validate(payload)


def test_group_action_must_match_complete_member_decisions() -> None:
    payload = mixed_plan_group()
    payload["action"] = "stack_all"

    with pytest.raises(ValueError, match="action must match its member decisions"):
        DuplicateResolutionPlanGroup.model_validate(payload)


def test_stack_follow_up_must_match_stack_decisions_and_primary() -> None:
    missing_member = mixed_plan_group()
    missing_member["follow_up"]["member_asset_ids"] = [str(B)]  # type: ignore[index]
    wrong_primary = deepcopy(mixed_plan_group())
    wrong_primary["follow_up"]["primary_asset_id"] = str(A)  # type: ignore[index]

    for payload in (missing_member, wrong_primary):
        with pytest.raises(ValueError, match="exactly match the frozen Stack decisions"):
            DuplicateResolutionPlanGroup.model_validate(payload)

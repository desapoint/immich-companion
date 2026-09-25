"""Plan-wide duplicate stack destination topology regression coverage."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.action_service import ActionPlanConflictError
from companion.duplicate_contracts import normalize_plan_group, stack_destination_id
from companion.duplicate_resolution import (
    _apply_stack_destination_overrides,
    _validate_stack_destination_topology,
)
from companion.duplicate_schema import DuplicateStackDestinationOverride

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")


def group(group_id: str, members: list[UUID], stack_ids: list[UUID]) -> dict:
    return {
        "group_id": group_id,
        "member_asset_ids": [str(value) for value in members],
        "members": [
            {
                "asset_id": str(value),
                "disposition": "stack" if value in stack_ids else "keep",
                "primary": value == stack_ids[0] if stack_ids else False,
            }
            for value in members
        ],
        "follow_up": None,
        "follow_ups": [],
    }


def member(asset_id: UUID):
    return SimpleNamespace(
        id=asset_id,
        file_modified_at=SimpleNamespace(isoformat=lambda: "2026-09-24T00:00:00"),
        file_size_bytes=100,
    )


def test_plan_wide_validation_rejects_asset_in_two_distinct_destinations() -> None:
    groups = [
        {
            **group("g1", [A, B], [A, B]),
            "follow_ups": [{
                "type": "stack",
                "destination_id": "d1",
                "source_group_ids": ["g1"],
                "primary_asset_id": str(A),
                "member_asset_ids": [str(A), str(B)],
            }],
        },
        {
            **group("g2", [B, C], [B, C]),
            "follow_ups": [{
                "type": "stack",
                "destination_id": "d2",
                "source_group_ids": ["g2"],
                "primary_asset_id": str(B),
                "member_asset_ids": [str(B), str(C)],
            }],
        },
    ]

    with pytest.raises(ActionPlanConflictError, match="multiple proposed"):
        _validate_stack_destination_topology(groups)


def test_plan_wide_validation_allows_one_shared_destination_across_groups() -> None:
    shared = {
        "type": "stack",
        "destination_id": "merged",
        "source_group_ids": ["g1", "g2"],
        "primary_asset_id": str(A),
        "member_asset_ids": [str(A), str(B), str(C)],
    }
    groups = [
        {**group("g1", [A, B], [A, B]), "follow_ups": [dict(shared)]},
        {**group("g2", [B, C], [B, C]), "follow_ups": [dict(shared)]},
    ]

    _validate_stack_destination_topology(groups)


def test_plan_wide_validation_rejects_delete_vs_stack() -> None:
    groups = [
        {
            **group("g1", [A, B], [A, B]),
            "follow_ups": [{
                "type": "stack",
                "destination_id": "d1",
                "source_group_ids": ["g1"],
                "primary_asset_id": str(A),
                "member_asset_ids": [str(A), str(B)],
            }],
        },
        {
            **group("g2", [A, C], []),
            "members": [
                {"asset_id": str(A), "disposition": "delete", "primary": False},
                {"asset_id": str(C), "disposition": "keep", "primary": True},
            ],
        },
    ]

    with pytest.raises(ActionPlanConflictError, match="deleted"):
        _validate_stack_destination_topology(groups)


def test_reviewed_destination_merges_overlapping_group_stacks() -> None:
    groups = [
        group("g1", [A, B], [A, B]),
        group("g2", [B, C], [B, C]),
    ]
    assets = {value: member(value) for value in [A, B, C]}

    _apply_stack_destination_overrides(
        groups,
        [
            DuplicateStackDestinationOverride(
                destination_id="merged",
                source_group_ids=["g1", "g2"],
                primary_asset_id=A,
                member_asset_ids=[A, B, C],
            )
        ],
        assets,
    )

    assert groups[0]["follow_ups"][0]["destination_id"] == "merged"
    assert groups[1]["follow_ups"][0]["destination_id"] == "merged"
    assert groups[0]["follow_ups"][0]["member_asset_ids"] == [str(A), str(B), str(C)]
    assert groups[1]["follow_ups"][0]["source_group_ids"] == ["g1", "g2"]



def test_internal_destination_id_is_bounded_for_long_group_ids() -> None:
    group_id = "companion:appearance-normalized-v1:6:8:a546bb2e720b:linked:cohesion-4:" + ":".join(
        str(value)
        for value in [
            A,
            B,
            C,
            UUID("44444444-4444-4444-8444-444444444444"),
            UUID("55555555-5555-4555-8555-555555555555"),
            UUID("66666666-6666-4666-8666-666666666666"),
            UUID("77777777-7777-4777-8777-777777777777"),
        ]
    )

    destination_id = stack_destination_id(group_id, 0)

    assert len(destination_id) <= 256
    assert destination_id.startswith("duplicate-stack:")


def test_normalized_stack_follow_up_uses_bounded_destination_id() -> None:
    group_id = "companion:" + ("very-long-group:" * 40)
    normalized = normalize_plan_group(
        {
            "group_id": group_id,
            "stable_group_key": "stable",
            "member_set_key": "members",
            "discovery_source": "companion_similarity",
            "action": "stack_all",
            "keeper_asset_id": str(A),
            "member_asset_ids": [str(A), str(B)],
            "keep_asset_ids": [str(A), str(B)],
            "trash_asset_ids": [],
            "follow_up": {
                "type": "stack",
                "primary_asset_id": str(A),
                "member_asset_ids": [str(A), str(B)],
            },
            "member_fingerprint": "members",
            "members": [
                {"asset_id": str(A), "disposition": "stack", "primary": True},
                {"asset_id": str(B), "disposition": "stack", "primary": False},
            ],
        }
    )

    assert len(normalized["follow_ups"][0]["destination_id"]) <= 256

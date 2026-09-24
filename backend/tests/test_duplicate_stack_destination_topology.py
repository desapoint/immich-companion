"""Plan-wide duplicate stack destination topology regression coverage."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.action_service import ActionPlanConflictError
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

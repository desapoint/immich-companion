from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.contained_duplicate_resolution import (
    CONTAINED_BY_GROUP_IDS,
    EXECUTION_TRASH_ASSET_IDS,
    _execution_duplicate_groups,
    _expand_contained_duplicate_groups,
    _has_contained_resolution_steps,
)

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")
D = UUID("44444444-4444-4444-8444-444444444444")
E = UUID("55555555-5555-4555-8555-555555555555")
F = UUID("66666666-6666-4666-8666-666666666666")
X = UUID("99999999-9999-4999-8999-999999999999")


def _parent(name: str, members: list[UUID], keeper: UUID) -> dict[str, object]:
    return {
        "group_id": name,
        "stable_group_key": f"stable-{name}",
        "member_set_key": f"members-{name}",
        "discovery_source": "companion_similarity",
        "provider_group_id": f"provider-{name}",
        "action": "resolve",
        "keeper_asset_id": str(keeper),
        "member_asset_ids": [str(asset_id) for asset_id in members],
        "keep_asset_ids": [str(keeper)],
        "trash_asset_ids": [str(asset_id) for asset_id in members if asset_id != keeper],
        "metadata_work": None,
        "follow_up": None,
        "execution_state": "pending",
        "member_fingerprint": f"fingerprint-{name}",
        "members": [
            {
                "asset_id": str(asset_id),
                "disposition": "keep" if asset_id == keeper else "delete",
                "primary": asset_id == keeper,
            }
            for asset_id in members
        ],
    }


def _candidate(name: str):
    return SimpleNamespace(
        group_id=name,
        provider_group_id=f"provider-{name}",
        stable_group_key=f"stable-{name}",
        member_fingerprint=f"fingerprint-{name}",
    )


def test_contained_immich_groups_execute_before_similarity_parent_leftovers() -> None:
    parent = _parent("companion:parent", [A, B, C, D, E, F], F)
    child_one = _candidate("immich:one")
    child_two = _candidate("immich:two")
    partial = _candidate("immich:partial")

    expanded = _expand_contained_duplicate_groups(
        [parent],
        [child_one, child_two, partial],
        {
            "immich:one": [A, B, C],
            "immich:two": [D, E],
            "immich:partial": [E, X],
        },
    )

    assert [group["group_id"] for group in expanded] == [
        "immich:one",
        "immich:two",
        "companion:parent",
    ]
    assert expanded[0]["keeper_asset_id"] == str(A)
    assert expanded[0]["trash_asset_ids"] == [str(B), str(C)]
    assert expanded[1]["keeper_asset_id"] == str(D)
    assert expanded[1]["trash_asset_ids"] == [str(E)]
    assert expanded[0][CONTAINED_BY_GROUP_IDS] == ["companion:parent"]
    assert expanded[1][CONTAINED_BY_GROUP_IDS] == ["companion:parent"]

    # The reviewed parent partition stays intact for audit/public preview.
    assert expanded[2]["trash_asset_ids"] == [str(A), str(B), str(C), str(D), str(E)]
    # Only the two temporary child keepers are left for the parent to resolve.
    assert expanded[2][EXECUTION_TRASH_ASSET_IDS] == [str(A), str(D)]

    execution = _execution_duplicate_groups(expanded)
    assert execution[0]["trash_asset_ids"] == [str(B), str(C)]
    assert execution[1]["trash_asset_ids"] == [str(E)]
    assert execution[2]["trash_asset_ids"] == [str(A), str(D)]


def test_contained_group_preserves_similarity_keeper_when_it_is_inside_child() -> None:
    parent = _parent("companion:parent", [A, B, C, D, E], B)
    child = _candidate("immich:child")

    expanded = _expand_contained_duplicate_groups(
        [parent],
        [child],
        {"immich:child": [A, B, C]},
    )

    assert expanded[0]["keeper_asset_id"] == str(B)
    assert expanded[0]["trash_asset_ids"] == [str(A), str(C)]
    assert expanded[1][EXECUTION_TRASH_ASSET_IDS] == [str(D), str(E)]


def test_partial_immich_overlap_is_not_promoted_to_child_resolution() -> None:
    parent = _parent("companion:parent", [A, B, C, D], D)
    partial = _candidate("immich:partial")

    expanded = _expand_contained_duplicate_groups(
        [parent],
        [partial],
        {"immich:partial": [C, X]},
    )

    assert [group["group_id"] for group in expanded] == ["companion:parent"]
    assert expanded[0][EXECUTION_TRASH_ASSET_IDS] == [str(A), str(B), str(C)]
    assert not _has_contained_resolution_steps(expanded)


def test_explicit_contained_resolve_becomes_a_required_parent_dependency() -> None:
    parent = _parent("companion:parent", [A, B, C, D], D)
    explicit_child = {
        **_parent("immich:child", [A, B], A),
        "discovery_source": "immich_duplicate",
        "trash_asset_ids": [str(B)],
    }

    expanded = _expand_contained_duplicate_groups(
        [parent, explicit_child],
        [],
        {},
    )

    assert expanded[0][CONTAINED_BY_GROUP_IDS] == ["companion:parent"]
    assert expanded[1][EXECUTION_TRASH_ASSET_IDS] == [str(A), str(C)]
    assert _has_contained_resolution_steps(expanded)


def test_conflicting_parent_keepers_inside_one_child_are_rejected() -> None:
    first = _parent("companion:first", [A, B, C], A)
    second = _parent("companion:second", [A, B, D], B)
    child = _candidate("immich:child")

    with pytest.raises(ValueError, match="incompatible keepers"):
        _expand_contained_duplicate_groups(
            [first, second],
            [child],
            {"immich:child": [A, B]},
        )

from uuid import UUID

from companion.duplicate_service import (
    _contained_native_resolution,
    _metadata_keeper_for_plan,
)

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")
GROUP = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


def test_similarity_multiple_survivors_do_not_merge_metadata() -> None:
    assert (
        _metadata_keeper_for_plan(
            [A, B],
            [C],
        )
        is None
    )


def test_similarity_single_survivor_is_metadata_target() -> None:
    assert (
        _metadata_keeper_for_plan(
            [A],
            [B, C],
        )
        == A
    )


def test_no_deletions_do_not_create_metadata_target() -> None:
    assert _metadata_keeper_for_plan([A, B], []) is None


def test_multiple_survivors_never_create_metadata_target() -> None:
    assert _metadata_keeper_for_plan([A, B], [C]) is None


def test_contained_immich_single_keeper_builds_native_resolution() -> None:
    resolution = _contained_native_resolution(
        {
            "discovery_source": "immich_duplicate",
            "provider_group_id": str(GROUP),
            "keep_asset_ids": [str(A)],
            "trash_asset_ids": [str(B), str(C)],
            "contained_by_group_ids": ["companion:parent"],
        }
    )

    assert resolution is not None
    assert resolution.duplicate_id == GROUP
    assert resolution.keep_asset_ids == [A]
    assert resolution.trash_asset_ids == [B, C]


def test_non_contained_immich_group_keeps_companion_execution_path() -> None:
    assert (
        _contained_native_resolution(
            {
                "discovery_source": "immich_duplicate",
                "provider_group_id": str(GROUP),
                "keep_asset_ids": [str(A)],
                "trash_asset_ids": [str(B)],
            }
        )
        is None
    )


def test_contained_immich_multiple_keepers_do_not_use_native_merge() -> None:
    assert (
        _contained_native_resolution(
            {
                "discovery_source": "immich_duplicate",
                "provider_group_id": str(GROUP),
                "keep_asset_ids": [str(A), str(B)],
                "trash_asset_ids": [str(C)],
                "contained_by_group_ids": ["companion:parent"],
            }
        )
        is None
    )

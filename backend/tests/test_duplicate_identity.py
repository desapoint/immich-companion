"""Stable duplicate identity regressions."""

from uuid import UUID

from companion.duplicate_identity import member_set_key, stable_group_key

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")


def test_member_set_identity_is_order_independent() -> None:
    assert member_set_key([A, B]) == member_set_key([B, A])


def test_changed_membership_creates_a_new_identity() -> None:
    assert member_set_key([A, B]) != member_set_key([A, B, C])


def test_stable_group_identity_is_provider_scoped_not_scan_scoped() -> None:
    members = member_set_key([A, B])

    assert stable_group_key("companion_similarity", members) == stable_group_key(
        "companion_similarity", members
    )
    assert stable_group_key("companion_similarity", members) != stable_group_key(
        "immich_duplicate", members
    )

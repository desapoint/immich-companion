"""Regression coverage for reviewed duplicate delete eligibility."""

from types import SimpleNamespace

from companion.duplicate_service import _reviewed_immich_delete_supported


def group(
    *,
    discovery_source: str = "immich_duplicate",
    provider_group_id: str | None = "provider-group",
    status: str = "unverified",
    member_count: int = 2,
):
    return SimpleNamespace(
        discovery_source=discovery_source,
        provider_group_id=provider_group_id,
        status=status,
        members=[SimpleNamespace(is_offline=True) for _ in range(member_count)],
    )


def test_reviewed_immich_delete_supports_offline_members() -> None:
    assert _reviewed_immich_delete_supported(group())


def test_reviewed_delete_stays_bound_to_immich_duplicate_groups() -> None:
    assert not _reviewed_immich_delete_supported(
        group(discovery_source="companion_similarity", provider_group_id=None)
    )
    assert not _reviewed_immich_delete_supported(group(provider_group_id=None))
    assert not _reviewed_immich_delete_supported(group(status="ineligible"))
    assert not _reviewed_immich_delete_supported(group(member_count=1))

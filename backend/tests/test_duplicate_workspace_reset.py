"""Regressions for bounded duplicate workspace decision clearing."""

from types import SimpleNamespace

import pytest

from companion.action_service import ActionPlanConflictError
from companion.duplicate_schema import DuplicateWorkspaceResetRequest
from companion.duplicate_service import CrossSourceDuplicateService
from companion.group_decision import DiscoverySource


class IdentityDiscovery:
    def __init__(self, identities: list[SimpleNamespace]) -> None:
        self.identities = identities
        self.calls: list[tuple[list[str] | None, list[str] | None]] = []

    async def resolve_identities(
        self,
        *,
        group_ids: list[str] | None = None,
        stable_group_keys: list[str] | None = None,
    ) -> list[SimpleNamespace]:
        self.calls.append((group_ids, stable_group_keys))
        return self.identities


class ReviewRepository:
    def __init__(self) -> None:
        self.cleared: list[tuple[str, list[str]]] = []
        self.consumed: tuple[list[str], list[str]] | None = None

    async def clear_decisions(
        self,
        discovery_source: str,
        stable_group_keys: list[str],
    ) -> None:
        self.cleared.append((discovery_source, stable_group_keys))

    async def consume_workspace_groups(
        self,
        stable_group_keys: list[str],
        legacy_group_ids: list[str],
    ) -> None:
        self.consumed = (stable_group_keys, legacy_group_ids)


def service_with(
    discovery: IdentityDiscovery,
    reviews: ReviewRepository,
) -> CrossSourceDuplicateService:
    service = object.__new__(CrossSourceDuplicateService)
    service._discovery = discovery
    service._reviews = reviews
    return service


@pytest.mark.asyncio
async def test_reset_workspace_decisions_uses_targeted_identity_resolution() -> None:
    group_id = "immich:group-1"
    identity = SimpleNamespace(
        group_id=group_id,
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        stable_group_key="stable:group-1",
    )
    discovery = IdentityDiscovery([identity])
    reviews = ReviewRepository()
    service = service_with(discovery, reviews)
    restored_workspace = object()

    async def full_result(*args, **kwargs):
        raise AssertionError("workspace reset must not materialize the full duplicate result")

    async def workspace(*args, **kwargs):
        return restored_workspace

    service.result = full_result  # type: ignore[method-assign]
    service.workspace = workspace  # type: ignore[method-assign]

    result = await service.reset_workspace_decisions(
        DuplicateWorkspaceResetRequest(group_ids=[group_id])
    )

    assert result is restored_workspace
    assert discovery.calls == [([group_id], None)]
    assert reviews.cleared == [("immich_duplicate", ["stable:group-1"])]
    assert reviews.consumed == (["stable:group-1"], [group_id])


@pytest.mark.asyncio
async def test_reset_workspace_decisions_rejects_missing_target_without_full_result() -> None:
    group_id = "immich:missing"
    discovery = IdentityDiscovery([])
    reviews = ReviewRepository()
    service = service_with(discovery, reviews)

    async def full_result(*args, **kwargs):
        raise AssertionError("missing targeted identity must not trigger full discovery")

    service.result = full_result  # type: ignore[method-assign]

    with pytest.raises(ActionPlanConflictError, match="no longer available"):
        await service.reset_workspace_decisions(
            DuplicateWorkspaceResetRequest(group_ids=[group_id])
        )

    assert discovery.calls == [([group_id], None)]
    assert reviews.cleared == []
    assert reviews.consumed is None

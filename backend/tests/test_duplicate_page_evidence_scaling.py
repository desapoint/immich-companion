"""Duplicate page evidence lookup scaling regressions."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.discovery import DiscoveredGroup, DiscoveryEvidence
from companion.duplicate_evidence import DuplicateEvidenceMixin
from companion.group_decision import DiscoverySource
from companion.similarity_repository import canonical_pair

SCAN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


class RecordingScanEvidence:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, list[tuple[UUID, UUID]], dict[UUID, str]]] = []

    async def pair_evidence_for_pairs(
        self,
        scan_id: UUID,
        pairs: list[tuple[UUID, UUID]],
        *,
        source_identities: dict[UUID, str] | None = None,
    ):
        self.calls.append((scan_id, list(pairs), dict(source_identities or {})))
        return {}

    async def pair_evidence(self, *_args, **_kwargs):
        raise AssertionError("duplicate page should use exact pair lookup")


def similarity_group(member_count: int) -> DiscoveredGroup:
    assets = tuple(
        SimpleNamespace(id=UUID(int=index + 1))
        for index in range(member_count)
    )
    return DiscoveredGroup(
        group_id=f"companion:large:{member_count}",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id=f"scan:{member_count}",
        assets=assets,
        discovery_evidence=(
            DiscoveryEvidence(
                discovery_source=DiscoverySource.COMPANION_SIMILARITY,
                provider_group_id=f"scan:{member_count}",
                metadata={"scan_id": str(SCAN_ID)},
            ),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("member_count", [100, 500, 1000])
async def test_page_scan_evidence_work_scales_with_members_not_all_pairs(
    member_count: int,
) -> None:
    group = similarity_group(member_count)
    scan_evidence = RecordingScanEvidence()
    service = SimpleNamespace(_scan_evidence=scan_evidence)
    features = {
        asset.id: SimpleNamespace(source_identity=f"source:{asset.id}")
        for asset in group.assets
    }

    result = await DuplicateEvidenceMixin._persisted_scan_edges(
        service,
        [group],
        features,
        {},
    )

    assert result == {}
    assert len(scan_evidence.calls) == 1
    scan_id, requested_pairs, source_identities = scan_evidence.calls[0]
    assert scan_id == SCAN_ID
    assert len(requested_pairs) == member_count - 1
    reference_id = group.assets[0].id
    assert {
        canonical_pair(left, right) for left, right in requested_pairs
    } == {
        canonical_pair(reference_id, member.id)
        for member in group.assets[1:]
    }
    assert len(requested_pairs) < member_count * (member_count - 1) // 2
    assert len(source_identities) == member_count

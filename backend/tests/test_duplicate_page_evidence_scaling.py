"""Duplicate page evidence lookup scaling regressions."""

from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from companion.discovery import DiscoveredGroup, DiscoveryEvidence
from companion.duplicate_evidence import DuplicateEvidenceMixin
from companion.group_decision import DiscoverySource
from companion.similarity_repository import canonical_pair
from companion.similarity_scan_repository import (
    SIMILARITY_SCAN_READ_BATCH_SIZE,
    SimilarityScanRepository,
)

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


class EmptyScalarResult:
    def all(self):
        return []


class RecordingSession:
    def __init__(self) -> None:
        self.statements = []

    async def get(self, _model, _identifier):
        return SimpleNamespace(
            status="completed",
            pair_evidence_pruned_at=None,
            model_version="appearance-v1",
            feature_version=1,
            comparison_version=1,
        )

    async def scalars(self, statement):
        self.statements.append(statement)
        return EmptyScalarResult()


class RecordingSessions:
    def __init__(self, session: RecordingSession) -> None:
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False


class RecordingDatabase:
    def __init__(self, session: RecordingSession) -> None:
        self.sessions = RecordingSessions(session)


@pytest.mark.asyncio
async def test_exact_pair_repository_lookup_is_batched_and_pair_scoped() -> None:
    session = RecordingSession()
    repository = SimilarityScanRepository(RecordingDatabase(session))
    pair_count = SIMILARITY_SCAN_READ_BATCH_SIZE + 1
    pairs = [
        (UUID(int=1), UUID(int=index + 2))
        for index in range(pair_count)
    ]

    result = await repository.pair_evidence_for_pairs(SCAN_ID, pairs)

    assert result == {}
    assert len(session.statements) == 2
    for statement in session.statements:
        sql = " ".join(
            str(statement.compile(dialect=postgresql.dialect())).split()
        )
        assert (
            "(similarity_scan_pairs.asset_id_low, "
            "similarity_scan_pairs.asset_id_high) IN"
        ) in sql

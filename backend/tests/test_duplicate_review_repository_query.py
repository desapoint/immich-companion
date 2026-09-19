from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from companion.duplicate_review_repository import (
    DuplicateReviewRepository,
    _normalized_metadata_keeper_asset_id,
)

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")


class _EmptyScalarResult:
    def all(self):
        return []


class _CaptureSession:
    def __init__(self) -> None:
        self.statements = []

    async def scalars(self, statement):
        self.statements.append(statement)
        return _EmptyScalarResult()


@pytest.mark.asyncio
async def test_contained_group_candidate_query_avoids_distinct_json_rows() -> None:
    session = _CaptureSession()
    repository = DuplicateReviewRepository(None)

    frozen = await repository._freeze_contained_immich_groups(
        session,
        [{A, B}],
        datetime.now(UTC),
    )

    assert frozen == 0
    assert len(session.statements) == 1
    sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    normalized = " ".join(sql.upper().split())
    assert "SELECT DISTINCT" not in normalized
    assert " IN (SELECT " in normalized
    assert "COMPOSITE_DUPLICATE_GROUP_MEMBERS.GROUP_ID" in normalized


def _decision(asset_id: UUID, disposition: str) -> dict[str, str]:
    return {"asset_id": str(asset_id), "disposition": disposition}


def test_metadata_keeper_is_sole_survivor_of_complete_destructive_draft() -> None:
    assert _normalized_metadata_keeper_asset_id(
        [_decision(A, "keep"), _decision(B, "delete"), _decision(C, "delete")],
        "completed",
    ) == A


def test_metadata_keeper_is_none_with_multiple_survivors() -> None:
    assert _normalized_metadata_keeper_asset_id(
        [_decision(A, "keep"), _decision(B, "stack"), _decision(C, "delete")],
        "completed",
    ) is None


def test_metadata_keeper_is_none_without_deletions() -> None:
    assert _normalized_metadata_keeper_asset_id(
        [_decision(A, "keep"), _decision(B, "keep")],
        "completed",
    ) is None


def test_metadata_keeper_is_none_for_partial_draft() -> None:
    assert _normalized_metadata_keeper_asset_id(
        [_decision(A, "keep"), _decision(B, "delete")],
        "pending",
    ) is None

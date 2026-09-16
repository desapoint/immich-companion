from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from companion.duplicate_review_repository import DuplicateReviewRepository

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")


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

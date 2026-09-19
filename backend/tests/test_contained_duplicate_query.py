from uuid import UUID

from sqlalchemy.dialects import postgresql

from companion.composite_duplicate_repository import (
    CompositeDuplicateGroupMemberRecord,
    CompositeDuplicateGroupRecord,
)
from companion.contained_duplicate_resolution import _contained_candidate_statement


def test_contained_candidate_query_avoids_distinct_over_json_columns() -> None:
    member_ids = {
        UUID("11111111-1111-4111-8111-111111111111"),
        UUID("22222222-2222-4222-8222-222222222222"),
    }
    statement = _contained_candidate_statement(
        CompositeDuplicateGroupRecord,
        CompositeDuplicateGroupMemberRecord,
        member_ids,
        2,
    )

    sql = str(statement.compile(dialect=postgresql.dialect())).upper()

    assert "SELECT DISTINCT" not in sql
    assert "EXISTS (SELECT" in sql
    assert "PROVIDER_METADATA" in sql
    assert "SIMILARITY_VALIDATION" in sql

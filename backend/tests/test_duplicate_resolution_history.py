"""Regression coverage for clearing completed duplicate-resolution history."""

import asyncio
from types import SimpleNamespace
from uuid import UUID

from companion.duplicate_resolution_history import (
    clear_all_completed_resolutions,
    clear_completed_resolution,
)

TARGET_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
INHERITED_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
SHARED_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")
D = UUID("44444444-4444-4444-8444-444444444444")


class _AsyncContext:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _Session:
    def __init__(self, target, remaining, inherited):
        self.target = target
        self.scalar_reads = 0
        self.scalars_reads = 0
        self.remaining = remaining
        self.inherited = inherited
        self.deleted = []

    async def scalar(self, _statement):
        self.scalar_reads += 1
        return self.target

    async def scalars(self, _statement):
        self.scalars_reads += 1
        return _Scalars(self.remaining if self.scalars_reads == 1 else self.inherited)

    async def delete(self, record):
        self.deleted.append(record)

    def begin(self):
        return _AsyncContext()


class _BulkExecuteResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return _Scalars(self.values)


class _BulkSession:
    def __init__(self, removed_statuses):
        self.removed_statuses = removed_statuses
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _BulkExecuteResult(self.removed_statuses)

    def begin(self):
        return _AsyncContext()


class _Database:
    def __init__(self, session):
        self.session = session

    def sessions(self):
        return _AsyncContext(self.session)


def _review(identifier: UUID, *asset_ids: UUID, draft_status: str = "completed"):
    return SimpleNamespace(
        id=identifier,
        draft_status=draft_status,
        review_status="reviewed_resolve",
        member_decisions=[{"asset_id": str(asset_id)} for asset_id in asset_ids],
    )


def test_clear_resolution_removes_orphaned_inherited_suppression() -> None:
    target = _review(TARGET_ID, A, B, C)
    inherited = _review(INHERITED_ID, A, B, draft_status="inherited")
    session = _Session(target, [], [inherited])

    cleared = asyncio.run(clear_completed_resolution(_Database(session), TARGET_ID))

    assert cleared is True
    assert session.deleted == [inherited, target]


def test_clear_resolution_preserves_suppression_still_covered_by_other_history() -> None:
    target = _review(TARGET_ID, A, B, C)
    other = _review(OTHER_ID, A, B, D)
    shared = _review(SHARED_ID, A, B, draft_status="inherited")
    session = _Session(target, [other], [shared])

    cleared = asyncio.run(clear_completed_resolution(_Database(session), TARGET_ID))

    assert cleared is True
    assert session.deleted == [target]


def test_clear_resolution_does_not_touch_unrelated_inherited_rows() -> None:
    target = _review(TARGET_ID, A, B)
    unrelated = _review(INHERITED_ID, C, D, draft_status="inherited")
    session = _Session(target, [], [unrelated])

    cleared = asyncio.run(clear_completed_resolution(_Database(session), TARGET_ID))

    assert cleared is True
    assert session.deleted == [target]


def test_clear_resolution_returns_false_when_history_row_is_missing() -> None:
    session = _Session(None, [], [])

    cleared = asyncio.run(clear_completed_resolution(_Database(session), TARGET_ID))

    assert cleared is False
    assert session.deleted == []
    assert session.scalars_reads == 0


def test_clear_all_resolutions_uses_one_bulk_delete_and_counts_completed_rows() -> None:
    session = _BulkSession(["completed", "inherited", "completed"])

    cleared = asyncio.run(clear_all_completed_resolutions(_Database(session)))

    assert cleared == 2
    assert len(session.statements) == 1
    statement_sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "DELETE FROM duplicate_group_reviews" in statement_sql
    assert "draft_status = 'completed'" in statement_sql
    assert "draft_status = 'inherited'" in statement_sql
    assert "RETURNING duplicate_group_reviews.draft_status" in statement_sql


def test_clear_all_resolutions_removes_inherited_rows_when_history_is_empty() -> None:
    session = _BulkSession(["inherited", "inherited"])

    cleared = asyncio.run(clear_all_completed_resolutions(_Database(session)))

    assert cleared == 0
    assert len(session.statements) == 1

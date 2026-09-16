"""Regression coverage for durable duplicate-resolution lineage."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from companion.duplicate_identity import member_set_key, stable_group_key
from companion.duplicate_review_repository import (
    COMPANION_SIMILARITY_SOURCE,
    COVERAGE_PENDING_DRAFT_STATUS,
    DuplicateReviewRepository,
    _coverage_rows,
)

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")
D = UUID("44444444-4444-4444-8444-444444444444")
E = UUID("55555555-5555-4555-8555-555555555555")
NOW = datetime(2026, 9, 14, tzinfo=UTC)


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
    def __init__(self, completed):
        self.completed = completed
        self.executed = []

    async def scalars(self, _statement):
        return _Scalars(self.completed)

    async def execute(self, statement):
        self.executed.append(statement)

    def begin(self):
        return _AsyncContext()


class _Database:
    def __init__(self, completed):
        self.session = _Session(completed)

    def sessions(self):
        return _AsyncContext(self.session)


class _CompletionSession:
    def __init__(self, parent, coverage):
        self.parent = parent
        self.coverage = coverage
        self.coverage_reads = 0

    async def scalar(self, _statement):
        return self.parent

    async def scalars(self, _statement):
        self.coverage_reads += 1
        return _Scalars(self.coverage)

    def begin(self):
        return _AsyncContext()


class _CompletionDatabase:
    def __init__(self, parent, coverage):
        self.session = _CompletionSession(parent, coverage)

    def sessions(self):
        return _AsyncContext(self.session)


def _review(*asset_ids: UUID, source: str = "immich_duplicate"):
    return SimpleNamespace(
        discovery_source=source,
        member_decisions=[
            {
                "asset_id": str(asset_id),
                "disposition": "keep" if index == 0 else "delete",
                "source": "manual",
                "status": "completed",
            }
            for index, asset_id in enumerate(asset_ids)
        ],
        manual_action="resolve",
        manual_primary_asset_id=asset_ids[0],
        stack_primary_asset_id=None,
        stack_resolution="move_selected",
        metadata_keeper_asset_id=None,
        review_status="reviewed_resolve",
        last_reviewed_at=NOW,
        updated_at=NOW,
    )


def _coverage_review(*asset_ids: UUID):
    return SimpleNamespace(
        discovery_source="immich_duplicate",
        member_decisions=[
            {
                "asset_id": str(asset_id),
                "disposition": "no_change",
                "primary": False,
                "status": "pending",
            }
            for asset_id in asset_ids
        ],
        draft_status=COVERAGE_PENDING_DRAFT_STATUS,
        review_status="pending",
        last_reviewed_at=None,
        updated_at=NOW,
    )


def _group(*asset_ids: UUID, source: str = "immich_duplicate"):
    return SimpleNamespace(
        discovery_source=source,
        provider_group_id="provider-group",
        group_id="group",
        asset_ids=asset_ids,
        evidence=(),
    )


def _coverage_group(name: str):
    return SimpleNamespace(
        group_id=name,
        provider_group_id=f"provider-{name}",
        stable_group_key=f"stable-{name}",
        member_fingerprint=f"fingerprint-{name}",
    )


def _repository(*reviews):
    database = _Database(list(reviews))
    repository = DuplicateReviewRepository(database)

    async def no_exact_reviews(_source, _keys):
        return {}

    repository.get_many = no_exact_reviews  # type: ignore[method-assign]
    return repository, database


def test_deleted_member_keeps_resolved_group_suppressed() -> None:
    repository, database = _repository(_review(A, B, C))

    inherited = asyncio.run(repository.inherit_completed_groups([_group(A, B)]))

    assert inherited == 1
    assert len(database.session.executed) == 1


def test_provider_change_keeps_same_resolved_lineage_suppressed() -> None:
    repository, database = _repository(_review(A, B, C, source="immich_duplicate"))

    inherited = asyncio.run(
        repository.inherit_completed_groups(
            [_group(A, B, source="companion_similarity")]
        )
    )

    assert inherited == 1
    assert len(database.session.executed) == 1


def test_new_member_reopens_previously_resolved_group() -> None:
    repository, database = _repository(_review(A, B, C))

    inherited = asyncio.run(repository.inherit_completed_groups([_group(A, B, D)]))

    assert inherited == 0
    assert database.session.executed == []


def test_separately_resolved_groups_are_not_union_suppressed() -> None:
    repository, database = _repository(_review(A, B), _review(C, D))

    inherited = asyncio.run(repository.inherit_completed_groups([_group(A, B, C, D)]))

    assert inherited == 0
    assert database.session.executed == []


def test_similarity_coverage_freezes_only_fully_contained_immich_groups() -> None:
    contained = _coverage_group("contained")
    partial = _coverage_group("partial")

    rows = _coverage_rows(
        [contained, partial],
        {
            "contained": [A, B],
            "partial": [D, E],
        },
        [{A, B, C, D}],
        NOW,
    )

    assert [row["stable_group_key"] for row in rows] == ["stable-contained"]
    assert rows[0]["draft_status"] == COVERAGE_PENDING_DRAFT_STATUS
    assert [decision["asset_id"] for decision in rows[0]["member_decisions"]] == [
        str(A),
        str(B),
    ]


def test_similarity_completion_consumes_only_fully_contained_frozen_groups() -> None:
    parent = _review(A, B, C, D, source=COMPANION_SIMILARITY_SOURCE)
    parent.draft_status = "completed"
    contained = _coverage_review(A, B)
    partial = _coverage_review(D, E)
    database = _CompletionDatabase(parent, [contained, partial])
    repository = DuplicateReviewRepository(database)

    asyncio.run(
        repository.complete_draft(
            COMPANION_SIMILARITY_SOURCE,
            "similarity-parent",
            "fingerprint",
        )
    )

    assert contained.draft_status == "inherited"
    assert contained.review_status == "reviewed_resolve"
    assert all(decision["status"] == "completed" for decision in contained.member_decisions)
    assert partial.draft_status == COVERAGE_PENDING_DRAFT_STATUS
    assert partial.review_status == "pending"
    assert database.session.coverage_reads == 1


def test_coverage_placeholder_does_not_block_completed_lineage_inheritance() -> None:
    repository, database = _repository(_review(A, B, C))
    group = _group(A, B)
    group_key = stable_group_key("immich_duplicate", member_set_key([A, B]))
    placeholder = _coverage_review(A, B)

    async def coverage_exact_review(_source, _keys):
        return {group_key: placeholder}

    repository.get_many = coverage_exact_review  # type: ignore[method-assign]

    inherited = asyncio.run(repository.inherit_completed_groups([group]))

    assert inherited == 1
    assert len(database.session.executed) == 1

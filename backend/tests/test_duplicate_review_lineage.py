"""Regression coverage for durable duplicate-resolution lineage."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from companion.duplicate_review_repository import DuplicateReviewRepository

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")
D = UUID("44444444-4444-4444-8444-444444444444")
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


def _group(*asset_ids: UUID, source: str = "immich_duplicate"):
    return SimpleNamespace(
        discovery_source=source,
        provider_group_id="provider-group",
        group_id="group",
        asset_ids=asset_ids,
        evidence=(),
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

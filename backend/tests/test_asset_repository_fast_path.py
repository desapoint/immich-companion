"""Asset persistence timestamp fast-path regression coverage."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.asset_repository import AssetRepository
from companion.immich import ImmichAsset

ASSET_STABLE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_CHANGED = UUID("22222222-2222-4222-8222-222222222222")


def asset(
    identifier: UUID,
    *,
    updated_at: str | None,
    modified_at: str = "2026-09-28T12:00:00Z",
) -> ImmichAsset:
    payload: dict[str, object] = {
        "id": str(identifier),
        "type": "IMAGE",
        "originalFileName": f"{identifier}.jpg",
        "originalMimeType": "image/jpeg",
        "width": 100,
        "height": 100,
        "fileCreatedAt": "2026-09-27T12:00:00Z",
        "fileModifiedAt": modified_at,
    }
    if updated_at is not None:
        payload["updatedAt"] = updated_at
    return ImmichAsset.model_validate(payload)


class FakeSession:
    def __init__(self, rows):
        self.rows = list(rows)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        if len(self.statements) == 1:
            return list(self.rows)
        return SimpleNamespace(rowcount=0)

    @asynccontextmanager
    async def begin(self):
        yield self


class FakeSessions:
    def __init__(self, rows):
        self.session = FakeSession(rows)

    @asynccontextmanager
    async def __call__(self):
        yield self.session


@pytest.mark.asyncio
async def test_timestamp_stable_asset_only_bumps_generation() -> None:
    stable = asset(ASSET_STABLE, updated_at="2026-09-28T13:00:00Z")
    sessions = FakeSessions([
        (
            stable.id,
            "existing-fingerprint",
            4,
            stable.file_size_bytes,
            stable.file_modified_at,
            stable.updated_at,
        )
    ])
    repository = AssetRepository(SimpleNamespace(sessions=sessions))
    fingerprinted = []
    repository._fingerprint = lambda item: fingerprinted.append(item.id) or "unexpected"

    result = await repository.upsert_asset_batch(
        [stable],
        generation=5,
        track_similarity_changes=False,
    )

    assert result == (0, 0, 1)
    assert fingerprinted == []
    assert len(sessions.session.statements) == 2
    assert sessions.session.statements[1].is_update


@pytest.mark.asyncio
async def test_timestamp_change_uses_full_persistence_path() -> None:
    changed = asset(ASSET_CHANGED, updated_at="2026-09-28T14:00:00Z")
    sessions = FakeSessions([
        (
            changed.id,
            "old-fingerprint",
            4,
            changed.file_size_bytes,
            changed.file_modified_at,
            asset(ASSET_CHANGED, updated_at="2026-09-28T13:00:00Z").updated_at,
        )
    ])
    repository = AssetRepository(SimpleNamespace(sessions=sessions))
    fingerprinted = []
    repository._fingerprint = lambda item: fingerprinted.append(item.id) or "new-fingerprint"

    result = await repository.upsert_asset_batch(
        [changed],
        generation=5,
        track_similarity_changes=False,
    )

    assert result == (0, 1, 0)
    assert fingerprinted == [changed.id]
    assert len(sessions.session.statements) == 2
    assert sessions.session.statements[1].is_insert


@pytest.mark.asyncio
async def test_missing_updated_at_does_not_take_fast_path() -> None:
    ambiguous = asset(ASSET_STABLE, updated_at=None)
    sessions = FakeSessions([
        (
            ambiguous.id,
            "old-fingerprint",
            4,
            ambiguous.file_size_bytes,
            ambiguous.file_modified_at,
            None,
        )
    ])
    repository = AssetRepository(SimpleNamespace(sessions=sessions))
    fingerprinted = []
    repository._fingerprint = lambda item: fingerprinted.append(item.id) or "new-fingerprint"

    await repository.upsert_asset_batch(
        [ambiguous],
        generation=5,
        track_similarity_changes=False,
    )

    assert fingerprinted == [ambiguous.id]
    assert sessions.session.statements[1].is_insert

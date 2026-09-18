"""Regression coverage for bounded adaptive tag-sync writes."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.adaptive_tag_sync import reconcile_generation_asset_tags

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
TAG_ONE = UUID("33333333-3333-4333-8333-333333333333")
TAG_TWO = UUID("44444444-4444-4444-8444-444444444444")


@pytest.mark.asyncio
async def test_asset_oriented_tag_sync_batches_generation_writes_by_tag() -> None:
    class Immich:
        async def get_asset(self, asset_id: UUID):
            tags = (
                [{"id": str(TAG_ONE)}, {"id": str(TAG_TWO)}, {"id": str(TAG_ONE)}]
                if asset_id == ASSET_ONE
                else [{"id": str(TAG_ONE)}]
            )
            return SimpleNamespace(id=asset_id, includes_tags=True, tags=tags)

    class Repository:
        def __init__(self) -> None:
            self.replaced: list[tuple[UUID, list[UUID]]] = []
            self.upserted: list[tuple[UUID, list[UUID], int]] = []

        async def replace_asset_tag_memberships(self, asset_id: UUID, tag_ids: list[UUID]):
            self.replaced.append((asset_id, tag_ids))

        async def upsert_tag_memberships(
            self, tag_id: UUID, asset_ids: list[UUID], generation: int
        ) -> int:
            self.upserted.append((tag_id, asset_ids, generation))
            return len(asset_ids)

    repository = Repository()
    result = await reconcile_generation_asset_tags(
        Immich(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        [ASSET_ONE, ASSET_TWO],
        generation=17,
        concurrency=2,
    )

    assert result == (3, 2, 0)
    assert repository.replaced == [
        (ASSET_ONE, [TAG_ONE, TAG_TWO]),
        (ASSET_TWO, [TAG_ONE]),
    ]
    assert repository.upserted == [
        (TAG_ONE, [ASSET_ONE, ASSET_TWO], 17),
        (TAG_TWO, [ASSET_ONE], 17),
    ]

"""Configurable V2 sync-step behavior."""

from uuid import UUID

import pytest

from companion.immich import ImmichAlbum, ImmichTag
from companion.sync_steps import (
    CatalogSyncInput,
    CatalogSyncStep,
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
)

ALBUM_ONE = UUID("11111111-1111-4111-8111-111111111111")
ALBUM_TWO = UUID("22222222-2222-4222-8222-222222222222")
TAG_ONE = UUID("33333333-3333-4333-8333-333333333333")


def album(identifier: UUID, name: str) -> ImmichAlbum:
    return ImmichAlbum(
        id=identifier,
        albumName=name,
        assetCount=0,
        createdAt="2026-09-07T12:00:00Z",
        updatedAt="2026-09-07T12:00:00Z",
    )


def tag(identifier: UUID, name: str) -> ImmichTag:
    return ImmichTag(id=identifier, name=name, value=name, color=None, assetCount=0)


class FakeAssets:
    def __init__(self) -> None:
        self.album_batches: list[list[UUID]] = []
        self.tag_batches: list[list[UUID]] = []

    async def upsert_album_catalog(self, items, _generation: int) -> tuple[int, int]:
        self.album_batches.append([item.id for item in items])
        return len(items), 0

    async def upsert_tag_catalog(self, items, _generation: int) -> tuple[int, int]:
        self.tag_batches.append([item.id for item in items])
        return 0, len(items)


@pytest.mark.asyncio
async def test_catalog_step_reports_processed_and_total() -> None:
    assets = FakeAssets()
    progress: list[tuple[str | None, int, int | None, float | None]] = []

    async def checkpoint(cursor, _counters, current) -> None:
        progress.append((cursor, current.completed, current.total, current.percent))

    context = SyncStepContext(
        mode="full",
        generation=7,
        config=SyncStepConfig(batch_size=1, concurrency=3),
        checkpoint_callback=checkpoint,
    )
    result = await CatalogSyncStep(assets).run(
        context,
        CatalogSyncInput(
            albums=[album(ALBUM_ONE, "One"), album(ALBUM_TWO, "Two")],
            tags=[tag(TAG_ONE, "Review")],
        ),
    )

    assert result.skipped is False
    assert result.completed == 3
    assert result.total == 3
    assert result.counters["albums_seen"] == 2
    assert result.counters["tags_seen"] == 1
    assert assets.album_batches == [[ALBUM_ONE], [ALBUM_TWO]]
    assert assets.tag_batches == [[TAG_ONE]]
    assert progress[-1] == (None, 3, 3, 100.0)


@pytest.mark.asyncio
async def test_catalog_step_resumes_from_existing_cursor() -> None:
    assets = FakeAssets()
    context = SyncStepContext(
        mode="full",
        generation=8,
        config=SyncStepConfig(batch_size=1),
        counters={"albums_seen": 1, "tags_seen": 0},
        cursor="albums:1",
    )

    result = await CatalogSyncStep(assets).run(
        context,
        CatalogSyncInput(
            albums=[album(ALBUM_ONE, "One"), album(ALBUM_TWO, "Two")],
            tags=[tag(TAG_ONE, "Review")],
        ),
    )

    assert result.completed == 3
    assert assets.album_batches == [[ALBUM_TWO]]
    assert assets.tag_batches == [[TAG_ONE]]


@pytest.mark.asyncio
async def test_manual_step_can_bypass_normal_conditionals() -> None:
    assets = FakeAssets()
    data = CatalogSyncInput(albums=[album(ALBUM_ONE, "One")], tags=[])
    config = SyncStepConfig(
        batch_size=10,
        conditionals=SyncStepConditionals(enabled=False),
    )

    skipped = await CatalogSyncStep(assets).run(
        SyncStepContext(mode="full", generation=1, config=config),
        data,
    )
    assert skipped.skipped is True

    manual = await CatalogSyncStep(assets).run(
        SyncStepContext(
            mode="full",
            generation=1,
            config=config,
            manual=True,
            respect_conditionals=False,
        ),
        data,
    )
    assert manual.skipped is False
    assert manual.completed == 1


def test_standard_config_validates_operational_limits() -> None:
    with pytest.raises(ValueError, match="concurrency"):
        SyncStepConfig(concurrency=0)
    with pytest.raises(ValueError, match="batch_size"):
        SyncStepConfig(batch_size=0)
    with pytest.raises(ValueError, match="page_size"):
        SyncStepConfig(page_size=0)

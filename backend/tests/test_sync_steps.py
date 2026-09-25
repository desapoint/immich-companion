"""Configurable synchronization-step behavior."""

from uuid import UUID

import pytest

from companion.immich import ImmichAlbum, ImmichTag
from companion.synchronization.evidence import SyncAuthority
from companion.synchronization.scopes import CatalogScope
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    PersistedSelection,
)
from companion.synchronization.steps import (
    CatalogSyncStep,
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
)

ALBUM_ONE = UUID("11111111-1111-4111-8111-111111111111")
ALBUM_TWO = UUID("22222222-2222-4222-8222-222222222222")
TAG_ONE = UUID("33333333-3333-4333-8333-333333333333")
TAG_TWO = UUID("44444444-4444-4444-8444-444444444444")
SELECTION_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


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


class FakeImmich:
    def __init__(self) -> None:
        self.albums = [album(ALBUM_ONE, "One"), album(ALBUM_TWO, "Two")]
        self.tags = [tag(TAG_ONE, "Review"), tag(TAG_TWO, "Later")]
        self.calls: list[str] = []

    async def list_album_catalog(self):
        self.calls.append("albums")
        return self.albums

    async def list_tag_catalog(self):
        self.calls.append("tags")
        return self.tags


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


class FakeSelections:
    def __init__(self) -> None:
        self.album_batches: list[list[UUID]] = []
        self.tag_batches: list[list[UUID]] = []
        self.calls: list[tuple[str, int]] = []

    async def iter_album_ids(self, _selection, *, batch_size):
        self.calls.append(("albums", batch_size))
        for batch in self.album_batches:
            yield batch

    async def iter_tag_ids(self, _selection, *, batch_size):
        self.calls.append(("tags", batch_size))
        for batch in self.tag_batches:
            yield batch


@pytest.mark.asyncio
async def test_catalog_step_reports_processed_and_total() -> None:
    immich = FakeImmich()
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
    result = await CatalogSyncStep(immich, assets).run(
        context,
        CatalogScope(albums=AllSelection(), tags=AllSelection()),
    )

    assert result.skipped is False
    assert result.completed == 4
    assert result.total == 4
    assert result.counters["albums_seen"] == 2
    assert result.counters["tags_seen"] == 2
    assert assets.album_batches == [[ALBUM_ONE], [ALBUM_TWO]]
    assert assets.tag_batches == [[TAG_ONE], [TAG_TWO]]
    assert set(immich.calls) == {"albums", "tags"}
    assert {item.domain for item in result.evidence} == {"albums", "tags"}
    assert {item.authority for item in result.evidence} == {SyncAuthority.COMPLETE}
    assert progress[-1] == (None, 4, 4, 100.0)


@pytest.mark.asyncio
async def test_catalog_step_resumes_from_existing_cursor() -> None:
    immich = FakeImmich()
    assets = FakeAssets()
    context = SyncStepContext(
        mode="full",
        generation=8,
        config=SyncStepConfig(batch_size=1),
        counters={"albums_seen": 1, "tags_seen": 0},
        cursor="albums:1",
    )

    result = await CatalogSyncStep(immich, assets).run(
        context,
        CatalogScope(albums=AllSelection(), tags=ExplicitIdsSelection(ids=[TAG_ONE])),
    )

    assert result.completed == 3
    assert assets.album_batches == [[ALBUM_TWO]]
    assert assets.tag_batches == [[TAG_ONE]]


@pytest.mark.asyncio
async def test_catalog_step_supports_album_only_scope_without_loading_tags() -> None:
    immich = FakeImmich()
    assets = FakeAssets()

    result = await CatalogSyncStep(immich, assets).run(
        SyncStepContext(
            mode="full",
            generation=9,
            config=SyncStepConfig(batch_size=10),
        ),
        CatalogScope(albums=AllSelection(), tags=None),
    )

    assert result.completed == 2
    assert immich.calls == ["albums"]
    assert assets.album_batches == [[ALBUM_ONE, ALBUM_TWO]]
    assert assets.tag_batches == []


@pytest.mark.asyncio
async def test_catalog_step_supports_explicit_tag_only_scope() -> None:
    immich = FakeImmich()
    assets = FakeAssets()

    result = await CatalogSyncStep(immich, assets).run(
        SyncStepContext(
            mode="full",
            generation=10,
            config=SyncStepConfig(batch_size=10),
        ),
        CatalogScope(
            albums=None,
            tags=ExplicitIdsSelection(ids=[TAG_TWO, TAG_TWO]),
        ),
    )

    assert result.completed == 1
    assert immich.calls == ["tags"]
    assert assets.album_batches == []
    assert assets.tag_batches == [[TAG_TWO]]
    assert result.evidence[0].domain == "tags"
    assert result.evidence[0].authority == SyncAuthority.SELECTED


@pytest.mark.asyncio
async def test_catalog_step_supports_persisted_album_selection_via_resolver() -> None:
    immich = FakeImmich()
    assets = FakeAssets()
    selections = FakeSelections()
    selections.album_batches = [[ALBUM_TWO]]

    result = await CatalogSyncStep(
        immich,
        assets,
        selections,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="full",
            generation=11,
            config=SyncStepConfig(batch_size=1),
        ),
        CatalogScope(
            albums=PersistedSelection(selection_id=SELECTION_ID),
            tags=None,
        ),
    )

    assert result.completed == 1
    assert selections.calls == [("albums", 1)]
    assert assets.album_batches == [[ALBUM_TWO]]
    assert immich.calls == ["albums"]


@pytest.mark.asyncio
async def test_catalog_step_requires_resolver_for_persisted_selection() -> None:
    immich = FakeImmich()

    with pytest.raises(ValueError, match="requires SyncSelectionResolver"):
        await CatalogSyncStep(immich, FakeAssets()).run(
            SyncStepContext(
                mode="full",
                generation=12,
                config=SyncStepConfig(batch_size=10),
            ),
            CatalogScope(
                albums=PersistedSelection(selection_id=SELECTION_ID),
                tags=None,
            ),
        )


@pytest.mark.asyncio
async def test_manual_step_can_bypass_normal_conditionals() -> None:
    immich = FakeImmich()
    assets = FakeAssets()
    scope = CatalogScope(
        albums=ExplicitIdsSelection(ids=[ALBUM_ONE]),
        tags=None,
    )
    config = SyncStepConfig(
        batch_size=10,
        conditionals=SyncStepConditionals(enabled=False),
    )

    skipped = await CatalogSyncStep(immich, assets).run(
        SyncStepContext(mode="full", generation=1, config=config),
        scope,
    )
    assert skipped.skipped is True
    assert immich.calls == []

    manual = await CatalogSyncStep(immich, assets).run(
        SyncStepContext(
            mode="full",
            generation=1,
            config=config,
            manual=True,
            respect_conditionals=False,
        ),
        scope,
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

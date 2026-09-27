"""First-class relationship synchronization behavior and authority evidence."""

import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.action_schema import AssetSelectionRequest
from companion.immich import ImmichAlbum, ImmichTag
from companion.synchronization import relationships as relationship_module
from companion.synchronization.evidence import SyncAuthority
from companion.synchronization.relationships import RelationshipSyncStep
from companion.synchronization.scopes import RelationshipScope
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    GenerationSelection,
    PersistedSelection,
    RequestSelection,
)
from companion.synchronization.steps import (
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
)

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ALBUM_ONE = UUID("33333333-3333-4333-8333-333333333333")
TAG_ONE = UUID("44444444-4444-4444-8444-444444444444")
SELECTION_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


class FakeImmich:
    def __init__(self) -> None:
        self.album_catalog = [
            ImmichAlbum(
                id=ALBUM_ONE,
                albumName="Review",
                assetCount=1,
                createdAt="2026-09-25T10:00:00Z",
                updatedAt="2026-09-25T10:00:00Z",
            )
        ]
        self.tag_catalog = [
            ImmichTag(
                id=TAG_ONE,
                name="Review",
                value="Review",
                assetCount=1,
            )
        ]
        self.calls: list[str] = []

    async def list_album_catalog(self):
        self.calls.append("album_catalog")
        return self.album_catalog

    async def list_tag_catalog(self):
        self.calls.append("tag_catalog")
        return self.tag_catalog

    async def iter_album_asset_ids(self, _album_id, *, page_size, start_page):
        assert page_size == 1000
        assert start_page == 1
        self.calls.append("album_memberships")
        yield [ASSET_ONE]

    async def iter_tag_asset_ids(self, _tag_id, *, page_size, start_page):
        assert page_size == 1000
        assert start_page == 1
        self.calls.append("tag_memberships")
        yield [ASSET_ONE]


class FakeAssets:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def tag_asset_counts(self):
        return {TAG_ONE: 1}

    async def upsert_album_memberships(self, _album_id, ids, _generation):
        self.calls.append("album")
        return len(ids)

    async def upsert_tag_memberships(self, _tag_id, ids, _generation):
        self.calls.append("tag")
        return len(ids)

    async def replace_asset_album_memberships(self, _asset_id, _album_ids):
        self.calls.append("replace_asset_album")

    async def replace_asset_tag_memberships(self, _asset_id, _tag_ids):
        self.calls.append("replace_asset_tag")

    async def replace_album_memberships(self, _album_id, ids):
        self.calls.append("replace_album")
        return len(ids)

    async def replace_tag_memberships(self, _tag_id, ids):
        self.calls.append("replace_tag")
        return len(ids)


class FakeSelections:
    def __init__(self) -> None:
        self.asset_batches: list[list[UUID]] = []
        self.tag_batches: list[list[UUID]] = []
        self.calls: list[tuple[str, object, int]] = []

    async def iter_asset_ids(self, selection, *, batch_size):
        self.calls.append(("assets", selection, batch_size))
        for batch in self.asset_batches:
            yield batch

    async def iter_album_ids(self, selection, *, batch_size):
        self.calls.append(("albums", selection, batch_size))
        if False:
            yield []

    async def iter_tag_ids(self, selection, *, batch_size):
        self.calls.append(("tags", selection, batch_size))
        for batch in self.tag_batches:
            yield batch


def context() -> SyncStepContext:
    return SyncStepContext(
        mode="incremental",
        generation=41,
        config=SyncStepConfig(
            batch_size=25,
            page_size=1000,
            concurrency=4,
            conditionals=SyncStepConditionals(enabled=False),
        ),
        manual=True,
        respect_conditionals=False,
    )


@pytest.mark.asyncio
async def test_full_relation_traversal_emits_complete_membership_evidence() -> None:
    immich = FakeImmich()
    result = await RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        FakeSelections(),  # type: ignore[arg-type]
    ).run(
        context(),
        RelationshipScope(
            kinds={"albums", "tags"},
            strategy="by_relation",
            albums=AllSelection(),
            tags=AllSelection(),
        ),
    )

    evidence = {item.domain: item for item in result.evidence}
    assert evidence["album_memberships"].authority == SyncAuthority.COMPLETE
    assert evidence["tag_memberships"].authority == SyncAuthority.COMPLETE
    assert result.counters["album_memberships"] == 1
    assert result.counters["tag_memberships"] == 1
    assert result.outputs == {"strategy": "by_relation", "tag_fallback": False}


@pytest.mark.asyncio
async def test_selected_relation_scope_replaces_snapshot_after_full_traversal() -> None:
    immich = FakeImmich()
    assets = FakeAssets()
    result = await RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSelections(),  # type: ignore[arg-type]
    ).run(
        context(),
        RelationshipScope(
            kinds={"albums", "tags"},
            strategy="by_relation",
            albums=ExplicitIdsSelection(ids=[ALBUM_ONE]),
            tags=ExplicitIdsSelection(ids=[TAG_ONE]),
        ),
    )

    assert "replace_album" in assets.calls
    assert "replace_tag" in assets.calls
    assert "album" not in assets.calls
    assert "tag" not in assets.calls
    assert {item.authority for item in result.evidence} == {SyncAuthority.SELECTED}


@pytest.mark.asyncio
async def test_manual_persisted_tag_relation_scope_emits_selected_evidence() -> None:
    immich = FakeImmich()
    selections = FakeSelections()
    selections.tag_batches = [[TAG_ONE]]
    selection = PersistedSelection(selection_id=SELECTION_ID)

    result = await RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        selections,  # type: ignore[arg-type]
    ).run(
        context(),
        RelationshipScope(
            kinds={"tags"},
            strategy="by_relation",
            tags=selection,
        ),
    )

    assert "album_catalog" not in immich.calls
    assert result.evidence[0].domain == "tag_memberships"
    assert result.evidence[0].authority == SyncAuthority.SELECTED
    assert result.evidence[0].selection == selection
    assert selections.calls == [("tags", selection, 25)]


@pytest.mark.asyncio
async def test_manual_request_asset_scope_uses_resolver_and_selected_evidence(
    monkeypatch,
) -> None:
    immich = FakeImmich()
    selections = FakeSelections()
    selections.asset_batches = [[ASSET_ONE]]
    request = RequestSelection(
        request=AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE])
    )
    reconciled: list[list[UUID]] = []

    async def reconcile(_immich, _assets, ids, *, generation, concurrency):
        assert generation == 41
        assert concurrency == 1
        reconciled.append(list(ids))
        return SimpleNamespace(
            album_links=1,
            tag_links=1,
            payload_assets=1,
            tag_fallback_assets=0,
        )

    monkeypatch.setattr(
        relationship_module,
        "reconcile_generation_asset_relations",
        reconcile,
    )
    result = await RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        selections,  # type: ignore[arg-type]
    ).run(
        context(),
        RelationshipScope(
            kinds={"albums", "tags"},
            strategy="by_asset",
            assets=request,
        ),
    )

    assert reconciled == [[ASSET_ONE]]
    assert "album_catalog" not in immich.calls
    assert "tag_catalog" not in immich.calls
    assert {item.authority for item in result.evidence} == {SyncAuthority.SELECTED}
    assert all(item.selection == request for item in result.evidence)


@pytest.mark.asyncio
async def test_asset_strategy_tag_fallback_returns_complete_tag_evidence(
    monkeypatch,
) -> None:
    immich = FakeImmich()
    selections = FakeSelections()
    selections.asset_batches = [[ASSET_ONE]]
    selection = GenerationSelection(generation=41)

    async def reconcile(_immich, _assets, ids, *, generation, concurrency):
        assert ids == [ASSET_ONE]
        assert generation == 41
        assert concurrency == 1
        return SimpleNamespace(
            album_links=1,
            tag_links=0,
            payload_assets=0,
            tag_fallback_assets=1,
        )

    monkeypatch.setattr(
        relationship_module,
        "reconcile_generation_asset_relations",
        reconcile,
    )
    result = await RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        selections,  # type: ignore[arg-type]
    ).run(
        context(),
        RelationshipScope(
            kinds={"albums", "tags"},
            strategy="by_asset",
            assets=selection,
        ),
    )

    evidence = {item.domain: item for item in result.evidence}
    assert evidence["album_memberships"].authority == SyncAuthority.SELECTED
    assert evidence["album_memberships"].selection == selection
    assert evidence["tag_memberships"].authority == SyncAuthority.COMPLETE
    assert evidence["tag_memberships"].selection == AllSelection()
    assert result.counters["tag_strategy_asset_fallback"] == 1
    assert "tag_memberships" in immich.calls
    assert result.outputs == {"strategy": "by_asset", "tag_fallback": True}


@pytest.mark.asyncio
async def test_forced_asset_strategy_uses_selected_assets() -> None:
    immich = FakeImmich()
    selections = FakeSelections()
    selections.asset_batches = [[ASSET_ONE]]
    reconciled: list[list[UUID]] = []

    async def reconcile(_immich, _assets, ids, *, generation, concurrency):
        assert generation == 41
        assert concurrency == 1
        reconciled.append(list(ids))
        return SimpleNamespace(
            album_links=1,
            tag_links=1,
            payload_assets=1,
            tag_fallback_assets=0,
        )

    original = relationship_module.reconcile_generation_asset_relations
    relationship_module.reconcile_generation_asset_relations = reconcile
    try:
        result = await RelationshipSyncStep(
            immich,  # type: ignore[arg-type]
            FakeAssets(),  # type: ignore[arg-type]
            selections,  # type: ignore[arg-type]
        ).run(
            context(),
            RelationshipScope(
                kinds={"albums", "tags"},
                strategy="by_asset",
                assets=GenerationSelection(generation=41),
            ),
        )
    finally:
        relationship_module.reconcile_generation_asset_relations = original

    assert reconciled == [[ASSET_ONE]]
    assert result.outputs["strategy"] == "by_asset"
    assert "album_memberships" not in immich.calls
    assert "tag_memberships" not in immich.calls


@pytest.mark.asyncio
async def test_forced_relation_strategy_traverses_relations() -> None:
    immich = FakeImmich()

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("forced relation strategy must not reconcile selected assets")

    original = relationship_module.reconcile_generation_asset_relations
    relationship_module.reconcile_generation_asset_relations = unexpected
    try:
        result = await RelationshipSyncStep(
            immich,  # type: ignore[arg-type]
            FakeAssets(),  # type: ignore[arg-type]
            FakeSelections(),  # type: ignore[arg-type]
        ).run(
            context(),
            RelationshipScope(
                kinds={"albums", "tags"},
                strategy="by_relation",
                albums=AllSelection(),
                tags=AllSelection(),
            ),
        )
    finally:
        relationship_module.reconcile_generation_asset_relations = original

    assert result.outputs["strategy"] == "by_relation"
    assert "album_memberships" in immich.calls
    assert "tag_memberships" in immich.calls


@pytest.mark.asyncio
async def test_automatic_strategy_prefers_assets_on_equal_cost() -> None:
    immich = FakeImmich()
    selections = FakeSelections()
    selections.asset_batches = [[ASSET_ONE]]
    reconciled: list[list[UUID]] = []

    async def reconcile(_immich, _assets, ids, *, generation, concurrency):
        reconciled.append(list(ids))
        return SimpleNamespace(
            album_links=1,
            tag_links=1,
            payload_assets=1,
            tag_fallback_assets=0,
        )

    original = relationship_module.reconcile_generation_asset_relations
    relationship_module.reconcile_generation_asset_relations = reconcile
    try:
        result = await RelationshipSyncStep(
            immich,  # type: ignore[arg-type]
            FakeAssets(),  # type: ignore[arg-type]
            selections,  # type: ignore[arg-type]
        ).run(
            context(),
            RelationshipScope(
                kinds={"albums", "tags"},
                strategy="automatic",
                assets=GenerationSelection(generation=41),
                albums=AllSelection(),
                tags=AllSelection(),
            ),
        )
    finally:
        relationship_module.reconcile_generation_asset_relations = original

    assert reconciled == [[ASSET_ONE]]
    assert result.outputs["strategy"] == "by_asset"


@pytest.mark.asyncio
async def test_automatic_strategy_prefers_relation_when_cheaper() -> None:
    immich = FakeImmich()
    selections = FakeSelections()
    selections.asset_batches = [[ASSET_ONE, ASSET_TWO]]

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("automatic strategy should choose relation traversal")

    original = relationship_module.reconcile_generation_asset_relations
    relationship_module.reconcile_generation_asset_relations = unexpected
    try:
        result = await RelationshipSyncStep(
            immich,  # type: ignore[arg-type]
            FakeAssets(),  # type: ignore[arg-type]
            selections,  # type: ignore[arg-type]
        ).run(
            context(),
            RelationshipScope(
                kinds={"albums", "tags"},
                strategy="automatic",
                assets=GenerationSelection(generation=41),
                albums=AllSelection(),
                tags=AllSelection(),
            ),
        )
    finally:
        relationship_module.reconcile_generation_asset_relations = original

    assert result.outputs["strategy"] == "by_relation"
    assert "album_memberships" in immich.calls
    assert "tag_memberships" in immich.calls


@pytest.mark.asyncio
async def test_relation_traversal_preserves_page_pacing_and_large_page_size() -> None:
    class PagedImmich(FakeImmich):
        def __init__(self) -> None:
            super().__init__()
            self.album_page_size: int | None = None
            self.tag_page_size: int | None = None

        async def iter_album_asset_ids(self, _album_id, *, page_size, start_page):
            assert start_page == 1
            self.album_page_size = page_size
            yield [ASSET_ONE]
            yield [ASSET_TWO]
            yield [ASSET_ONE, ASSET_TWO]

        async def iter_tag_asset_ids(self, _tag_id, *, page_size, start_page):
            assert start_page == 1
            self.tag_page_size = page_size
            yield [ASSET_ONE]
            yield [ASSET_TWO]

    class PacedStep(RelationshipSyncStep):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.paced = 0

        async def pace(self, _context, _started):
            self.paced += 1

    immich = PagedImmich()
    step = PacedStep(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        FakeSelections(),  # type: ignore[arg-type]
    )
    result = await step.run(
        context(),
        RelationshipScope(
            kinds={"albums", "tags"},
            strategy="by_relation",
            albums=AllSelection(),
            tags=AllSelection(),
        ),
    )

    assert immich.album_page_size == 1000
    assert immich.tag_page_size == 1000
    assert step.paced == 3
    assert result.counters["album_memberships"] == 4
    assert result.counters["tag_memberships"] == 2


@pytest.mark.asyncio
async def test_tag_relation_traversal_preserves_runtime_concurrency_and_empty_counts() -> None:
    tag_ids = [
        UUID(f"{index:08x}-0000-4000-8000-000000000000")
        for index in range(1, 7)
    ]

    class ConcurrentTagImmich(FakeImmich):
        def __init__(self) -> None:
            super().__init__()
            self.active = 0
            self.maximum_active = 0
            self.tag_catalog = [
                ImmichTag(
                    id=tag_id,
                    name=f"Tag {index}",
                    value=f"Tag {index}",
                    assetCount=0 if index == 0 else 1,
                )
                for index, tag_id in enumerate(tag_ids)
            ]

        async def iter_tag_asset_ids(self, tag_id, *, page_size, start_page):
            assert page_size == 1000
            assert start_page == 1
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            await asyncio.sleep(0)
            yield [] if tag_id == tag_ids[0] else [ASSET_ONE]
            self.active -= 1

    immich = ConcurrentTagImmich()
    assets = FakeAssets()
    result = await RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSelections(),  # type: ignore[arg-type]
    ).run(
        context(),
        RelationshipScope(
            kinds={"tags"},
            strategy="by_relation",
            tags=AllSelection(),
        ),
    )

    assert immich.maximum_active == 4
    assert result.counters["tag_memberships"] == 5
    assert result.counters["tag_relationships_scanned"] == 6
    assert result.counters["tag_empty_relationships"] == 1


@pytest.mark.asyncio
async def test_relationship_step_respects_normal_conditionals_without_remote_work() -> None:
    immich = FakeImmich()
    step = RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        FakeSelections(),  # type: ignore[arg-type]
    )
    skipped_context = SyncStepContext(
        mode="full",
        generation=42,
        config=SyncStepConfig(
            batch_size=25,
            page_size=1000,
            concurrency=4,
            conditionals=SyncStepConditionals(enabled=False),
        ),
    )

    result = await step.run(
        skipped_context,
        RelationshipScope(
            kinds={"albums", "tags"},
            strategy="by_relation",
            albums=AllSelection(),
            tags=AllSelection(),
        ),
    )

    assert result.skipped is True
    assert result.evidence == []
    assert immich.calls == []


@pytest.mark.asyncio
async def test_relation_traversal_resumes_after_completed_album_cursor() -> None:
    album_two = UUID("55555555-5555-4555-8555-555555555555")

    class ResumeImmich(FakeImmich):
        def __init__(self) -> None:
            super().__init__()
            self.album_catalog.append(
                ImmichAlbum(
                    id=album_two,
                    albumName="Later",
                    assetCount=1,
                    createdAt="2026-09-25T10:00:00Z",
                    updatedAt="2026-09-25T10:00:00Z",
                )
            )
            self.album_ids: list[UUID] = []

        async def iter_album_asset_ids(self, album_id, *, page_size, start_page):
            assert page_size == 1000
            assert start_page == 1
            self.album_ids.append(album_id)
            yield [ASSET_ONE]

    immich = ResumeImmich()
    assets = FakeAssets()
    resume_context = context()
    resume_context.cursor = "albums:1:0"
    resume_context.counters = {
        "album_memberships": 1,
        "tag_memberships": 0,
    }

    result = await RelationshipSyncStep(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeSelections(),  # type: ignore[arg-type]
    ).run(
        resume_context,
        RelationshipScope(
            kinds={"albums", "tags"},
            strategy="by_relation",
            albums=AllSelection(),
            tags=AllSelection(),
        ),
    )

    assert immich.album_ids == [album_two]
    assert result.counters["album_memberships"] == 2
    assert result.counters["tag_memberships"] == 1
    assert result.evidence[0].authority == SyncAuthority.COMPLETE

"""First-class relationship synchronization behavior and authority evidence."""

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

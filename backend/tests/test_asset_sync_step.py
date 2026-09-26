"""First-class asset synchronization step behavior."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from companion.action_schema import AssetSelectionRequest
from companion.asset_schema import SearchCondition, SearchGroup
from companion.immich import ImmichApiError, ImmichAsset, ImmichAssetSearchPage
from companion.synchronization.evidence import SyncAuthority
from companion.synchronization.scopes import AssetScope
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    PersistedSelection,
    RequestSelection,
    WindowSelection,
)
from companion.synchronization.steps import AssetSyncStep, SyncStepConfig, SyncStepContext

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ASSET_THREE = UUID("33333333-3333-4333-8333-333333333333")
SELECTION_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def asset(identifier: UUID, *, tags: list[dict[str, str]] | None = None) -> ImmichAsset:
    payload: dict[str, object] = {
        "id": str(identifier),
        "type": "IMAGE",
        "originalFileName": f"{identifier}.jpg",
        "originalMimeType": "image/jpeg",
        "width": 100,
        "height": 100,
        "fileCreatedAt": "2026-09-25T10:00:00Z",
        "fileModifiedAt": "2026-09-25T10:00:00Z",
        "updatedAt": "2026-09-25T10:00:00Z",
        "exifInfo": {"make": "Camera"},
        "people": [{"id": "person"}],
        "stack": {"id": "stack"},
    }
    if tags is not None:
        payload["tags"] = tags
    return ImmichAsset.model_validate(payload)


class FakeImmich:
    def __init__(self) -> None:
        self.pages: list[tuple[int, ImmichAssetSearchPage]] = []
        self.details: dict[UUID, ImmichAsset | Exception] = {}
        self.page_calls: list[dict[str, object]] = []
        self.detail_calls: list[UUID] = []
        self.count_calls: list[tuple[datetime | None, datetime | None]] = []
        self.total: int | None = None

    async def count_assets(self, *, updated_after=None, updated_before=None):
        self.count_calls.append((updated_after, updated_before))
        return self.total

    async def iter_asset_pages(self, **kwargs):
        self.page_calls.append(kwargs)
        for item in self.pages:
            yield item

    async def get_asset(self, asset_id: UUID) -> ImmichAsset:
        self.detail_calls.append(asset_id)
        value = self.details[asset_id]
        if isinstance(value, Exception):
            raise value
        return value


class FakeAssets:
    def __init__(self) -> None:
        self.batches: list[list[ImmichAsset]] = []
        self.generations: list[int] = []
        self.similarity_flags: list[bool] = []

    async def upsert_asset_batch(
        self,
        items,
        generation,
        *,
        track_similarity_changes,
    ):
        self.batches.append(list(items))
        self.generations.append(generation)
        self.similarity_flags.append(track_similarity_changes)
        return len(items), 0, 0


class FakeSelections:
    def __init__(self) -> None:
        self.batches: list[list[UUID]] = []
        self.calls: list[object] = []

    async def iter_asset_ids(self, selection, *, batch_size):
        self.calls.append((selection, batch_size))
        for batch in self.batches:
            yield batch


class PagePacedAssetStep(AssetSyncStep):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.page_paces = 0

    async def pace_page(self, _context) -> None:
        self.page_paces += 1


@pytest.mark.asyncio
async def test_asset_step_all_scope_preserves_page_batching_counters_and_evidence() -> None:
    immich = FakeImmich()
    immich.total = 3
    immich.pages = [
        (
            1,
            ImmichAssetSearchPage.model_validate(
                {
                    "count": 2,
                    "total": 3,
                    "items": [
                        asset(ASSET_ONE, tags=[]),
                        asset(ASSET_TWO),
                    ],
                    "nextPage": "2",
                }
            ),
        ),
        (
            2,
            ImmichAssetSearchPage.model_validate(
                {
                    "count": 1,
                    "total": 3,
                    "items": [asset(ASSET_THREE, tags=[])],
                    "nextPage": None,
                }
            ),
        ),
    ]
    assets = FakeAssets()
    progress = []

    async def checkpoint(cursor, _counters, current):
        progress.append((cursor, current.completed, current.total, current.detail))

    step = PagePacedAssetStep(
        immich,
        assets,  # type: ignore[arg-type]
        page_prefetch=1,
    )
    result = await step.run(
        SyncStepContext(
            mode="full",
            generation=7,
            config=SyncStepConfig(batch_size=1, page_size=2),
            manual=True,
            respect_conditionals=False,
            checkpoint_callback=checkpoint,
        ),
        AssetScope(selection=AllSelection()),
    )

    assert result.completed == 3
    assert result.total == 3
    assert result.counters["assets_seen"] == 3
    assert result.counters["tag_cheap_path_eligible_assets"] == 2
    assert result.counters["tag_cheap_path_fallback_assets"] == 1
    assert result.evidence[0].authority == SyncAuthority.COMPLETE
    assert [len(batch) for batch in assets.batches] == [1, 1, 1]
    assert assets.similarity_flags == [True, True, True]
    assert all(batch[0].exif_info is None for batch in assets.batches)
    assert all(batch[0].people == [] for batch in assets.batches)
    assert all(batch[0].tags == [] for batch in assets.batches)
    assert step.page_paces == 1
    assert progress[-1][:3] == ("assets:2:1", 3, 3)


@pytest.mark.asyncio
async def test_asset_step_window_scope_preserves_bounds_and_resume_cursor() -> None:
    start = datetime(2026, 9, 25, 10, tzinfo=UTC)
    end = start + timedelta(hours=1)
    immich = FakeImmich()
    immich.pages = [
        (
            2,
            ImmichAssetSearchPage.model_validate(
                {
                    "count": 2,
                    "total": 2,
                    "items": [asset(ASSET_ONE), asset(ASSET_TWO)],
                    "nextPage": None,
                }
            ),
        )
    ]
    assets = FakeAssets()

    result = await AssetSyncStep(
        immich,
        assets,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="incremental",
            generation=8,
            config=SyncStepConfig(batch_size=1, page_size=2),
            manual=True,
            respect_conditionals=False,
            counters={
                "assets_seen": 1,
                "assets_created": 1,
                "assets_updated": 0,
                "assets_unchanged": 0,
                "tag_cheap_path_eligible_assets": 0,
                "tag_cheap_path_fallback_assets": 1,
            },
            cursor="assets:2:1",
        ),
        AssetScope(selection=WindowSelection(start=start, end=end)),
    )

    assert immich.page_calls == [
        {
            "page_size": 2,
            "updated_after": start,
            "updated_before": end,
            "start_page": 2,
        }
    ]
    assert len(assets.batches) == 1
    assert assets.batches[0][0].id == ASSET_TWO
    assert result.counters["assets_seen"] == 2
    assert result.evidence[0].authority == SyncAuthority.WINDOW
    assert result.evidence[0].selection == WindowSelection(start=start, end=end)


@pytest.mark.asyncio
async def test_manual_explicit_asset_scope_fetches_authoritative_remote_details() -> None:
    immich = FakeImmich()
    immich.details = {
        ASSET_ONE: asset(ASSET_ONE, tags=[]),
        ASSET_TWO: asset(ASSET_TWO),
    }
    assets = FakeAssets()
    selections = FakeSelections()
    selections.batches = [[ASSET_ONE, ASSET_TWO]]

    result = await AssetSyncStep(
        immich,
        assets,  # type: ignore[arg-type]
        selections,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="full",
            generation=9,
            config=SyncStepConfig(batch_size=2, concurrency=2),
            manual=True,
            respect_conditionals=False,
        ),
        AssetScope(
            selection=ExplicitIdsSelection(
                ids=[ASSET_ONE, ASSET_TWO, ASSET_ONE],
            )
        ),
    )

    assert immich.detail_calls == [ASSET_ONE, ASSET_TWO]
    assert len(assets.batches) == 1
    assert result.total == 2
    assert result.evidence[0].authority == SyncAuthority.SELECTED
    assert selections.calls[0][1] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("selection_kind", ["persisted", "request"])
async def test_manual_database_backed_asset_scopes_use_resolver(selection_kind: str) -> None:
    immich = FakeImmich()
    immich.details = {ASSET_THREE: asset(ASSET_THREE)}
    assets = FakeAssets()
    selections = FakeSelections()
    selections.batches = [[ASSET_THREE]]

    if selection_kind == "persisted":
        selection = PersistedSelection(selection_id=SELECTION_ID)
    else:
        selection = RequestSelection(
            request=AssetSelectionRequest(
                mode="all_matching",
                expression=SearchGroup(
                    children=[
                        SearchCondition(
                            field="favorite",
                            operator="equals",
                            value=True,
                        )
                    ]
                ),
            )
        )

    result = await AssetSyncStep(
        immich,
        assets,  # type: ignore[arg-type]
        selections,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="full",
            generation=10,
            config=SyncStepConfig(batch_size=25, concurrency=2),
            manual=True,
            respect_conditionals=False,
        ),
        AssetScope(selection=selection),
    )

    assert immich.detail_calls == [ASSET_THREE]
    assert result.completed == 1
    assert result.evidence[0].authority == SyncAuthority.SELECTED
    assert selections.calls[0][0] == selection


@pytest.mark.asyncio
async def test_selected_asset_missing_in_immich_fails_before_persistence() -> None:
    immich = FakeImmich()
    immich.details = {ASSET_ONE: ImmichApiError("get asset", 404)}
    assets = FakeAssets()
    selections = FakeSelections()
    selections.batches = [[ASSET_ONE]]

    with pytest.raises(ImmichApiError, match="HTTP 404"):
        await AssetSyncStep(
            immich,
            assets,  # type: ignore[arg-type]
            selections,  # type: ignore[arg-type]
        ).run(
            SyncStepContext(
                mode="full",
                generation=11,
                config=SyncStepConfig(batch_size=10),
                manual=True,
                respect_conditionals=False,
            ),
            AssetScope(selection=ExplicitIdsSelection(ids=[ASSET_ONE])),
        )

    assert assets.batches == []

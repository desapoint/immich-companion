"""Bounded selection resolution for first-class synchronization steps."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from companion.action_schema import AssetSelectionRequest
from companion.asset_repository import AssetRepository
from companion.asset_schema import SearchCondition, SearchGroup
from companion.selection_repository import RelationSelectionRepository
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    GenerationSelection,
    PersistedSelection,
    RequestSelection,
    SyncSelectionResolver,
    WindowSelection,
)

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
ASSET_THREE = UUID("33333333-3333-4333-8333-333333333333")
ASSET_FOUR = UUID("44444444-4444-4444-8444-444444444444")
SELECTION_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


async def collect(iterator):
    return [batch async for batch in iterator]


class FakeAssets:
    def __init__(self) -> None:
        self.request_batches: list[list[UUID]] = []
        self.generation_batches: list[list[UUID]] = []
        self.requests: list[tuple[AssetSelectionRequest, int]] = []
        self.generations: list[tuple[int, int]] = []

    async def iter_selection_ids(self, selection, *, batch_size):
        self.requests.append((selection, batch_size))
        for batch in self.request_batches:
            yield batch

    async def iter_generation_asset_ids(self, generation, *, batch_size):
        self.generations.append((generation, batch_size))
        for batch in self.generation_batches:
            yield batch


class FakeRelations:
    def __init__(self) -> None:
        self.batches: list[list[UUID]] = []
        self.calls: list[tuple[UUID, str, int]] = []

    async def iter_ids(self, selection_id, kind, *, batch_size):
        self.calls.append((selection_id, kind, batch_size))
        for batch in self.batches:
            yield batch


@pytest.mark.asyncio
async def test_explicit_ids_are_deduplicated_and_batched() -> None:
    resolver = SyncSelectionResolver(FakeAssets(), FakeRelations())

    batches = await collect(
        resolver.iter_asset_ids(
            ExplicitIdsSelection(ids=[ASSET_ONE, ASSET_TWO, ASSET_ONE, ASSET_THREE]),
            batch_size=2,
        )
    )

    assert batches == [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]


@pytest.mark.asyncio
async def test_generation_selection_uses_bounded_repository_iterator() -> None:
    assets = FakeAssets()
    assets.generation_batches = [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]
    resolver = SyncSelectionResolver(assets, FakeRelations())

    batches = await collect(
        resolver.iter_asset_ids(GenerationSelection(generation=17), batch_size=2)
    )

    assert batches == [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]
    assert assets.generations == [(17, 2)]


@pytest.mark.asyncio
async def test_asset_request_selection_is_forwarded_without_materializing_ids() -> None:
    assets = FakeAssets()
    assets.request_batches = [[ASSET_ONE], [ASSET_TWO]]
    resolver = SyncSelectionResolver(assets, FakeRelations())
    request = AssetSelectionRequest(
        mode="all_matching",
        expression=SearchGroup(
            children=[
                SearchCondition(field="favorite", operator="equals", value=True),
            ]
        ),
        excluded_ids=[ASSET_FOUR],
    )

    batches = await collect(
        resolver.iter_asset_ids(RequestSelection(request=request), batch_size=1)
    )

    assert batches == [[ASSET_ONE], [ASSET_TWO]]
    assert assets.requests == [(request, 1)]
    assert request.ids == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("kind", "method"), [("album", "iter_album_ids"), ("tag", "iter_tag_ids")])
async def test_persisted_relation_selection_uses_typed_batched_repository(
    kind: str,
    method: str,
) -> None:
    relations = FakeRelations()
    relations.batches = [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]
    resolver = SyncSelectionResolver(FakeAssets(), relations)

    batches = await collect(
        getattr(resolver, method)(
            PersistedSelection(selection_id=SELECTION_ID),
            batch_size=2,
        )
    )

    assert batches == [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]
    assert relations.calls == [(SELECTION_ID, kind, 2)]


@pytest.mark.asyncio
async def test_remote_asset_selections_are_not_replaced_by_local_database_ids() -> None:
    resolver = SyncSelectionResolver(FakeAssets(), FakeRelations())
    start = datetime(2026, 9, 25, 10, tzinfo=UTC)
    end = start + timedelta(hours=1)

    with pytest.raises(ValueError, match="remote traversal"):
        await collect(resolver.iter_asset_ids(AllSelection(), batch_size=10))
    with pytest.raises(ValueError, match="remote traversal"):
        await collect(
            resolver.iter_asset_ids(
                WindowSelection(start=start, end=end),
                batch_size=10,
            )
        )


class ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class PagingDatabase:
    def __init__(self, pages, *, selection_record=None) -> None:
        self.pages = list(pages)
        self.selection_record = selection_record
        self.statements = []

    @asynccontextmanager
    async def sessions(self):
        database = self

        class Session:
            async def scalars(self, statement):
                database.statements.append(statement)
                values = database.pages.pop(0) if database.pages else []
                return ScalarResult(values)

            async def get(self, _model, _identifier):
                return database.selection_record

        yield Session()


@pytest.mark.asyncio
async def test_query_backed_asset_request_uses_existing_search_semantics_in_pages() -> None:
    database = PagingDatabase([[ASSET_ONE, ASSET_TWO], [ASSET_THREE]])
    repository = AssetRepository(database)  # type: ignore[arg-type]
    request = AssetSelectionRequest(
        mode="all_matching",
        expression=SearchGroup(
            children=[
                SearchCondition(field="favorite", operator="equals", value=True),
            ]
        ),
        excluded_ids=[ASSET_FOUR],
    )

    batches = await collect(repository.iter_selection_ids(request, batch_size=2))

    assert batches == [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]
    assert len(database.statements) == 2
    first_sql = str(
        database.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    second_sql = str(
        database.statements[1].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "assets.is_trashed IS false" in first_sql
    assert "assets.is_favorite = true" in first_sql
    assert "assets.id NOT IN" in first_sql
    assert str(ASSET_FOUR) in first_sql
    assert "LIMIT 2" in first_sql
    assert f"assets.id > '{ASSET_TWO}'" in second_sql


@pytest.mark.asyncio
async def test_request_explicit_ids_keep_request_order_and_skip_missing_local_assets() -> None:
    database = PagingDatabase([[ASSET_TWO, ASSET_ONE], [ASSET_THREE]])
    repository = AssetRepository(database)  # type: ignore[arg-type]
    request = AssetSelectionRequest(
        mode="explicit",
        ids=[ASSET_ONE, ASSET_TWO, ASSET_THREE, ASSET_FOUR],
    )

    batches = await collect(repository.iter_selection_ids(request, batch_size=2))

    assert batches == [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]


@pytest.mark.asyncio
async def test_generation_asset_ids_are_queried_in_bounded_keyset_pages() -> None:
    database = PagingDatabase([[ASSET_ONE, ASSET_TWO], [ASSET_THREE]])
    repository = AssetRepository(database)  # type: ignore[arg-type]

    batches = await collect(repository.iter_generation_asset_ids(23, batch_size=2))

    assert batches == [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]
    first_sql = str(
        database.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    second_sql = str(
        database.statements[1].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "assets.sync_generation = 23" in first_sql
    assert "assets.is_trashed IS false" in first_sql
    assert f"assets.id > '{ASSET_TWO}'" in second_sql


@pytest.mark.asyncio
async def test_asset_persisted_selection_rejects_expired_selection() -> None:
    record = SimpleNamespace(
        entity_kind="asset",
        status="active",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        revision=4,
    )
    database = PagingDatabase([], selection_record=record)
    repository = AssetRepository(database)  # type: ignore[arg-type]
    request = AssetSelectionRequest(mode="explicit", selection_id=SELECTION_ID)

    with pytest.raises(ValueError, match="expired"):
        await collect(repository.iter_selection_ids(request, batch_size=10))


@pytest.mark.asyncio
async def test_relation_persisted_selection_is_batched_and_revision_checked() -> None:
    record = SimpleNamespace(
        entity_kind="album",
        status="active",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revision=7,
    )
    database = PagingDatabase([[ASSET_ONE, ASSET_TWO], [ASSET_THREE]])
    repository = RelationSelectionRepository(database)  # type: ignore[arg-type]

    async def get(_selection_id, _kind):
        return record

    repository.get = get  # type: ignore[method-assign]

    batches = await collect(repository.iter_ids(SELECTION_ID, "album", batch_size=2))

    assert batches == [[ASSET_ONE, ASSET_TWO], [ASSET_THREE]]
    assert len(database.statements) == 2
    second_sql = str(
        database.statements[1].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert f"selection_set_key_members.entity_id > '{ASSET_TWO}'" in second_sql


@pytest.mark.asyncio
async def test_relation_persisted_selection_rejects_expired_selection() -> None:
    record = SimpleNamespace(
        entity_kind="tag",
        status="active",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        revision=1,
    )
    repository = RelationSelectionRepository(PagingDatabase([]))  # type: ignore[arg-type]

    async def get(_selection_id, _kind):
        return record

    repository.get = get  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="expired"):
        await collect(repository.iter_ids(SELECTION_ID, "tag", batch_size=10))


@pytest.mark.asyncio
async def test_zero_batch_size_is_rejected_before_selection_work() -> None:
    resolver = SyncSelectionResolver(FakeAssets(), FakeRelations())

    with pytest.raises(ValueError, match="batch_size"):
        await collect(
            resolver.iter_asset_ids(
                ExplicitIdsSelection(ids=[ASSET_ONE]),
                batch_size=0,
            )
        )

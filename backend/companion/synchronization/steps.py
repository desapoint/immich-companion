"""Canonical composable synchronization-step contracts."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.immich import (
    ImmichAlbum,
    ImmichApiClient,
    ImmichApiError,
    ImmichAsset,
    ImmichTag,
)
from companion.sync_schema import SyncMode
from companion.synchronization.batching import batches, prefetch_async
from companion.synchronization.evidence import SyncAuthority, SyncEvidence
from companion.synchronization.scopes import AssetScope, CatalogScope, SyncStepName
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    GenerationSelection,
    PersistedSelection,
    RequestSelection,
    SyncSelectionResolver,
    WindowSelection,
)
from companion.tasks.coordinator import TaskContext


@dataclass(frozen=True, slots=True)
class SyncStepConditionals:
    enabled: bool = True
    run_on_full: bool = True
    run_on_incremental: bool = True

    def allows(self, mode: SyncMode) -> bool:
        if not self.enabled:
            return False
        return self.run_on_full if mode == "full" else self.run_on_incremental


@dataclass(frozen=True, slots=True)
class SyncStepConfig:
    """Standard operational controls shared by all sync steps."""

    batch_size: int | None = None
    page_size: int | None = None
    concurrency: int = 1
    min_batch_delay_seconds: float = 0.0
    conditionals: SyncStepConditionals = field(default_factory=SyncStepConditionals)

    def __post_init__(self) -> None:
        if self.batch_size is not None and self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.page_size is not None and self.page_size < 1:
            raise ValueError("page_size must be at least 1")
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if self.min_batch_delay_seconds < 0:
            raise ValueError("min_batch_delay_seconds cannot be negative")


@dataclass(frozen=True, slots=True)
class SyncStepProgress:
    phase: str
    completed: int
    total: int | None
    detail: str | None = None

    @property
    def percent(self) -> float | None:
        if self.total is None or self.total <= 0:
            return None
        return round(min(100.0, max(0, self.completed) / self.total * 100), 1)

    def as_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "step": self.phase,
            "completed": max(0, self.completed),
            "total": self.total,
            "percent": self.percent,
            "detail": self.detail,
        }


CheckpointCallback = Callable[
    [str | None, dict[str, int], SyncStepProgress], Awaitable[None]
]


async def _noop_checkpoint(
    _cursor: str | None,
    _counters: dict[str, int],
    _progress: SyncStepProgress,
) -> None:
    return None


def task_checkpoint_callback(task: TaskContext, step: str) -> CheckpointCallback:
    """Bridge a sync step to the durable task state consumed by the frontend."""

    async def checkpoint(
        cursor: str | None,
        counters: dict[str, int],
        progress: SyncStepProgress,
    ) -> None:
        await task.checkpoint_sync_step(
            step=step,
            cursor=cursor,
            counters=counters,
            completed=progress.completed,
            total=progress.total,
            detail=progress.detail,
        )

    return checkpoint


@dataclass(slots=True)
class SyncStepContext:
    mode: SyncMode
    generation: int
    config: SyncStepConfig
    counters: dict[str, int] = field(default_factory=dict)
    cursor: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    manual: bool = False
    respect_conditionals: bool = True
    checkpoint_callback: CheckpointCallback = _noop_checkpoint


@dataclass(frozen=True, slots=True)
class SyncStepResult:
    name: SyncStepName
    phase: str
    skipped: bool
    completed: int
    total: int | None
    counters: dict[str, int]
    evidence: list[SyncEvidence] = field(default_factory=list)
    outputs: dict[str, object] = field(default_factory=dict)


class SyncStep[ScopeT](ABC):
    name: SyncStepName
    phase: str

    def should_run(self, context: SyncStepContext) -> bool:
        if context.manual and not context.respect_conditionals:
            return True
        return context.config.conditionals.allows(context.mode)

    async def run(self, context: SyncStepContext, data: ScopeT) -> SyncStepResult:
        if not self.should_run(context):
            return SyncStepResult(
                name=self.name,
                phase=self.phase,
                skipped=True,
                completed=0,
                total=0,
                counters=dict(context.counters),
            )
        completed, total = await self.execute(context, data)
        return SyncStepResult(
            name=self.name,
            phase=self.phase,
            skipped=False,
            completed=completed,
            total=total,
            counters=dict(context.counters),
        )

    @abstractmethod
    async def execute(self, context: SyncStepContext, data: ScopeT) -> tuple[int, int | None]:
        raise NotImplementedError

    async def pace(self, context: SyncStepContext, started: float) -> None:
        delay = context.config.min_batch_delay_seconds
        if delay <= 0:
            return
        await asyncio.sleep(max(0.0, delay - (perf_counter() - started)))

    async def bounded_map[ResultT](
        self,
        context: SyncStepContext,
        items: Sequence[ScopeT],
        worker: Callable[[ScopeT], Awaitable[ResultT]],
    ) -> list[ResultT]:
        """Bound work while preserving result order for deterministic commits/checkpoints."""

        semaphore = asyncio.Semaphore(context.config.concurrency)

        async def guarded(item: ScopeT) -> ResultT:
            async with semaphore:
                return await worker(item)

        return list(await asyncio.gather(*(guarded(item) for item in items)))


class CatalogSyncStep(SyncStep[CatalogScope]):
    """Synchronize scoped album/tag catalogs with resumable batch cursors."""

    name = "catalogs"
    phase = "catalogs"

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        selections: SyncSelectionResolver | None = None,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._selections = selections

    @staticmethod
    def _batches[T](items: Sequence[T], size: int) -> list[Sequence[T]]:
        return [items[index : index + size] for index in range(0, len(items), size)]

    async def _selected_ids(
        self,
        selection: ExplicitIdsSelection | PersistedSelection,
        *,
        relation: str,
        batch_size: int,
    ) -> set[UUID]:
        if isinstance(selection, ExplicitIdsSelection):
            return set(dict.fromkeys(selection.ids))
        if self._selections is None:
            raise ValueError(
                f"Persisted {relation} catalog selection requires SyncSelectionResolver"
            )

        ids: set[UUID] = set()
        iterator = (
            self._selections.iter_album_ids(selection, batch_size=batch_size)
            if relation == "album"
            else self._selections.iter_tag_ids(selection, batch_size=batch_size)
        )
        async for batch in iterator:
            ids.update(batch)
        return ids

    async def _load_albums(
        self,
        scope: CatalogScope,
        *,
        batch_size: int,
    ) -> list[ImmichAlbum]:
        if scope.albums is None:
            return []
        catalog = await self._immich.list_album_catalog()
        if isinstance(scope.albums, AllSelection):
            return catalog
        selected = await self._selected_ids(
            scope.albums,
            relation="album",
            batch_size=batch_size,
        )
        return [album for album in catalog if album.id in selected]

    async def _load_tags(
        self,
        scope: CatalogScope,
        *,
        batch_size: int,
    ) -> list[ImmichTag]:
        if scope.tags is None:
            return []
        catalog = await self._immich.list_tag_catalog()
        if isinstance(scope.tags, AllSelection):
            return catalog
        selected = await self._selected_ids(
            scope.tags,
            relation="tag",
            batch_size=batch_size,
        )
        return [tag for tag in catalog if tag.id in selected]

    async def execute(
        self,
        context: SyncStepContext,
        scope: CatalogScope,
    ) -> tuple[int, int]:
        if context.config.batch_size is None:
            raise ValueError("CatalogSyncStep requires config.batch_size")

        albums, tags = await asyncio.gather(
            self._load_albums(scope, batch_size=context.config.batch_size),
            self._load_tags(scope, batch_size=context.config.batch_size),
        )
        album_batches = self._batches(albums, context.config.batch_size)
        tag_batches = self._batches(tags, context.config.batch_size)
        total = len(albums) + len(tags)
        context.counters.setdefault("albums_seen", 0)
        context.counters.setdefault("tags_seen", 0)

        completed_albums = 0
        completed_tags = 0
        if context.cursor:
            kind, separator, value = context.cursor.partition(":")
            if separator:
                if kind == "albums":
                    completed_albums = int(value)
                elif kind == "tags":
                    completed_albums = len(album_batches)
                    completed_tags = int(value)

        await self._checkpoint(
            context,
            context.cursor,
            min(context.counters["albums_seen"], len(albums))
            + min(context.counters["tags_seen"], len(tags)),
            total,
            f"Preparing {len(albums)} albums and {len(tags)} tags",
        )

        for index, album_batch in enumerate(album_batches, start=1):
            if index <= completed_albums:
                continue
            started = perf_counter()
            created, observed = await self._assets.upsert_album_catalog(
                list(album_batch), context.generation
            )
            context.counters["albums_seen"] += created + observed
            await self._checkpoint(
                context,
                f"albums:{index}",
                min(context.counters["albums_seen"], len(albums)),
                total,
                (
                    f"Albums {min(context.counters['albums_seen'], len(albums))}/"
                    f"{len(albums)} · tags 0/{len(tags)}"
                ),
            )
            await self.pace(context, started)

        for index, tag_batch in enumerate(tag_batches, start=1):
            if index <= completed_tags:
                continue
            started = perf_counter()
            created, observed = await self._assets.upsert_tag_catalog(
                list(tag_batch), context.generation
            )
            context.counters["tags_seen"] += created + observed
            await self._checkpoint(
                context,
                f"tags:{index}",
                len(albums) + min(context.counters["tags_seen"], len(tags)),
                total,
                (
                    f"Albums {len(albums)}/{len(albums)} · tags "
                    f"{min(context.counters['tags_seen'], len(tags))}/{len(tags)}"
                ),
            )
            await self.pace(context, started)

        completed = min(context.counters["albums_seen"], len(albums)) + min(
            context.counters["tags_seen"], len(tags)
        )
        await self._checkpoint(
            context,
            None,
            completed,
            total,
            f"Catalogs complete · {len(albums)} albums · {len(tags)} tags",
        )
        return completed, total

    async def _checkpoint(
        self,
        context: SyncStepContext,
        cursor: str | None,
        completed: int,
        total: int,
        detail: str,
    ) -> None:
        context.cursor = cursor
        await context.checkpoint_callback(
            cursor,
            context.counters,
            SyncStepProgress(
                phase=self.phase,
                completed=completed,
                total=total,
                detail=detail,
            ),
        )



class AssetSyncStep(SyncStep[AssetScope]):
    """Synchronize assets from remote traversal or a typed selected-asset scope."""

    name = "assets"
    phase = "assets"

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        selections: SyncSelectionResolver | None = None,
        *,
        page_prefetch: int = 0,
    ) -> None:
        if page_prefetch < 0:
            raise ValueError("page_prefetch cannot be negative")
        self._immich = immich
        self._assets = assets
        self._selections = selections
        self._page_prefetch = page_prefetch

    async def run(
        self,
        context: SyncStepContext,
        scope: AssetScope,
    ) -> SyncStepResult:
        result = await super().run(context, scope)
        if result.skipped:
            return result

        selection = scope.selection
        if isinstance(selection, AllSelection):
            authority = SyncAuthority.COMPLETE
        elif isinstance(selection, WindowSelection):
            authority = SyncAuthority.WINDOW
        else:
            authority = SyncAuthority.SELECTED

        return SyncStepResult(
            name=result.name,
            phase=result.phase,
            skipped=result.skipped,
            completed=result.completed,
            total=result.total,
            counters=result.counters,
            evidence=[
                SyncEvidence(
                    domain="assets",
                    authority=authority,
                    selection=selection,
                    generation=context.generation,
                )
            ],
            outputs=result.outputs,
        )

    async def execute(
        self,
        context: SyncStepContext,
        scope: AssetScope,
    ) -> tuple[int, int | None]:
        if context.config.batch_size is None:
            raise ValueError("AssetSyncStep requires config.batch_size")

        for counter in (
            "assets_seen",
            "assets_created",
            "assets_updated",
            "assets_unchanged",
            "tag_cheap_path_eligible_assets",
            "tag_cheap_path_fallback_assets",
        ):
            context.counters.setdefault(counter, 0)

        if isinstance(scope.selection, (AllSelection, WindowSelection)):
            return await self._execute_remote(context, scope)
        return await self._execute_selected(context, scope)

    async def _execute_remote(
        self,
        context: SyncStepContext,
        scope: AssetScope,
    ) -> tuple[int, int | None]:
        if context.config.page_size is None:
            raise ValueError("AssetSyncStep remote traversal requires config.page_size")

        updated_after = None
        updated_before = None
        if isinstance(scope.selection, WindowSelection):
            updated_after = scope.selection.start
            updated_before = scope.selection.end

        total: int | None = None
        count_assets = getattr(self._immich, "count_assets", None)
        if count_assets is not None:
            try:
                total = await count_assets(
                    updated_after=updated_after,
                    updated_before=updated_before,
                )
            except ImmichApiError:
                total = None

        await self._checkpoint(
            context,
            context.cursor,
            context.counters["assets_seen"],
            total,
            (
                f"Preparing {total} media items"
                if total is not None
                else "Preparing media traversal"
            ),
        )

        batch_size = context.config.batch_size
        page_size = context.config.page_size
        start_page = 1
        completed_page_batches = 0
        if context.cursor:
            cursor_parts = context.cursor.split(":")
            if len(cursor_parts) == 3:
                start_page = int(cursor_parts[1])
                completed_page_batches = int(cursor_parts[2])
            else:
                completed_batches = int(cursor_parts[-1])
                completed_assets = completed_batches * batch_size
                start_page = completed_assets // page_size + 1
                completed_page_batches = (completed_assets % page_size) // batch_size

        iterator = prefetch_async(
            self._immich.iter_asset_pages(
                page_size=page_size,
                updated_after=updated_after,
                updated_before=updated_before,
                start_page=start_page,
            ),
            self._page_prefetch,
        )
        async for page_number, page in iterator:
            for batch_number, batch in enumerate(batches(page.items, batch_size), start=1):
                if page_number == start_page and batch_number <= completed_page_batches:
                    continue
                await self._commit_batch(
                    context,
                    batch,
                    f"assets:{page_number}:{batch_number}",
                    total,
                )
            if page.next_page is not None:
                await self.pace_page(context)

        return context.counters["assets_seen"], total

    async def _execute_selected(
        self,
        context: SyncStepContext,
        scope: AssetScope,
    ) -> tuple[int, int | None]:
        if self._selections is None:
            raise ValueError("Selected asset synchronization requires SyncSelectionResolver")

        selection = scope.selection
        assert isinstance(
            selection,
            (
                ExplicitIdsSelection,
                PersistedSelection,
                RequestSelection,
                GenerationSelection,
            ),
        )
        total = (
            len(dict.fromkeys(selection.ids))
            if isinstance(selection, ExplicitIdsSelection)
            else None
        )
        completed_batches = 0
        if context.cursor:
            cursor_parts = context.cursor.split(":")
            if len(cursor_parts) == 3 and cursor_parts[1] == "0":
                completed_batches = int(cursor_parts[2])

        await self._checkpoint(
            context,
            context.cursor,
            context.counters["assets_seen"],
            total,
            (
                f"Preparing {total} selected media items"
                if total is not None
                else "Preparing selected media traversal"
            ),
        )

        batch_number = 0
        async for asset_ids in self._selections.iter_asset_ids(
            selection,
            batch_size=context.config.batch_size,
        ):
            batch_number += 1
            if batch_number <= completed_batches:
                continue
            started = perf_counter()
            details = await self._fetch_assets(context, asset_ids)
            await self._commit_batch(
                context,
                details,
                f"assets:0:{batch_number}",
                total,
            )
            await self.pace(context, started)

        return context.counters["assets_seen"], total

    async def _fetch_assets(
        self,
        context: SyncStepContext,
        asset_ids: list[UUID],
    ) -> list[ImmichAsset]:
        semaphore = asyncio.Semaphore(context.config.concurrency)

        async def fetch(asset_id: UUID) -> ImmichAsset:
            async with semaphore:
                return await self._immich.get_asset(asset_id)

        return list(await asyncio.gather(*(fetch(asset_id) for asset_id in asset_ids)))

    async def _commit_batch(
        self,
        context: SyncStepContext,
        batch: list[ImmichAsset],
        cursor: str,
        total: int | None,
    ) -> None:
        context.counters["tag_cheap_path_eligible_assets"] += sum(
            1 for asset in batch if asset.includes_tags
        )
        context.counters["tag_cheap_path_fallback_assets"] += sum(
            1 for asset in batch if not asset.includes_tags
        )
        lightweight_batch = [
            asset.model_copy(
                update={"exif_info": None, "people": [], "tags": [], "stack": None}
            )
            for asset in batch
        ]
        created, updated, unchanged = await self._assets.upsert_asset_batch(
            lightweight_batch,
            context.generation,
            track_similarity_changes=True,
        )
        context.counters["assets_seen"] += created + updated + unchanged
        context.counters["assets_created"] += created
        context.counters["assets_updated"] += updated
        context.counters["assets_unchanged"] += unchanged
        await self._checkpoint(
            context,
            cursor,
            context.counters["assets_seen"],
            total,
            (
                f"Media {context.counters['assets_seen']}/{total}"
                if total is not None
                else f"Media {context.counters['assets_seen']} processed"
            ),
        )

    async def pace_page(self, _context: SyncStepContext) -> None:
        """Pace remote pages when the orchestrated runtime requests it."""

        return None

    async def _checkpoint(
        self,
        context: SyncStepContext,
        cursor: str | None,
        completed: int,
        total: int | None,
        detail: str,
    ) -> None:
        context.cursor = cursor
        await context.checkpoint_callback(
            cursor,
            context.counters,
            SyncStepProgress(
                phase=self.phase,
                completed=completed,
                total=total,
                detail=detail,
            ),
        )

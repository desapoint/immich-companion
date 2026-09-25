"""Canonical composable synchronization-step contracts."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter

from companion.asset_repository import AssetRepository
from companion.immich import ImmichAlbum, ImmichApiClient, ImmichTag
from companion.sync_schema import SyncMode
from companion.synchronization.evidence import SyncEvidence
from companion.synchronization.scopes import CatalogScope, SyncStepName
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    PersistedSelection,
    SyncSelectionResolver,
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

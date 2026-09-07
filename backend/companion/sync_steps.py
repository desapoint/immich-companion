"""Composable V2 synchronization steps.

This module is intentionally independent from the V1/legacy synchronization path.  A
step owns one unit of synchronization work, exposes the same processed/total progress
shape whether it is run as part of a staged sync or manually, and accepts operational
settings explicitly so later steps can opt into bounded page concurrency without
inventing a second execution model.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Generic, TypeVar

from companion.asset_repository import AssetRepository
from companion.immich import ImmichAlbum, ImmichApiClient, ImmichTag
from companion.sync_schema import SyncMode

InputT = TypeVar("InputT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True, slots=True)
class SyncStepConditionals:
    """Conditions applied when a step participates in a normal staged sync.

    Manual execution can either respect these conditions or explicitly bypass them.
    Keeping that choice in the execution request is important: the step itself does not
    need a separate manual-only implementation.
    """

    enabled: bool = True
    run_on_full: bool = True
    run_on_incremental: bool = True

    def allows(self, mode: SyncMode) -> bool:
        if not self.enabled:
            return False
        return self.run_on_full if mode == "full" else self.run_on_incremental


@dataclass(frozen=True, slots=True)
class SyncStepConfig:
    """Standard operational controls shared by every V2 sync step.

    ``concurrency`` is deliberately generic.  Relationship/tag synchronization can use
    it for association waves and the asset step can use the same setting for multiple
    pages in flight once that step is extracted.  ``page_size`` is optional because not
    every step is paged; ``batch_size`` is optional for the same reason.
    """

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
    """Stable progress contract for staged and manual step execution."""

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


@dataclass(slots=True)
class SyncStepContext:
    """Execution state supplied by either the staged coordinator or a manual task."""

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

    async def checkpoint(
        self,
        *,
        cursor: str | None,
        completed: int,
        total: int | None,
        detail: str | None,
    ) -> None:
        self.cursor = cursor
        await self.checkpoint_callback(
            cursor,
            self.counters,
            SyncStepProgress(
                phase="",
                completed=completed,
                total=total,
                detail=detail,
            ),
        )


@dataclass(frozen=True, slots=True)
class SyncStepResult:
    """Result returned by one step, suitable for task summaries and UI state."""

    name: str
    phase: str
    skipped: bool
    completed: int
    total: int | None
    counters: dict[str, int]


class SyncStep(ABC, Generic[InputT]):
    """Base class for independently runnable V2 synchronization steps."""

    name: str
    phase: str

    def should_run(self, context: SyncStepContext) -> bool:
        if context.manual and not context.respect_conditionals:
            return True
        return context.config.conditionals.allows(context.mode)

    async def run(self, context: SyncStepContext, data: InputT) -> SyncStepResult:
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
    async def execute(self, context: SyncStepContext, data: InputT) -> tuple[int, int | None]:
        """Execute the step and return ``(processed, total)``."""

    async def pace(self, context: SyncStepContext, started: float) -> None:
        """Apply a minimum batch duration without coupling the step to global settings."""

        delay = context.config.min_batch_delay_seconds
        if delay <= 0:
            return
        elapsed = perf_counter() - started
        await asyncio.sleep(max(0.0, delay - elapsed))

    async def bounded_map(
        self,
        context: SyncStepContext,
        items: Sequence[InputT],
        worker: Callable[[InputT], Awaitable[ResultT]],
    ) -> list[ResultT]:
        """Run work with bounded concurrency while preserving input/result order.

        This helper is intended for paged steps such as assets.  Fetch/transform work can
        happen concurrently, while callers can still commit/checkpoint results in page
        order so restart cursors remain monotonic and deterministic.
        """

        semaphore = asyncio.Semaphore(context.config.concurrency)

        async def guarded(item: InputT) -> ResultT:
            async with semaphore:
                return await worker(item)

        return list(await asyncio.gather(*(guarded(item) for item in items)))


@dataclass(frozen=True, slots=True)
class CatalogSyncInput:
    albums: Sequence[ImmichAlbum]
    tags: Sequence[ImmichTag]


class CatalogSyncStep(SyncStep[CatalogSyncInput]):
    """V2 step 1: synchronize album and tag catalogs.

    Cursor and counter semantics intentionally mirror the current staged sync:
    ``albums:<batch>`` then ``tags:<batch>``, with ``albums_seen``/``tags_seen``
    counting rows observed by persistence.  That makes the extraction compatible with
    existing restart and progress behavior while making the step independently runnable.
    """

    name = "catalogs"
    phase = "catalogs"

    def __init__(self, assets: AssetRepository) -> None:
        self._assets = assets

    @staticmethod
    async def load(immich: ImmichApiClient) -> CatalogSyncInput:
        albums, tags = await asyncio.gather(
            immich.list_album_catalog(),
            immich.list_tag_catalog(),
        )
        return CatalogSyncInput(albums=albums, tags=tags)

    @staticmethod
    def _batches[T](items: Sequence[T], size: int) -> list[Sequence[T]]:
        return [items[index : index + size] for index in range(0, len(items), size)]

    async def execute(
        self,
        context: SyncStepContext,
        data: CatalogSyncInput,
    ) -> tuple[int, int]:
        if context.config.batch_size is None:
            raise ValueError("CatalogSyncStep requires config.batch_size")

        albums = data.albums
        tags = data.tags
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
            cursor=context.cursor,
            completed=min(context.counters["albums_seen"], len(albums))
            + min(context.counters["tags_seen"], len(tags)),
            total=total,
            detail=f"Preparing {len(albums)} albums and {len(tags)} tags",
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
                cursor=f"albums:{index}",
                completed=min(context.counters["albums_seen"], len(albums)),
                total=total,
                detail=(
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
                cursor=f"tags:{index}",
                completed=len(albums) + min(context.counters["tags_seen"], len(tags)),
                total=total,
                detail=(
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
            cursor=None,
            completed=completed,
            total=total,
            detail=f"Catalogs complete · {len(albums)} albums · {len(tags)} tags",
        )
        return completed, total

    async def _checkpoint(
        self,
        context: SyncStepContext,
        *,
        cursor: str | None,
        completed: int,
        total: int,
        detail: str,
    ) -> None:
        context.cursor = cursor
        progress = SyncStepProgress(
            phase=self.phase,
            completed=completed,
            total=total,
            detail=detail,
        )
        await context.checkpoint_callback(cursor, context.counters, progress)

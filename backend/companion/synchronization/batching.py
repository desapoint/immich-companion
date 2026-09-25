"""Bounded batching and prefetch primitives shared by synchronization flows."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress


def batches[T](items: list[T], size: int) -> list[list[T]]:
    """Split an already compact collection into bounded persistence batches."""

    return [items[index : index + size] for index in range(0, len(items), size)]


async def async_batches_with_last[T](
    items: AsyncIterator[T], size: int
) -> AsyncIterator[tuple[list[T], bool]]:
    """Yield bounded async batches and identify the final batch."""

    batch: list[T] = []
    async for item in items:
        batch.append(item)
        if len(batch) > size:
            overflow = batch.pop()
            yield batch, False
            batch = [overflow]
    if batch:
        yield batch, True


async def async_items_with_last[T](
    items: AsyncIterator[T],
) -> AsyncIterator[tuple[T, bool]]:
    """Yield async items with one-item lookahead."""

    previous: T | None = None
    has_previous = False
    async for item in items:
        if has_previous:
            assert previous is not None
            yield previous, False
        previous = item
        has_previous = True
    if has_previous:
        assert previous is not None
        yield previous, True


async def enumerate_async[T](
    items: AsyncIterator[T], start: int = 0
) -> AsyncIterator[tuple[int, T]]:
    """Enumerate an asynchronous iterator without materializing it."""

    index = start
    async for item in items:
        yield index, item
        index += 1


async def prefetch_async[T](items: AsyncIterator[T], ahead: int) -> AsyncIterator[T]:
    """Bound asynchronous lookahead so remote reads overlap persistence."""

    if ahead <= 0:
        async for item in items:
            yield item
        return
    queue: asyncio.Queue[tuple[bool, T | BaseException | None]] = asyncio.Queue(
        maxsize=ahead
    )

    async def produce() -> None:
        try:
            async for item in items:
                await queue.put((True, item))
        except BaseException as error:
            await queue.put((False, error))
        finally:
            await queue.put((False, None))

    producer = asyncio.create_task(produce(), name="sync-page-prefetch")
    try:
        while True:
            available, value = await queue.get()
            if available:
                yield value  # type: ignore[misc]
                continue
            if isinstance(value, BaseException):
                raise value
            return
    finally:
        producer.cancel()
        with suppress(asyncio.CancelledError):
            await producer

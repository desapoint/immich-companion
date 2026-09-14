"""Durable rebuilds for the provider-neutral composite duplicate projection."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from companion.composite_duplicate_repository import (
    CompositeDuplicateRepository,
    CompositeDuplicateSnapshotAssetMissingError,
)
from companion.discovery.base import GroupDiscoveryProvider
from companion.task_coordinator import PermanentTaskError, TaskContext, TaskCoordinator
from companion.task_schema import TaskResult

COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE = "composite_duplicate_rebuild"
COMPOSITE_DUPLICATE_REBUILD_DEDUPLICATION_KEY = "authoritative_projection"

logger = logging.getLogger("uvicorn.error")


class CompositeDuplicateRebuildTaskHandler:
    """Materialize the current provider-composed groups into one atomic DB generation."""

    task_type = COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE
    lane_key = COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE
    max_concurrency = 1

    def __init__(
        self,
        discovery: GroupDiscoveryProvider,
        repository: CompositeDuplicateRepository,
    ) -> None:
        self._discovery = discovery
        self._repository = repository

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        del payload
        await context.checkpoint(
            checkpoint={"phase": "discovering"},
            counters={},
            progress={
                "phase": "composite_duplicates_discover",
                "completed": 0,
                "total": None,
                "percent": None,
                "detail": "Composing persisted duplicate providers",
            },
        )
        groups = await self._discovery.discover()
        member_count = sum(len(group.assets) for group in groups)
        evidence_count = sum(len(group.evidence) for group in groups)
        await context.checkpoint(
            checkpoint={"phase": "publishing"},
            counters={
                "groups": len(groups),
                "members": member_count,
                "evidence": evidence_count,
            },
            progress={
                "phase": "composite_duplicates_publish",
                "completed": 0,
                "total": len(groups),
                "percent": 0.0 if groups else 100.0,
                "detail": f"Publishing {len(groups)} composite duplicate groups",
            },
        )
        try:
            metadata = await self._repository.replace_snapshot(groups)
        except CompositeDuplicateSnapshotAssetMissingError as error:
            raise PermanentTaskError(str(error)) from error
        counters = {
            "groups": metadata.group_count,
            "members": metadata.member_count,
            "evidence": metadata.evidence_count,
        }
        await context.checkpoint(
            checkpoint={"phase": "published", "generation": metadata.authoritative_generation},
            counters=counters,
            progress={
                "phase": "composite_duplicates_publish",
                "completed": metadata.group_count,
                "total": metadata.group_count,
                "percent": 100.0,
                "detail": f"Published {metadata.group_count} composite duplicate groups",
            },
        )
        return TaskResult(
            summary={
                "generation": metadata.authoritative_generation,
                "group_count": metadata.group_count,
                "member_count": metadata.member_count,
                "evidence_count": metadata.evidence_count,
            },
            counters=counters,
        )


class CompositeDuplicateSyncService:
    """Submit and await idempotent composite projection rebuilds."""

    def __init__(self, tasks: TaskCoordinator) -> None:
        self._tasks = tasks

    async def start(self) -> UUID:
        task = await self._tasks.submit(
            COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE,
            {},
            priority=18,
            deduplication_key=COMPOSITE_DUPLICATE_REBUILD_DEDUPLICATION_KEY,
        )
        await self._tasks.start()
        return task.id

    async def refresh_and_wait(self) -> object | None:
        """Rebuild after a source generation changes and wait for publication."""

        task_id = await self.start()
        completed = await self._tasks.wait(task_id)
        if completed.status != "completed":
            raise RuntimeError("Composite duplicate rebuild did not complete")
        return completed

    async def start_after_source_change(self) -> object | None:
        """Best-effort durable follow-up that must not fail the source task."""

        try:
            return await self.refresh_and_wait()
        except Exception:
            logger.exception("Could not rebuild composite duplicate projection")
            return None


class FollowUpTaskHandler:
    """Run one best-effort durable follow-up after a delegate task succeeds."""

    def __init__(
        self,
        delegate: Any,
        after_success: Callable[[], Awaitable[object | None]],
    ) -> None:
        self._delegate = delegate
        self._after_success = after_success
        self.task_type = delegate.task_type
        self.lane_key = getattr(delegate, "lane_key", delegate.task_type)
        self.max_concurrency = getattr(delegate, "max_concurrency", 1)
        self.supports_pause = getattr(delegate, "supports_pause", False)

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        result = await self._delegate.execute(context, payload)
        try:
            await self._after_success()
        except Exception:
            logger.exception(
                "Task %s completed but its composite duplicate follow-up failed",
                self.task_type,
            )
        return result

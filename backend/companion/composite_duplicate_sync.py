"""Durable rebuilds for the provider-neutral composite duplicate projection."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from companion.composite_duplicate_repository import (
    CompositeDuplicateRepository,
    CompositeDuplicateSnapshotAssetMissingError,
    CompositeDuplicateSnapshotMetadata,
)
from companion.discovery.base import GroupDiscoveryProvider
from companion.runtime_metrics import reclaim_process_memory
from companion.similarity_generation import SimilarityEvidenceEpochRepository
from companion.task_coordinator import PermanentTaskError, TaskContext, TaskCoordinator
from companion.task_schema import TaskResult

COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE = "composite_duplicate_rebuild"
COMPOSITE_DUPLICATE_REBUILD_DEDUPLICATION_KEY = "authoritative_projection"
COMPOSITE_DUPLICATE_STARTUP_RECONCILE_TASK_TYPE = "composite_duplicate_startup_reconcile"
COMPOSITE_DUPLICATE_STARTUP_RECONCILE_DEDUPLICATION_KEY = "startup_projection"
SOURCE_CHANGING_TASK_TYPES = frozenset(
    {"immich_duplicate_sync", "similarity_scan", "similarity_maintenance"}
)
SOURCE_CHANGING_ACTIVE_STATUSES = frozenset(
    {"queued", "running", "retrying", "recovering", "pause_requested", "cancel_requested"}
)

logger = logging.getLogger("uvicorn.error")


def source_change_in_progress(tasks: list[object]) -> bool:
    """Return whether source-changing work can still publish a newer generation."""

    return any(
        getattr(task, "task_type", None) in SOURCE_CHANGING_TASK_TYPES
        and getattr(task, "status", None) in SOURCE_CHANGING_ACTIVE_STATUSES
        for task in tasks
    )


def composite_projection_is_stale(
    composite_last_success_at: datetime | None,
    immich_last_success_at: datetime | None,
    similarity_last_success_at: datetime | None,
) -> bool:
    """Return whether a source snapshot is newer than the composite publication."""

    if composite_last_success_at is None:
        return True
    return any(
        source_time is not None and source_time > composite_last_success_at
        for source_time in (immich_last_success_at, similarity_last_success_at)
    )


class CompositeDuplicateStartupReconcileTaskHandler:
    """Repair a stale startup projection after source-changing work becomes idle."""

    task_type = COMPOSITE_DUPLICATE_STARTUP_RECONCILE_TASK_TYPE
    lane_key = COMPOSITE_DUPLICATE_STARTUP_RECONCILE_TASK_TYPE
    max_concurrency = 1

    def __init__(
        self,
        tasks: TaskCoordinator,
        projection_is_stale: Callable[[], Awaitable[bool]],
        refresh_projection: Callable[[], Awaitable[object | None]],
    ) -> None:
        self._tasks = tasks
        self._projection_is_stale = projection_is_stale
        self._refresh_projection = refresh_projection

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        del payload
        waiting_reported = False
        while True:
            await context.ensure_active()
            active_tasks = await self._tasks.list_tasks(active_only=True, limit=100)
            if not source_change_in_progress(active_tasks):
                break
            if not waiting_reported:
                await context.checkpoint(
                    checkpoint={"phase": "waiting_for_sources"},
                    counters={},
                    progress={
                        "phase": "composite_duplicates_startup_wait",
                        "completed": 0,
                        "total": None,
                        "percent": None,
                        "detail": (
                            "Waiting for duplicate source work before startup reconciliation"
                        ),
                    },
                )
                waiting_reported = True
            await asyncio.sleep(2.0)

        if not await self._projection_is_stale():
            return TaskResult(
                summary={"projection_refreshed": False, "reason": "already_current"},
                counters={},
            )

        await context.checkpoint(
            checkpoint={"phase": "refreshing_projection"},
            counters={},
            progress={
                "phase": "composite_duplicates_startup_refresh",
                "completed": 0,
                "total": 1,
                "percent": 0.0,
                "detail": "Refreshing stale duplicate projection after startup",
            },
        )
        await self._refresh_projection()
        return TaskResult(
            summary={"projection_refreshed": True},
            counters={},
        )


class CompositeDuplicateStartupReconcileService:
    """Submit one durable, nonblocking startup projection reconciliation."""

    def __init__(self, tasks: TaskCoordinator) -> None:
        self._tasks = tasks

    async def start(self) -> UUID:
        task = await self._tasks.submit(
            COMPOSITE_DUPLICATE_STARTUP_RECONCILE_TASK_TYPE,
            {},
            priority=4,
            deduplication_key=COMPOSITE_DUPLICATE_STARTUP_RECONCILE_DEDUPLICATION_KEY,
        )
        await self._tasks.start()
        return task.id


class CompositeDuplicateRebuildTaskHandler:
    """Materialize the current provider-composed groups into one atomic DB generation."""

    task_type = COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE
    lane_key = COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE
    max_concurrency = 1

    def __init__(
        self,
        discovery: GroupDiscoveryProvider,
        repository: CompositeDuplicateRepository,
        *,
        after_publish: Callable[[], Awaitable[object]] | None = None,
    ) -> None:
        self._discovery = discovery
        self._repository = repository
        self._after_publish = after_publish
        # The persisted composite projection includes the latest similarity scan. Capture
        # the same database-backed epoch used by similarity writers so a rebuild cannot
        # publish groups discovered before a manual evidence reset. Lightweight test
        # repositories without a database keep the legacy contract.
        self._database = getattr(repository, "_database", None)
        self._evidence_epochs = (
            SimilarityEvidenceEpochRepository(self._database)
            if self._database is not None
            else None
        )

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        del payload
        evidence_epoch = (
            await self._evidence_epochs.capture_epoch()
            if self._evidence_epochs is not None
            else None
        )
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
        discover_batches = getattr(self._discovery, "discover_batches", None)
        replace_batches = getattr(self._repository, "replace_snapshot_batches", None)
        use_bounded_path = callable(discover_batches) and callable(replace_batches)

        async def publish() -> CompositeDuplicateSnapshotMetadata:
            if use_bounded_path:
                discovered_groups = 0

                async def monitored_batches():
                    nonlocal discovered_groups
                    async for batch in discover_batches():
                        discovered_groups += len(batch)
                        await context.checkpoint(
                            checkpoint={"phase": "publishing", "groups": discovered_groups},
                            counters={"groups": discovered_groups},
                            progress={
                                "phase": "composite_duplicates_publish",
                                "completed": discovered_groups,
                                "total": None,
                                "percent": None,
                                "detail": (
                                    f"Publishing composite duplicate groups · "
                                    f"{discovered_groups} streamed"
                                ),
                            },
                        )
                        yield batch

                return await replace_batches(monitored_batches())

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
            return await self._repository.replace_snapshot(groups)

        try:
            if (
                self._evidence_epochs is not None
                and self._database is not None
                and evidence_epoch is not None
            ):
                # Keep the epoch's shared row lock open across the independent snapshot
                # transaction. A rebuild needs an exclusive lock on the same row, so
                # either this old projection commits first and is then cleared, or the
                # rebuild wins and this publication is rejected as stale.
                async with self._database.sessions() as session, session.begin():
                    await self._evidence_epochs.assert_current(session, evidence_epoch)
                    metadata = await publish()
            else:
                metadata = await publish()
        except CompositeDuplicateSnapshotAssetMissingError as error:
            raise PermanentTaskError(str(error)) from error
        pruned_pair_generations = 0
        if self._after_publish is not None:
            try:
                cleanup_result = await self._after_publish()
                if isinstance(cleanup_result, int) and not isinstance(cleanup_result, bool):
                    pruned_pair_generations = cleanup_result
            except Exception:
                logger.exception(
                    "Post-publish duplicate projection cleanup failed; "
                    "published projection remains authoritative"
                )

        counters = {
            "groups": metadata.group_count,
            "members": metadata.member_count,
            "evidence": metadata.evidence_count,
        }
        if pruned_pair_generations:
            counters["similarity_pair_generations_pruned"] = pruned_pair_generations
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
    """Submit and await one serialized rebuild per committed source change."""

    def __init__(self, tasks: TaskCoordinator) -> None:
        self._tasks = tasks

    async def start(self) -> UUID:
        # Source tasks have independent commit boundaries. Never coalesce a later
        # source commit into an older in-flight projection rebuild; the composite
        # lane already serializes these tasks without losing generations.
        task = await self._tasks.submit(
            COMPOSITE_DUPLICATE_REBUILD_TASK_TYPE,
            {},
            priority=18,
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
        """Publish the source change and fail the parent task if publication fails."""

        return await self.refresh_and_wait()


class FollowUpTaskHandler:
    """Run one required follow-up after a delegate task succeeds."""

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
        reclaim_process_memory()
        await context.checkpoint(
            checkpoint={"phase": "publishing_results"},
            counters=result.counters,
            progress={
                "phase": "duplicate_projection_publish",
                "completed": 0,
                "total": None,
                "percent": None,
                "detail": "Publishing duplicate results…",
            },
        )
        try:
            await self._after_success()
        except PermanentTaskError:
            raise
        except Exception as error:
            raise PermanentTaskError(
                f"{self.task_type} source work completed, but its required follow-up failed: "
                f"{error}"
            ) from error
        await context.checkpoint(
            checkpoint={"phase": "published_results"},
            counters=result.counters,
            progress={
                "phase": "duplicate_projection_publish",
                "completed": 1,
                "total": 1,
                "percent": 100.0,
                "detail": "Duplicate results published.",
            },
        )
        return result

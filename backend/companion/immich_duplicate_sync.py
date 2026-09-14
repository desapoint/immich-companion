"""Durable synchronization of Immich's duplicate-group snapshot."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from companion.duplicate_service import (
    CrossSourceDuplicateService,
    DuplicateResolutionTaskHandler,
)
from companion.immich import ImmichApiClient
from companion.immich_duplicate_repository import (
    ImmichDuplicateRepository,
    ImmichDuplicateSnapshotAssetMissingError,
)
from companion.task_coordinator import PermanentTaskError, TaskContext, TaskCoordinator
from companion.task_schema import TaskResult, TaskStatus

IMMICH_DUPLICATE_SYNC_TASK_TYPE = "immich_duplicate_sync"
IMMICH_DUPLICATE_SYNC_DEDUPLICATION_KEY = "authoritative_snapshot"
IMMICH_DUPLICATE_SYNC_MIN_INTERVAL = timedelta(minutes=5)

logger = logging.getLogger("uvicorn.error")


class ImmichDuplicateSyncTaskStart(BaseModel):
    task_id: UUID


class ImmichDuplicateSyncStatus(BaseModel):
    state: Literal[
        "never_synced",
        "idle",
        "queued",
        "running",
        "retrying",
        "recovering",
        "pause_requested",
        "paused",
        "cancel_requested",
        "failed",
    ]
    authoritative_generation: int
    group_count: int
    member_count: int
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    task_id: UUID | None = None
    task_status: TaskStatus | None = None
    error: str | None = None


class ImmichDuplicateSyncTaskHandler:
    """Fetch one complete Immich snapshot and publish it atomically."""

    task_type = IMMICH_DUPLICATE_SYNC_TASK_TYPE
    lane_key = IMMICH_DUPLICATE_SYNC_TASK_TYPE
    max_concurrency = 1

    def __init__(self, immich: ImmichApiClient, repository: ImmichDuplicateRepository) -> None:
        self._immich = immich
        self._repository = repository

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        del payload
        await context.checkpoint(
            checkpoint={"phase": "fetching"},
            counters={},
            progress={
                "phase": "immich_duplicates_fetch",
                "completed": 0,
                "total": None,
                "percent": None,
                "detail": "Fetching duplicate groups from Immich",
            },
        )
        groups = await self._immich.list_duplicate_groups()
        member_count = sum(len(group.assets) for group in groups)
        await context.checkpoint(
            checkpoint={"phase": "publishing"},
            counters={"groups": len(groups), "members": member_count},
            progress={
                "phase": "immich_duplicates_publish",
                "completed": 0,
                "total": len(groups),
                "percent": 0.0 if groups else 100.0,
                "detail": f"Publishing {len(groups)} duplicate groups",
            },
        )
        try:
            metadata = await self._repository.replace_snapshot(groups)
        except ImmichDuplicateSnapshotAssetMissingError as error:
            raise PermanentTaskError(str(error)) from error
        counters = {"groups": metadata.group_count, "members": metadata.member_count}
        await context.checkpoint(
            checkpoint={"phase": "published", "generation": metadata.authoritative_generation},
            counters=counters,
            progress={
                "phase": "immich_duplicates_publish",
                "completed": metadata.group_count,
                "total": metadata.group_count,
                "percent": 100.0,
                "detail": f"Published {metadata.group_count} duplicate groups",
            },
        )
        return TaskResult(
            summary={
                "generation": metadata.authoritative_generation,
                "group_count": metadata.group_count,
                "member_count": metadata.member_count,
            },
            counters=counters,
        )


class ImmichDuplicateSyncService:
    """Submit and report the durable Immich duplicate snapshot task."""

    def __init__(self, tasks: TaskCoordinator, repository: ImmichDuplicateRepository) -> None:
        self._tasks = tasks
        self._repository = repository

    async def start(self) -> ImmichDuplicateSyncTaskStart:
        task = await self._tasks.submit(
            IMMICH_DUPLICATE_SYNC_TASK_TYPE,
            {},
            priority=20,
            deduplication_key=IMMICH_DUPLICATE_SYNC_DEDUPLICATION_KEY,
        )
        await self._tasks.start()
        return ImmichDuplicateSyncTaskStart(task_id=task.id)

    async def start_after_asset_sync(self) -> object | None:
        """Queue a refresh without allowing follow-up failures to fail asset sync."""

        try:
            metadata = await self._repository.metadata()
            if (
                metadata.last_success_at is not None
                and datetime.now(UTC) - metadata.last_success_at
                < IMMICH_DUPLICATE_SYNC_MIN_INTERVAL
            ):
                return metadata
            return await self.start()
        except Exception:
            # This is deliberately a follow-up. Asset synchronization must remain
            # successful even if duplicate refresh status/submission is unavailable.
            logger.exception("Could not queue Immich duplicate synchronization after asset sync")
            return None

    async def status(self) -> ImmichDuplicateSyncStatus:
        metadata = await self._repository.metadata()
        active = await self._tasks.find_active(
            IMMICH_DUPLICATE_SYNC_TASK_TYPE,
            IMMICH_DUPLICATE_SYNC_DEDUPLICATION_KEY,
        )
        recent = await self._tasks.list_tasks(task_type=IMMICH_DUPLICATE_SYNC_TASK_TYPE, limit=1)
        latest = active or (recent[0] if recent else None)

        if active is not None:
            state = active.status
        elif latest is not None and latest.status == "failed":
            state = "failed"
        elif metadata.last_success_at is None:
            state = "never_synced"
        else:
            state = "idle"

        error = None
        if latest is not None and latest.error:
            raw = latest.error.get("message")
            error = str(raw) if raw else str(latest.error.get("type") or "Duplicate sync failed")
        return ImmichDuplicateSyncStatus(
            state=state,  # type: ignore[arg-type]
            authoritative_generation=metadata.authoritative_generation,
            group_count=metadata.group_count,
            member_count=metadata.member_count,
            last_success_at=metadata.last_success_at,
            last_attempt_at=latest.created_at if latest is not None else None,
            task_id=active.id if active is not None else latest.id if latest is not None else None,
            task_status=latest.status if latest is not None else None,
            error=error,
        )


class RefreshingDuplicateResolutionTaskHandler(DuplicateResolutionTaskHandler):
    """Refresh the authoritative Immich group projection after duplicate mutations."""

    def __init__(
        self,
        service: CrossSourceDuplicateService,
        duplicate_sync: ImmichDuplicateSyncService,
    ) -> None:
        super().__init__(service)
        self._duplicate_sync = duplicate_sync

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        result = await super().execute(context, payload)
        try:
            await self._duplicate_sync.start()
        except Exception:
            # Resolution already completed and was independently verified against Immich.
            # A snapshot refresh failure must not rewrite the resolution outcome.
            logger.exception("Could not queue Immich duplicate refresh after resolution")
        return result

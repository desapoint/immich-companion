"""Persistent, non-overlapping staged synchronization coordinator."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.asset_schema import AssetSyncResult
from companion.config import Settings
from companion.immich import (
    ImmichAlbum,
    ImmichApiClient,
    ImmichApiError,
    ImmichAsset,
    ImmichStack,
    ImmichTag,
)
from companion.sync_repository import SyncRepository, new_sync_owner
from companion.sync_schema import (
    SyncCoordinatorStatus,
    SyncEvent,
    SyncMode,
    SyncProgress,
    SyncRunStatus,
)
from companion.task_coordinator import TaskContext, TaskCoordinator
from companion.task_schema import TaskResult, TaskStatusView


def batches[T](items: list[T], size: int) -> list[list[T]]:
    """Split an already compact collection into bounded persistence batches."""

    return [items[index : index + size] for index in range(0, len(items), size)]


class _CoordinatorSyncRepository:
    """Adapt generic task context checkpoints to the legacy sync internals."""

    def __init__(self, context: TaskContext) -> None:
        self._context = context

    async def checkpoint(
        self, _run_id, _owner, *, phase, cursor, counters, progress=None, **_kwargs
    ):
        await self._context.checkpoint(
            checkpoint={"phase": phase, "cursor": cursor},
            counters=counters,
            progress=(
                progress.model_dump(mode="json") if progress is not None else {"phase": phase}
            ),
        )


class AssetSyncTaskHandler:
    """Run staged synchronization through the generic coordinator."""

    task_type = "asset_sync"
    lane_key = "asset_sync"
    max_concurrency = 1

    def __init__(self, service: AssetSyncService) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        service = self._service
        mode = payload.get("mode", "incremental")
        if "generation" not in payload or "window_end" not in payload:
            (
                generation,
                window_start,
                window_end,
            ) = await service._legacy_metadata.next_sync_metadata(
                mode,
                overlap=service._overlap,  # type: ignore[arg-type]
            )
            if mode == "incremental" and window_start is None:
                mode = "full"
            payload = {
                **payload,
                "mode": mode,
                "generation": generation,
                "window_start": window_start.isoformat() if window_start else None,
                "window_end": window_end.isoformat(),
            }
            await context.update_payload(payload)
        checkpoint = context.task.checkpoint
        phase = str(checkpoint.get("phase", "queued"))
        now = datetime.now(UTC)

        def parse(value: object, fallback: datetime | None = None) -> datetime | None:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return fallback

        window_end = parse(payload.get("window_end"), now)
        assert window_end is not None
        run = SyncRunStatus(
            id=context.task.id,
            mode=mode,  # type: ignore[arg-type]
            status="recovering" if context.task.status == "recovering" else "running",
            phase=phase,  # type: ignore[arg-type]
            generation=int(payload.get("generation", 0)),
            window_start=parse(payload.get("window_start")),
            window_end=window_end,
            cursor=checkpoint.get("cursor"),
            counters=context.task.counters,
            attempts=context.task.attempt,
            error=None,
            created_at=context.task.created_at,
            started_at=context.task.started_at,
            heartbeat_at=context.task.heartbeat_at,
            completed_at=None,
            progress=SyncProgress.model_validate(context.task.progress or {"phase": phase}),
        )
        previous = service._syncs
        service._syncs = _CoordinatorSyncRepository(context)  # type: ignore[assignment]
        try:
            counters = await service._execute(run, context.worker_id)
        finally:
            service._syncs = previous
        await service._legacy_metadata.record_success(
            mode=run.mode,
            generation=run.generation,
            watermark=run.window_end,
        )
        return TaskResult(
            summary={"mode": run.mode, "generation": run.generation}, counters=counters
        )


class AssetRepairTaskHandler:
    """Repair action-affected assets through the same task lifecycle."""

    task_type = "asset_repair"
    lane_key = "asset_repair"
    max_concurrency = 4

    def __init__(self, service: AssetSyncService) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        await self._service._repair_targets_now(
            [UUID(str(value)) for value in payload.get("asset_ids", [])]
        )
        return TaskResult(summary={"repaired": len(payload.get("asset_ids", []))})


class AssetRelationRepairTaskHandler:
    """Rebuild affected album/tag snapshots through the serialized sync lane."""

    task_type = "asset_relation_repair"
    lane_key = "asset_sync"
    max_concurrency = 1

    def __init__(self, service: AssetSyncService) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        relations = [
            (str(item["kind"]), UUID(str(item["id"])))
            for item in payload.get("relations", [])
            if isinstance(item, dict) and item.get("kind") in {"album", "tag"}
        ]
        counters = await self._service._repair_relations_now(relations)
        return TaskResult(summary=counters, counters=counters)


class AssetSyncService:
    """Queue and execute catalog-first staged sync runs under one durable lease."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        syncs: SyncRepository,
        settings: Settings,
        coordinator: TaskCoordinator | None = None,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._syncs = syncs
        self._settings = settings
        self._coordinator = coordinator
        self._legacy_metadata = syncs
        self._worker: asyncio.Task[None] | None = None
        self._scheduler: asyncio.Task[None] | None = None
        self._last_full_sync = monotonic()

    @staticmethod
    def _status_from_task(task: TaskStatusView) -> SyncRunStatus:
        """Project one generic task into the established sync response."""

        payload = task.payload
        checkpoint = task.checkpoint
        phase = str(checkpoint.get("phase", "queued"))
        phase = (
            phase
            if phase
            in {
                "queued",
                "catalogs",
                "assets",
                "stacks",
                "relationships",
                "finalizing",
                "completed",
                "failed",
            }
            else "queued"
        )
        status = task.status
        status = "recovering" if status == "cancel_requested" else status
        status = (
            status
            if status in {"queued", "running", "completed", "failed", "recovering", "retrying"}
            else "queued"
        )

        def parse_datetime(value: object, fallback: datetime | None = None) -> object:
            if not isinstance(value, str):
                return value if value is not None else fallback
            return datetime.fromisoformat(value)

        window_end = parse_datetime(payload.get("window_end"), task.created_at)
        assert isinstance(window_end, datetime)
        window_start = parse_datetime(payload.get("window_start"))
        return SyncRunStatus(
            id=task.id,
            task_id=task.id,
            mode=payload.get("mode", "incremental"),
            status=status,
            phase=phase,
            generation=int(payload.get("generation", 0)),
            window_start=window_start if isinstance(window_start, datetime) else None,
            window_end=window_end,
            cursor=checkpoint.get("cursor"),
            counters=task.counters,
            attempts=task.attempt,
            error=(task.error or {}).get("type") if task.error else None,
            created_at=task.created_at,
            started_at=task.started_at,
            heartbeat_at=task.heartbeat_at,
            completed_at=task.completed_at,
            retry_at=task.next_attempt_at,
            source="full" if payload.get("mode") == "full" else "window",
            progress=SyncProgress.model_validate(task.progress or {"phase": phase}),
        )

    @property
    def _lease_duration(self) -> timedelta:
        return timedelta(seconds=self._settings.sync_lease_seconds)

    @property
    def _overlap(self) -> timedelta:
        return timedelta(seconds=self._settings.sync_overlap_seconds)

    def wake(self) -> None:
        """Ensure this process competes for queued or recoverable work."""

        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._drain(), name="asset-sync-worker")
        if self._scheduler is None or self._scheduler.done():
            self._scheduler = asyncio.create_task(self._schedule(), name="asset-sync-scheduler")

    async def stop(self) -> None:
        """Stop local work safely; the durable lease can later be recovered."""

        if self._worker is not None and not self._worker.done():
            self._worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker
        if self._scheduler is not None and not self._scheduler.done():
            self._scheduler.cancel()
            with suppress(asyncio.CancelledError):
                await self._scheduler

    async def _schedule(self) -> None:
        """Submit periodic work; durable enqueue coalesces replica timers."""

        incremental = self._settings.sync_incremental_interval_seconds
        full = self._settings.sync_full_interval_seconds
        while True:
            await asyncio.sleep(min(incremental, 30))
            elapsed = monotonic() - self._last_full_sync
            mode: SyncMode = "full" if elapsed >= full else "incremental"
            if mode == "full":
                self._last_full_sync = monotonic()
            await self.start(mode)

    async def start(
        self,
        mode: SyncMode = "incremental",
        *,
        force_follow_up: bool = False,
    ) -> SyncRunStatus:
        """Persist sync intent, coalesce safely, and wake a background worker."""

        if self._coordinator is not None:
            if mode == "incremental":
                active_tasks = await self._coordinator.list_tasks(
                    task_type="asset_sync", limit=100
                )
                if any(
                    task.status
                    in {"queued", "running", "retrying", "recovering", "cancel_requested"}
                    and task.payload.get("mode") == "full"
                    for task in active_tasks
                ):
                    full_task = next(
                        task
                        for task in active_tasks
                        if task.status
                        in {"queued", "running", "retrying", "recovering", "cancel_requested"}
                        and task.payload.get("mode") == "full"
                    )
                    return self._status_from_task(full_task)
            requested_key = f"asset-sync:{mode}"
            existing = await self._coordinator.find_active("asset_sync", requested_key)
            if existing is not None:
                return self._status_from_task(existing)
            generation, window_start, window_end = await self._legacy_metadata.next_sync_metadata(
                mode, overlap=self._overlap
            )
            effective_mode: SyncMode = (
                "full" if mode == "incremental" and window_start is None else mode
            )
            deduplication_key = f"asset-sync:{effective_mode}"
            if effective_mode != mode:
                existing = await self._coordinator.find_active("asset_sync", deduplication_key)
                if existing is not None:
                    return self._status_from_task(existing)
            task = await self._coordinator.submit(
                "asset_sync",
                {
                    "mode": effective_mode,
                    "generation": generation,
                    "window_start": window_start.isoformat() if window_start else None,
                    "window_end": window_end.isoformat(),
                },
                priority=100 if effective_mode == "full" else 10,
                deduplication_key=deduplication_key,
                task_id=None,
            )
            await self._coordinator.start()
            return self._status_from_task(task)

        run = await self._syncs.enqueue(
            mode,
            overlap=self._overlap,
            force_follow_up=force_follow_up,
        )
        self.wake()
        return run

    async def status(self) -> SyncCoordinatorStatus:
        """Return shared persisted status and recover queued work when needed."""

        if self._coordinator is not None:
            tasks = await self._coordinator.list_tasks(task_type="asset_sync", limit=100)
            active_states = {"running", "recovering", "retrying", "cancel_requested"}
            queued_states = {"queued"}
            active_task = next((task for task in tasks if task.status in active_states), None)
            pending_task = next((task for task in tasks if task.status in queued_states), None)
            completed = [task for task in tasks if task.status == "completed"]
            last_task = completed[0] if completed else None
            last = self._status_from_task(last_task) if last_task else None
            return SyncCoordinatorStatus(
                active=self._status_from_task(active_task) if active_task else None,
                pending=self._status_from_task(pending_task) if pending_task else None,
                last_success=last,
                successful_watermark=last.window_end if last else None,
                authoritative_generation=(
                    max(
                        (
                            int(task.payload.get("generation", 0))
                            for task in completed
                            if task.payload.get("mode") == "full"
                        ),
                        default=0,
                    )
                ),
            )

        status = await self._syncs.status()
        if status.active is not None or status.pending is not None:
            self.wake()
        return status

    async def run_status(self, run_id: UUID) -> SyncRunStatus | None:
        """Return one durable run for audit and deterministic validation."""

        if self._coordinator is not None:
            task = await self._coordinator.get_status(run_id)
            if task is not None:
                return self._status_from_task(task)
            # Keep historical sync_runs readable while generic tasks are
            # authoritative for migrated and newly submitted work.
            return await self._legacy_metadata.get_run(run_id)

        return await self._syncs.get_run(run_id)

    async def wait(self, run_id: UUID) -> SyncRunStatus:
        """Wait for one durable run without coupling progress to an HTTP request."""

        if self._coordinator is not None:
            task = await self._coordinator.wait(run_id)
            result = self._status_from_task(task)
            if result.status == "failed":
                raise RuntimeError(f"Staged sync failed during {result.phase}")
            return result

        while True:
            run = await self._syncs.get_run(run_id)
            if run is None:
                raise RuntimeError("The staged sync run was not found")
            if run.status == "completed":
                return run
            if run.status == "failed":
                raise RuntimeError(f"Staged sync failed during {run.phase}")
            self.wake()
            await asyncio.sleep(0.25)

    async def synchronize(self, mode: SyncMode = "incremental") -> AssetSyncResult:
        """Compatibility wait path used by bootstrap and guarded actions."""

        run = await self.start(mode, force_follow_up=True)
        completed = await self.wait(run.id)
        counters = completed.counters
        return AssetSyncResult(
            seen=counters.get("assets_seen", 0),
            created=counters.get("assets_created", 0),
            updated=counters.get("assets_updated", 0),
            removed=counters.get("assets_removed", 0),
            completed_at=completed.completed_at or completed.window_end,
        )

    async def _drain(self) -> None:
        owner = new_sync_owner()
        while True:
            run = await self._syncs.claim_next(
                owner,
                lease_duration=self._lease_duration,
            )
            if run is None:
                status = await self._syncs.status()
                if status.active is None:
                    return
                await asyncio.sleep(self._settings.sync_lease_seconds / 2)
                continue
            try:
                counters = await self._execute_with_heartbeat(run, owner)
                await self._syncs.complete(run.id, owner, counters=counters)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                await self._syncs.fail(run.id, owner, error)
                transient = not isinstance(error, ImmichApiError) or error.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }
                if transient and run.attempts < self._settings.sync_max_attempts:
                    delay = min(
                        self._settings.sync_retry_backoff_seconds * (2 ** max(0, run.attempts - 1)),
                        300,
                    )
                    await asyncio.sleep(delay)
                    await self.start(run.mode)

    async def reconcile_targets(
        self,
        asset_ids: list[UUID],
        relations: list[tuple[str, UUID]] | None = None,
    ) -> None:
        """Repair action-affected asset metadata without a library-wide scan."""

        if relations:
            unique_relations = sorted(set(relations), key=lambda item: (item[0], str(item[1])))
            payload = {
                "relations": [
                    {"kind": kind, "id": str(relation_id)}
                    for kind, relation_id in unique_relations
                ]
            }
            if self._coordinator is not None:
                task = await self._coordinator.submit(
                    "asset_relation_repair",
                    payload,
                    priority=95,
                    deduplication_key="asset-relation-repair:"
                    + ",".join(f"{kind}:{relation_id}" for kind, relation_id in unique_relations),
                )
                await self._coordinator.start()
                await self._coordinator.wait(task.id)
                return
            await self._repair_relations_now(unique_relations)
            return

        if self._coordinator is not None:
            task = await self._coordinator.submit(
                "asset_repair",
                {"asset_ids": [str(asset_id) for asset_id in asset_ids]},
                priority=90,
                deduplication_key="asset-repair:"
                + ",".join(sorted(str(asset_id) for asset_id in asset_ids)),
            )
            await self._coordinator.start()
            await self._coordinator.wait(task.id)
            return

        await self._repair_targets_now(asset_ids)

    async def _repair_targets_now(self, asset_ids: list[UUID]) -> None:
        """Perform the remote reads used by an asset-repair handler."""

        assets = await asyncio.gather(
            *(self._immich.get_asset(identifier) for identifier in asset_ids)
        )
        for asset in assets:
            await self._assets.refresh_asset(asset)
            albums = await self._immich.list_albums_for_asset(asset.id)
            await self._assets.replace_asset_album_memberships(
                asset.id, [album.id for album in albums]
            )
            if asset.includes_tags:
                await self._assets.replace_asset_tag_memberships(
                    asset.id,
                    [UUID(str(tag["id"])) for tag in asset.tags if tag.get("id")],
                )
            else:
                tags = await self._immich.list_tag_catalog()
                present: list[UUID] = []
                for tag in tags:
                    async for page_ids in self._immich.iter_tag_asset_ids(tag.id):
                        if asset.id in page_ids:
                            present.append(tag.id)
                            break
                await self._assets.replace_asset_tag_memberships(asset.id, present)

    async def _repair_relations_now(self, relations: list[tuple[str, UUID]]) -> dict[str, int]:
        """Traverse each affected relation completely before replacing its snapshot."""

        counters = {"albums": 0, "tags": 0, "memberships": 0}
        for kind, relation_id in relations:
            asset_ids: list[UUID] = []
            iterator = (
                self._immich.iter_album_asset_ids(relation_id)
                if kind == "album"
                else self._immich.iter_tag_asset_ids(relation_id)
            )
            async for page_ids in iterator:
                asset_ids.extend(page_ids)
            if kind == "album":
                count = await self._assets.replace_album_memberships(relation_id, asset_ids)
                counters["albums"] += 1
            else:
                count = await self._assets.replace_tag_memberships(relation_id, asset_ids)
                counters["tags"] += 1
            counters["memberships"] += count
        return counters

    async def _execute_with_heartbeat(
        self,
        run: SyncRunStatus,
        owner: UUID,
    ) -> dict[str, int]:
        """Run one claim while renewing its lease during slow remote calls."""

        execution = asyncio.create_task(self._execute(run, owner))
        heartbeat = asyncio.create_task(self._heartbeat(run.id, owner))
        try:
            done, _ = await asyncio.wait(
                {execution, heartbeat},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeat in done:
                heartbeat.result()
                raise RuntimeError("The staged sync heartbeat stopped unexpectedly")
            return execution.result()
        finally:
            for task in (execution, heartbeat):
                if not task.done():
                    task.cancel()
            await asyncio.gather(execution, heartbeat, return_exceptions=True)

    async def _heartbeat(self, run_id: UUID, owner: UUID) -> None:
        interval = max(1.0, self._settings.sync_lease_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            await self._syncs.heartbeat(
                run_id,
                owner,
                lease_duration=self._lease_duration,
            )

    async def _checkpoint(
        self,
        run: SyncRunStatus,
        owner: UUID,
        counters: dict[str, int],
        phase: str,
        cursor: str | None,
        progress: SyncProgress | None = None,
    ) -> None:
        await self._syncs.checkpoint(
            run.id,
            owner,
            phase=phase,
            cursor=cursor,
            counters=counters,
            progress=progress,
            lease_duration=self._lease_duration,
        )

    @staticmethod
    def _progress(
        phase: str,
        completed: int,
        total: int | None,
        detail: str | None = None,
    ) -> SyncProgress:
        """Build safe phase progress, leaving the bar indeterminate when needed."""

        percent = (
            round(min(100.0, completed / total * 100), 1)
            if total is not None and total > 0
            else None
        )
        return SyncProgress(
            phase=phase,
            completed=max(0, completed),
            total=total,
            percent=percent,
            detail=detail,
        )

    async def _execute(self, run: SyncRunStatus, owner: UUID) -> dict[str, int]:
        defaults: dict[str, int] = {
            "albums_seen": 0,
            "tags_seen": 0,
            "assets_seen": 0,
            "assets_created": 0,
            "assets_updated": 0,
            "assets_unchanged": 0,
            "stacks_seen": 0,
            "stack_members": 0,
            "album_memberships": 0,
            "tag_memberships": 0,
            "assets_removed": 0,
        }
        counters = {**defaults, **run.counters}
        phase_order = {
            "queued": 0,
            "catalogs": 0,
            "assets": 1,
            "stacks": 2,
            "relationships": 3,
            "finalizing": 4,
        }
        start_phase = phase_order.get(run.phase, 0)

        capabilities = (
            await self._immich.sync_capabilities()
            if hasattr(self._immich, "sync_capabilities")
            else None
        )
        if capabilities is not None and capabilities.stream and run.mode == "incremental":
            await self._sync_events(run, owner, counters)

        albums, tags = await asyncio.gather(
            self._immich.list_album_catalog(),
            self._immich.list_tag_catalog(),
        )
        asset_total: int | None = None
        count_assets = getattr(self._immich, "count_assets", None)
        if count_assets is not None:
            try:
                asset_total = await count_assets(
                    updated_after=run.window_start if run.mode == "incremental" else None,
                    updated_before=run.window_end if run.mode == "incremental" else None,
                )
            except ImmichApiError:
                # A count is useful for feedback but must not make a valid sync fail.
                asset_total = None
        if start_phase <= 0:
            await self._checkpoint(
                run,
                owner,
                counters,
                "catalogs",
                run.cursor if run.phase == "catalogs" else None,
                self._progress(
                    "catalogs",
                    0,
                    len(albums) + len(tags),
                    f"Preparing {len(albums)} albums and {len(tags)} tags",
                ),
            )
            await self._sync_catalogs(run, owner, albums, tags, counters)
        if start_phase <= 1:
            await self._sync_assets(run, owner, counters, asset_total)
        if start_phase <= 2:
            await self._sync_stacks(run, owner, counters)
        if start_phase <= 3:
            await self._sync_relationships(run, owner, albums, tags, counters)

        await self._checkpoint(
            run,
            owner,
            counters,
            "finalizing",
            None,
            self._progress("finalizing", 0, 1, "Validating synchronized state"),
        )
        validated_counts = await self._assets.validate_generation(
            run.generation,
            counters,
            full=run.mode == "full",
            allow_counter_repair=run.attempts > 1,
        )
        counters.update(validated_counts)
        await self._checkpoint(
            run,
            owner,
            counters,
            "finalizing",
            "generation-valid",
            self._progress("finalizing", 1, 1, "Finalizing synchronized state"),
        )
        removed = await self._assets.finalize_generation(
            run.generation,
            remove_assets=run.mode == "full",
            batch_size=self._settings.sync_batch_size,
        )
        counters.update(removed)
        await self._assets.refresh_relation_counts()
        await self._checkpoint(
            run,
            owner,
            counters,
            "finalizing",
            "validated",
            self._progress("finalizing", 1, 1, "Synchronization complete"),
        )
        return counters

    async def _sync_events(
        self,
        run: SyncRunStatus,
        owner: UUID,
        counters: dict[str, int],
    ) -> None:
        """Apply optional remote deltas before the bounded repair scan."""

        cursor = run.cursor if run.phase == "queued" else None
        async for event in self._immich.iter_sync_events(cursor):
            await self._apply_event(event)
            if hasattr(self._immich, "acknowledge_sync_event"):
                await self._immich.acknowledge_sync_event(event.id)
            counters["events_seen"] = counters.get("events_seen", 0) + 1
            await self._checkpoint(run, owner, counters, "catalogs", f"event:{event.id}")

    async def _apply_event(self, event: SyncEvent) -> None:
        """Handle only events with enough data for an authoritative local write."""

        if event.kind == "asset_deleted" and event.entity_id is not None:
            await self._assets.remove_asset(event.entity_id)
            return
        if event.kind == "asset" and event.payload:
            await self._assets.refresh_asset(ImmichAsset.model_validate(event.payload))
            return
        if event.kind in {"album_membership", "tag_membership"}:
            relation_id = event.payload.get("relationId") or event.payload.get(
                "albumId" if event.kind == "album_membership" else "tagId"
            )
            asset_id = event.payload.get("assetId") or event.entity_id
            if relation_id is not None and asset_id is not None:
                present = bool(
                    event.payload.get("present", event.payload.get("action", "add") != "remove")
                )
                await self._assets.apply_membership_event(
                    "album" if event.kind == "album_membership" else "tag",
                    UUID(str(relation_id)),
                    UUID(str(asset_id)),
                    present,
                )

    async def _sync_catalogs(
        self,
        run: SyncRunStatus,
        owner: UUID,
        albums: list[ImmichAlbum],
        tags: list[ImmichTag],
        counters: dict[str, int],
    ) -> None:
        album_batches = batches(albums, self._settings.sync_batch_size)
        tag_batches = batches(tags, self._settings.sync_batch_size)
        completed_albums = 0
        completed_tags = 0
        if run.phase == "catalogs" and run.cursor:
            kind, value = run.cursor.split(":", 1)
            if kind == "albums":
                completed_albums = int(value)
            elif kind == "tags":
                completed_albums = len(album_batches)
                completed_tags = int(value)
        for index, album_batch in enumerate(album_batches, start=1):
            if index <= completed_albums:
                continue
            created, observed = await self._assets.upsert_album_catalog(album_batch, run.generation)
            counters["albums_seen"] += created + observed
            await self._checkpoint(
                run,
                owner,
                counters,
                "catalogs",
                f"albums:{index}",
                self._progress(
                    "catalogs",
                    counters["albums_seen"],
                    len(albums) + len(tags),
                    (
                        f"Albums {min(counters['albums_seen'], len(albums))}/{len(albums)} "
                        f"· tags 0/{len(tags)}"
                    ),
                ),
            )
        for index, tag_batch in enumerate(tag_batches, start=1):
            if index <= completed_tags:
                continue
            created, observed = await self._assets.upsert_tag_catalog(tag_batch, run.generation)
            counters["tags_seen"] += created + observed
            await self._checkpoint(
                run,
                owner,
                counters,
                "catalogs",
                f"tags:{index}",
                self._progress(
                    "catalogs",
                    len(albums) + min(counters["tags_seen"], len(tags)),
                    len(albums) + len(tags),
                    (
                        f"Albums {len(albums)}/{len(albums)} "
                        f"· tags {min(counters['tags_seen'], len(tags))}/{len(tags)}"
                    ),
                ),
            )
        await self._checkpoint(
            run,
            owner,
            counters,
            "assets",
            None,
            self._progress("assets", 0, None, "Preparing media traversal"),
        )

    async def _sync_assets(
        self,
        run: SyncRunStatus,
        owner: UUID,
        counters: dict[str, int],
        asset_total: int | None,
    ) -> None:
        batch = []
        completed_batches = 0
        if run.phase == "assets" and run.cursor:
            completed_batches = int(run.cursor.rsplit(":", 1)[1])
        batch_number = completed_batches
        iterator = self._immich.iter_assets(
            page_size=self._settings.sync_batch_size,
            updated_after=run.window_start if run.mode == "incremental" else None,
            updated_before=run.window_end if run.mode == "incremental" else None,
            start_page=completed_batches + 1,
        )
        if run.mode == "incremental":
            iterator = self._iter_incremental_details(iterator)
        async for asset in iterator:
            batch.append(asset)
            if len(batch) < self._settings.sync_batch_size:
                continue
            batch_number += 1
            await self._commit_asset_batch(run, owner, counters, batch, batch_number, asset_total)
            batch = []
        if batch:
            batch_number += 1
            await self._commit_asset_batch(run, owner, counters, batch, batch_number, asset_total)
        await self._checkpoint(run, owner, counters, "stacks", None)

    async def _iter_incremental_details(self, candidates):
        """Fetch each bounded incremental candidate through the detail endpoint."""

        async for candidate in candidates:
            yield await self._immich.get_asset(candidate.id)

    async def _commit_asset_batch(
        self,
        run: SyncRunStatus,
        owner: UUID,
        counters: dict[str, int],
        batch: list[ImmichAsset],
        batch_number: int,
        asset_total: int | None,
    ) -> None:
        created, updated, unchanged = await self._assets.upsert_asset_batch(
            batch,
            run.generation,
        )
        counters["assets_seen"] += created + updated + unchanged
        counters["assets_created"] += created
        counters["assets_updated"] += updated
        counters["assets_unchanged"] += unchanged
        await self._checkpoint(
            run,
            owner,
            counters,
            "assets",
            f"assets:{batch_number}",
            self._progress(
                "assets",
                counters["assets_seen"],
                asset_total,
                f"Media {counters['assets_seen']}/{asset_total}"
                if asset_total is not None
                else f"Media {counters['assets_seen']} processed",
            ),
        )

    @staticmethod
    def _stack_payload(stack: ImmichStack) -> tuple[dict[str, object], list[UUID]]:
        members = [
            {
                "id": str(member.id),
                "type": member.asset_type,
                "originalFileName": member.original_file_name,
                "originalMimeType": member.original_mime_type,
                "width": member.width,
                "height": member.height,
                "fileCreatedAt": member.file_created_at.isoformat(),
            }
            for member in stack.assets
        ]
        return (
            {
                "id": str(stack.id),
                "primaryAssetId": str(stack.primary_asset_id),
                "assetCount": len(stack.assets),
                "assets": members,
            },
            [member.id for member in stack.assets],
        )

    async def _sync_stacks(
        self,
        run: SyncRunStatus,
        owner: UUID,
        counters: dict[str, int],
    ) -> None:
        stacks = await self._immich.list_stacks()
        payloads = [self._stack_payload(stack) for stack in stacks]
        await self._checkpoint(
            run,
            owner,
            counters,
            "stacks",
            run.cursor if run.phase == "stacks" else None,
            self._progress("stacks", 0, len(payloads), f"Preparing {len(payloads)} stacks"),
        )
        completed_batches = 0
        if run.phase == "stacks" and run.cursor:
            completed_batches = int(run.cursor.rsplit(":", 1)[1])
        for index, stack_batch in enumerate(
            batches(payloads, self._settings.sync_batch_size), start=1
        ):
            if index <= completed_batches:
                continue
            counters["stack_members"] += await self._assets.apply_stack_batch(
                stack_batch, run.generation
            )
            counters["stacks_seen"] += len(stack_batch)
            await self._checkpoint(
                run,
                owner,
                counters,
                "stacks",
                f"stacks:{index}",
                self._progress(
                    "stacks",
                    min(counters["stacks_seen"], len(payloads)),
                    len(payloads),
                    f"Stacks {min(counters['stacks_seen'], len(payloads))}/{len(payloads)}",
                ),
            )
        await self._checkpoint(
            run,
            owner,
            counters,
            "relationships",
            None,
            self._progress("relationships", 0, None, "Preparing associations"),
        )

    async def _sync_relationships(
        self,
        run: SyncRunStatus,
        owner: UUID,
        albums: list[ImmichAlbum],
        tags: list[ImmichTag],
        counters: dict[str, int],
    ) -> None:
        relation_kind = ""
        completed_relation = 0
        completed_page = 0
        membership_total: int | None = None
        count_album = getattr(self._immich, "count_album_asset_ids", None)
        count_tag = getattr(self._immich, "count_tag_asset_ids", None)
        if count_album is not None and count_tag is not None:
            try:
                album_counts, tag_counts = await asyncio.gather(
                    asyncio.gather(*(count_album(album.id) for album in albums)),
                    asyncio.gather(*(count_tag(tag.id) for tag in tags)),
                )
                membership_total = sum(album_counts) + sum(tag_counts)
            except ImmichApiError:
                # The association traversal remains valid when count requests
                # are unavailable; only the visual estimate becomes indeterminate.
                membership_total = None
        association_completed = counters.get("album_memberships", 0) + counters.get(
            "tag_memberships", 0
        )
        await self._checkpoint(
            run,
            owner,
            counters,
            "relationships",
            run.cursor if run.phase == "relationships" else None,
            self._progress(
                "relationships",
                association_completed,
                membership_total,
                f"Preparing {len(albums)} album and {len(tags)} tag associations",
            ),
        )
        if run.phase == "relationships" and run.cursor:
            relation_kind, relation_text, page_text = run.cursor.split(":", 2)
            completed_relation = int(relation_text)
            completed_page = int(page_text)
        for relation_index, album in enumerate(albums, start=1):
            if relation_kind == "tags" or relation_index < completed_relation:
                continue
            start_page = (
                completed_page + 1
                if relation_kind == "albums" and relation_index == completed_relation
                else 1
            )
            page_number = start_page
            async for asset_ids in self._immich.iter_album_asset_ids(
                album.id,
                page_size=self._settings.sync_batch_size,
                start_page=start_page,
            ):
                counters["album_memberships"] += await self._assets.upsert_album_memberships(
                    album.id, asset_ids, run.generation
                )
                association_completed += len(asset_ids)
                await self._checkpoint(
                    run,
                    owner,
                    counters,
                    "relationships",
                    f"albums:{relation_index}:{page_number}",
                    self._progress(
                        "relationships",
                        association_completed,
                        membership_total,
                        (
                            f"Album associations {relation_index}/{len(albums)} "
                            f"· tag associations 0/{len(tags)}"
                        ),
                    ),
                )
                page_number += 1
            if page_number == start_page == 1:
                await self._checkpoint(
                    run,
                    owner,
                    counters,
                    "relationships",
                    f"albums:{relation_index}:0",
                    self._progress(
                        "relationships",
                        association_completed,
                        membership_total,
                        (
                            f"Album {relation_index}/{len(albums)} · "
                            f"{association_completed} associations"
                        ),
                    ),
                )
        for relation_index, tag in enumerate(tags, start=1):
            if relation_kind == "tags" and relation_index < completed_relation:
                continue
            start_page = (
                completed_page + 1
                if relation_kind == "tags" and relation_index == completed_relation
                else 1
            )
            page_number = start_page
            async for asset_ids in self._immich.iter_tag_asset_ids(
                tag.id,
                page_size=self._settings.sync_batch_size,
                start_page=start_page,
            ):
                counters["tag_memberships"] += await self._assets.upsert_tag_memberships(
                    tag.id, asset_ids, run.generation
                )
                association_completed += len(asset_ids)
                await self._checkpoint(
                    run,
                    owner,
                    counters,
                    "relationships",
                    f"tags:{relation_index}:{page_number}",
                    self._progress(
                        "relationships",
                        association_completed,
                        membership_total,
                        (
                            f"Album associations {len(albums)}/{len(albums)} "
                            f"· tag associations {relation_index}/{len(tags)}"
                        ),
                    ),
                )
                page_number += 1
            if page_number == start_page == 1:
                await self._checkpoint(
                    run,
                    owner,
                    counters,
                    "relationships",
                    f"tags:{relation_index}:0",
                    self._progress(
                        "relationships",
                        association_completed,
                        membership_total,
                        f"Tag {relation_index}/{len(tags)} · {association_completed} associations",
                    ),
                )
        await self._checkpoint(
            run,
            owner,
            counters,
            "relationships",
            None,
            self._progress(
                "relationships",
                membership_total if membership_total is not None else association_completed,
                membership_total,
                (
                    f"Associations complete · {counters['album_memberships']} album links "
                    f"· {counters['tag_memberships']} tag links"
                ),
            ),
        )

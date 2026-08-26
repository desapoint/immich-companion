"""Persistent, non-overlapping staged synchronization coordinator."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.asset_schema import AssetSyncResult
from companion.config import Settings
from companion.immich import (
    ImmichAlbum,
    ImmichApiClient,
    ImmichAsset,
    ImmichStack,
    ImmichTag,
)
from companion.sync_repository import SyncRepository, new_sync_owner
from companion.sync_schema import SyncCoordinatorStatus, SyncMode, SyncRunStatus


def batches[T](items: list[T], size: int) -> list[list[T]]:
    """Split an already compact collection into bounded persistence batches."""

    return [items[index : index + size] for index in range(0, len(items), size)]


class AssetSyncService:
    """Queue and execute catalog-first staged sync runs under one durable lease."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        syncs: SyncRepository,
        settings: Settings,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._syncs = syncs
        self._settings = settings
        self._worker: asyncio.Task[None] | None = None

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

    async def stop(self) -> None:
        """Stop local work safely; the durable lease can later be recovered."""

        if self._worker is None or self._worker.done():
            return
        self._worker.cancel()
        with suppress(asyncio.CancelledError):
            await self._worker

    async def start(
        self,
        mode: SyncMode = "incremental",
        *,
        force_follow_up: bool = False,
    ) -> SyncRunStatus:
        """Persist sync intent, coalesce safely, and wake a background worker."""

        run = await self._syncs.enqueue(
            mode,
            overlap=self._overlap,
            force_follow_up=force_follow_up,
        )
        self.wake()
        return run

    async def status(self) -> SyncCoordinatorStatus:
        """Return shared persisted status and recover queued work when needed."""

        status = await self._syncs.status()
        if status.active is not None or status.pending is not None:
            self.wake()
        return status

    async def run_status(self, run_id: UUID) -> SyncRunStatus | None:
        """Return one durable run for audit and deterministic validation."""

        return await self._syncs.get_run(run_id)

    async def wait(self, run_id: UUID) -> SyncRunStatus:
        """Wait for one durable run without coupling progress to an HTTP request."""

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
    ) -> None:
        await self._syncs.checkpoint(
            run.id,
            owner,
            phase=phase,
            cursor=cursor,
            counters=counters,
            lease_duration=self._lease_duration,
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

        albums, tags = await asyncio.gather(
            self._immich.list_album_catalog(),
            self._immich.list_tag_catalog(),
        )
        if start_phase <= 0:
            await self._sync_catalogs(run, owner, albums, tags, counters)
        if start_phase <= 1:
            await self._sync_assets(run, owner, counters)
        if start_phase <= 2:
            await self._sync_stacks(run, owner, counters)
        if start_phase <= 3:
            await self._sync_relationships(run, owner, albums, tags, counters)

        await self._checkpoint(run, owner, counters, "finalizing", None)
        validated_counts = await self._assets.validate_generation(
            run.generation,
            counters,
            full=run.mode == "full",
            allow_counter_repair=run.attempts > 1,
        )
        counters.update(validated_counts)
        await self._checkpoint(run, owner, counters, "finalizing", "generation-valid")
        removed = await self._assets.finalize_generation(
            run.generation,
            remove_assets=run.mode == "full",
            batch_size=self._settings.sync_batch_size,
        )
        counters.update(removed)
        await self._assets.refresh_relation_counts()
        await self._checkpoint(run, owner, counters, "finalizing", "validated")
        return counters

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
            created, observed = await self._assets.upsert_album_catalog(
                album_batch, run.generation
            )
            counters["albums_seen"] += created + observed
            await self._checkpoint(
                run, owner, counters, "catalogs", f"albums:{index}"
            )
        for index, tag_batch in enumerate(tag_batches, start=1):
            if index <= completed_tags:
                continue
            created, observed = await self._assets.upsert_tag_catalog(
                tag_batch, run.generation
            )
            counters["tags_seen"] += created + observed
            await self._checkpoint(run, owner, counters, "catalogs", f"tags:{index}")
        await self._checkpoint(run, owner, counters, "assets", None)

    async def _sync_assets(
        self,
        run: SyncRunStatus,
        owner: UUID,
        counters: dict[str, int],
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
        async for asset in iterator:
            batch.append(asset)
            if len(batch) < self._settings.sync_batch_size:
                continue
            batch_number += 1
            await self._commit_asset_batch(run, owner, counters, batch, batch_number)
            batch = []
        if batch:
            batch_number += 1
            await self._commit_asset_batch(run, owner, counters, batch, batch_number)
        await self._checkpoint(run, owner, counters, "stacks", None)

    async def _commit_asset_batch(
        self,
        run: SyncRunStatus,
        owner: UUID,
        counters: dict[str, int],
        batch: list[ImmichAsset],
        batch_number: int,
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
            run, owner, counters, "assets", f"assets:{batch_number}"
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
            await self._checkpoint(run, owner, counters, "stacks", f"stacks:{index}")
        await self._checkpoint(run, owner, counters, "relationships", None)

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
                counters["album_memberships"] += (
                    await self._assets.upsert_album_memberships(
                        album.id, asset_ids, run.generation
                    )
                )
                await self._checkpoint(
                    run,
                    owner,
                    counters,
                    "relationships",
                    f"albums:{relation_index}:{page_number}",
                )
                page_number += 1
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
                counters["tag_memberships"] += (
                    await self._assets.upsert_tag_memberships(
                        tag.id, asset_ids, run.generation
                    )
                )
                await self._checkpoint(
                    run,
                    owner,
                    counters,
                    "relationships",
                    f"tags:{relation_index}:{page_number}",
                )
                page_number += 1

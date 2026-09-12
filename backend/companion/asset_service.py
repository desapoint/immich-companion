"""V2 compatibility surface for synchronization.

The V2 branch preserves the previous staged implementation in
``companion.v2.legacy_asset_service`` and overrides only extracted V2 sync steps here.
This keeps the established task/status API stable while making the new step classes the
implementation used by the live V2 synchronization flow.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from companion.immich import ImmichAlbum, ImmichApiError, ImmichTag
from companion.sync_schema import SyncProgress, SyncRunStatus
from companion.v2.legacy_asset_service import *  # noqa: F403
from companion.v2.legacy_asset_service import AssetSyncService as _LegacyAssetSyncService
from companion.v2.sync_steps import (
    CatalogSyncInput,
    CatalogSyncStep,
    SyncStepConfig,
    SyncStepContext,
    SyncStepProgress,
)

ALBUM_MEMBERSHIP_PAGE_SIZE = 1000


class _LegacyPacedCatalogSyncStep(CatalogSyncStep):
    """Use the V2 step contract while preserving the staged sync's pacing semantics."""

    def __init__(
        self,
        assets,
        pace_callback: Callable[[float], Awaitable[None]],
    ) -> None:
        super().__init__(assets)
        self._pace_callback = pace_callback

    async def pace(self, _context: SyncStepContext, started: float) -> None:
        await self._pace_callback(started)


class AssetSyncService(_LegacyAssetSyncService):
    """Live V2 staged sync with extracted steps replacing legacy stages incrementally."""

    async def album_reconciliation_will_cover(self, album_ids: list[UUID]) -> bool:
        """Return whether the active global sync will still traverse every target album."""

        unique_album_ids = list(dict.fromkeys(album_ids))
        if not unique_album_ids:
            return False

        status = await self.status()
        active = status.active
        if active is None:
            return False

        if active.phase in {"catalogs", "assets", "stacks"}:
            return True
        if active.phase != "relationships":
            return False
        if not active.cursor:
            return False

        cursor_parts = active.cursor.split(":", 2)
        if len(cursor_parts) < 2 or cursor_parts[0] != "albums":
            return False
        try:
            current_album_index = int(cursor_parts[1])
        except ValueError:
            return False

        # The relationship stage traverses albums in the same catalog order. Only
        # albums strictly after the checkpoint are guaranteed to receive a future
        # authoritative traversal. The current album may already have passed the
        # changed asset's page, so it is deliberately not considered covered.
        catalog = await self._immich.list_album_catalog()
        positions = {album.id: index for index, album in enumerate(catalog, start=1)}
        return all(
            (position := positions.get(album_id)) is not None
            and position > current_album_index
            for album_id in unique_album_ids
        )

    async def tag_reconciliation_will_cover(self, tag_ids: list[UUID]) -> bool:
        """Return whether a full global sync definitely has tag work still ahead.

        Incremental runs may choose asset-oriented tag reconciliation over only
        the generation's bounded asset window, so they cannot guarantee coverage
        for a user mutation made after that window was established. Once any
        relationship work begins, tag progress is also intentionally treated as
        ambiguous until the sync exposes a durable tag-specific boundary.
        """

        if not list(dict.fromkeys(tag_ids)):
            return False
        status = await self.status()
        active = status.active
        return (
            active is not None
            and getattr(active, "mode", None) == "full"
            and active.phase in {"catalogs", "assets", "stacks"}
        )

    async def _repair_tags_from_asset_details(self, asset_ids: list[UUID]) -> bool:
        """Repair a bounded changed set directly from authoritative asset details."""

        unique_asset_ids = list(dict.fromkeys(asset_ids))
        if not unique_asset_ids:
            return True

        runtime = await self._runtime_sync_settings.get()
        if len(unique_asset_ids) > runtime.full_batch_size:
            return False

        concurrency = max(1, runtime.tag_association_concurrency)
        details = []

        async def fetch(identifier: UUID):
            try:
                return await self._immich.get_asset(identifier)
            except ImmichApiError as error:
                if error.status_code == 404:
                    return None
                raise

        for start in range(0, len(unique_asset_ids), concurrency):
            wave = unique_asset_ids[start : start + concurrency]
            details.extend(await asyncio.gather(*(fetch(identifier) for identifier in wave)))

        # An omitted tags relationship is not equivalent to an empty tag set.
        # Fall back to the existing relation-oriented authoritative traversal.
        if any(detail is None or not detail.includes_tags for detail in details):
            return False

        for detail in details:
            assert detail is not None
            tag_ids = [UUID(str(tag["id"])) for tag in detail.tags if tag.get("id")]
            await self._assets.replace_asset_tag_memberships(detail.id, tag_ids)
        return True

    async def reconcile_targets(
        self,
        asset_ids: list[UUID],
        relations: list[tuple[str, UUID]] | None = None,
        include_stacks: bool = False,
    ) -> None:
        """Choose bounded targeted relation repair before using the legacy flow."""

        if (
            relations
            and asset_ids
            and all(kind == "tag" for kind, _ in relations)
            and await self._repair_tags_from_asset_details(asset_ids)
        ):
            return

        if relations and asset_ids and all(kind == "album" for kind, _ in relations):
            unique_asset_ids = list(dict.fromkeys(asset_ids))
            unique_relation_ids = list(
                dict.fromkeys(relation_id for _, relation_id in relations)
            )
            catalog = await self._immich.list_album_catalog()
            albums_by_id = {album.id: album for album in catalog}
            affected_albums = [
                albums_by_id[relation_id]
                for relation_id in unique_relation_ids
                if relation_id in albums_by_id
            ]

            # Preserve the legacy authoritative error path when an affected album
            # is unexpectedly absent from the live catalog.
            if len(affected_albums) == len(unique_relation_ids):
                album_calls = sum(
                    max(
                        1,
                        (album.asset_count + ALBUM_MEMBERSHIP_PAGE_SIZE - 1)
                        // ALBUM_MEMBERSHIP_PAGE_SIZE,
                    )
                    for album in affected_albums
                )
                asset_calls = len(unique_asset_ids)

                # Ties intentionally favor the asset-oriented path because each
                # response is smaller and avoids rebuilding a full album snapshot.
                if album_calls >= asset_calls:
                    upsert_album_catalog = getattr(self._assets, "upsert_album_catalog", None)
                    if upsert_album_catalog is not None:
                        await upsert_album_catalog(affected_albums, 0)
                    for asset_id in unique_asset_ids:
                        albums = await self._immich.list_albums_for_asset(asset_id)
                        await self._assets.replace_asset_album_memberships(
                            asset_id,
                            [album.id for album in albums],
                        )
                    return

        await super().reconcile_targets(
            asset_ids,
            relations=relations,
            include_stacks=include_stacks,
        )

    async def _sync_catalogs(
        self,
        run: SyncRunStatus,
        owner: UUID,
        albums: list[ImmichAlbum],
        tags: list[ImmichTag],
        counters: dict[str, int],
        asset_total: int | None,
    ) -> None:
        async def checkpoint(
            cursor: str | None,
            step_counters: dict[str, int],
            progress: SyncStepProgress,
        ) -> None:
            await self._checkpoint(
                run,
                owner,
                step_counters,
                "catalogs",
                cursor,
                SyncProgress(
                    phase=progress.phase,
                    completed=max(0, progress.completed),
                    total=progress.total,
                    percent=progress.percent,
                    detail=progress.detail,
                ),
            )

        step = _LegacyPacedCatalogSyncStep(
            self._assets,
            lambda started: self._pace_full_batch(run, started),
        )
        context = SyncStepContext(
            mode=run.mode,
            generation=run.generation,
            config=SyncStepConfig(
                batch_size=self._full_batch_size(run, self._settings),
                concurrency=1,
            ),
            counters=counters,
            cursor=run.cursor if run.phase == "catalogs" else None,
            window_start=run.window_start,
            window_end=run.window_end,
            manual=False,
            respect_conditionals=True,
            checkpoint_callback=checkpoint,
        )
        await step.run(context, CatalogSyncInput(albums=albums, tags=tags))

        # The orchestrator, not the step, owns phase transitions. This keeps each
        # extracted step independently runnable and prevents it from knowing what comes next.
        await self._checkpoint(
            run,
            owner,
            counters,
            "assets",
            None,
            self._progress(
                "assets",
                0,
                asset_total,
                f"Preparing {asset_total} media items"
                if asset_total is not None
                else "Preparing media traversal",
            ),
        )

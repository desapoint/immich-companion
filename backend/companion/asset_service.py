"""V2 compatibility surface for synchronization.

The V2 branch preserves the previous staged implementation in
``companion.v2.legacy_asset_service`` and overrides only extracted V2 sync steps here.
This keeps the established task/status API stable while making the new step classes the
implementation used by the live V2 synchronization flow.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from companion.immich import ImmichAlbum, ImmichTag
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

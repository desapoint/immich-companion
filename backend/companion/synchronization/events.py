"""First-class optional Immich sync-event application."""

from __future__ import annotations

from uuid import UUID

from companion.asset_repository import AssetRepository
from companion.immich import ImmichApiClient, ImmichAsset
from companion.sync_schema import SyncEvent
from companion.synchronization.scopes import EventScope
from companion.synchronization.steps import (
    SyncStep,
    SyncStepContext,
    SyncStepProgress,
)


class EventSyncStep(SyncStep[EventScope]):
    """Apply optional Immich sync-stream changes before normal catalog traversal."""

    name = "events"
    phase = "catalogs"

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
    ) -> None:
        self._immich = immich
        self._assets = assets

    async def execute(
        self,
        context: SyncStepContext,
        scope: EventScope,
    ) -> tuple[int, None]:
        context.counters.setdefault("events_seen", 0)

        async for event in self._immich.iter_sync_events(scope.cursor):
            await self.apply_event(event)
            acknowledge = getattr(self._immich, "acknowledge_sync_event", None)
            if acknowledge is not None:
                await acknowledge(event.id)

            context.counters["events_seen"] += 1
            context.cursor = f"event:{event.id}"
            await context.checkpoint_callback(
                context.cursor,
                context.counters,
                SyncStepProgress(
                    phase=self.phase,
                    completed=context.counters["events_seen"],
                    total=None,
                    detail=(
                        f"Applied {context.counters['events_seen']} sync "
                        f"{'event' if context.counters['events_seen'] == 1 else 'events'}"
                    ),
                ),
            )

        return context.counters["events_seen"], None

    async def apply_event(self, event: SyncEvent) -> None:
        """Apply one event using the same local mutations as the legacy service path."""

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
                    event.payload.get(
                        "present",
                        event.payload.get("action", "add") != "remove",
                    )
                )
                await self._assets.apply_membership_event(
                    "album" if event.kind == "album_membership" else "tag",
                    UUID(str(relation_id)),
                    UUID(str(asset_id)),
                    present,
                )


__all__ = ["EventSyncStep"]

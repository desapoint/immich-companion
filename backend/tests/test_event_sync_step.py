"""First-class optional event-stream synchronization behavior."""

from uuid import UUID

import pytest

from companion.sync_schema import SyncEvent
from companion.synchronization.events import EventSyncStep
from companion.synchronization.scopes import EventScope
from companion.synchronization.steps import (
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
)

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ALBUM_ONE = UUID("22222222-2222-4222-8222-222222222222")
TAG_ONE = UUID("33333333-3333-4333-8333-333333333333")


def asset_payload() -> dict[str, object]:
    return {
        "id": str(ASSET_ONE),
        "type": "IMAGE",
        "originalFileName": "changed.jpg",
        "originalMimeType": "image/jpeg",
        "width": 100,
        "height": 80,
        "fileCreatedAt": "2026-09-25T10:00:00Z",
        "fileModifiedAt": "2026-09-25T10:00:00Z",
        "updatedAt": "2026-09-25T10:00:00Z",
    }


class FakeImmich:
    def __init__(self, events: list[SyncEvent]) -> None:
        self.events = events
        self.cursors: list[str | None] = []
        self.acknowledged: list[str] = []

    async def iter_sync_events(self, cursor=None):
        self.cursors.append(cursor)
        for event in self.events:
            yield event

    async def acknowledge_sync_event(self, event_id: str) -> None:
        self.acknowledged.append(event_id)


class NoAckImmich:
    def __init__(self, events: list[SyncEvent]) -> None:
        self.events = events

    async def iter_sync_events(self, _cursor=None):
        for event in self.events:
            yield event


class FakeAssets:
    def __init__(self) -> None:
        self.removed: list[UUID] = []
        self.refreshed: list[UUID] = []
        self.memberships: list[tuple[str, UUID, UUID, bool]] = []

    async def remove_asset(self, asset_id: UUID) -> None:
        self.removed.append(asset_id)

    async def refresh_asset(self, asset) -> None:
        self.refreshed.append(asset.id)

    async def apply_membership_event(
        self,
        kind: str,
        relation_id: UUID,
        asset_id: UUID,
        present: bool,
    ) -> None:
        self.memberships.append((kind, relation_id, asset_id, present))


@pytest.mark.asyncio
async def test_event_step_applies_supported_events_and_preserves_cursor_contract() -> None:
    events = [
        SyncEvent(id="1", kind="asset", entity_id=ASSET_ONE, payload=asset_payload()),
        SyncEvent(id="2", kind="asset_deleted", entity_id=ASSET_ONE),
        SyncEvent(
            id="3",
            kind="album_membership",
            entity_id=ASSET_ONE,
            payload={"albumId": str(ALBUM_ONE), "action": "remove"},
        ),
        SyncEvent(
            id="4",
            kind="tag_membership",
            payload={
                "relationId": str(TAG_ONE),
                "assetId": str(ASSET_ONE),
                "present": True,
            },
        ),
        SyncEvent(id="5", kind="stack", entity_id=ASSET_ONE),
        SyncEvent(id="6", kind="reset"),
    ]
    immich = FakeImmich(events)
    assets = FakeAssets()
    checkpoints = []

    async def checkpoint(cursor, counters, progress):
        checkpoints.append(
            (cursor, counters["events_seen"], progress.phase, progress.completed)
        )

    result = await EventSyncStep(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="incremental",
            generation=51,
            config=SyncStepConfig(),
            checkpoint_callback=checkpoint,
        ),
        EventScope(cursor="cursor-1"),
    )

    assert result.completed == 6
    assert result.total is None
    assert result.counters["events_seen"] == 6
    assert result.evidence == []
    assert immich.cursors == ["cursor-1"]
    assert immich.acknowledged == ["1", "2", "3", "4", "5", "6"]
    assert assets.refreshed == [ASSET_ONE]
    assert assets.removed == [ASSET_ONE]
    assert assets.memberships == [
        ("album", ALBUM_ONE, ASSET_ONE, False),
        ("tag", TAG_ONE, ASSET_ONE, True),
    ]
    assert [item[0] for item in checkpoints] == [
        "event:1",
        "event:2",
        "event:3",
        "event:4",
        "event:5",
        "event:6",
    ]
    assert all(item[2] == "catalogs" for item in checkpoints)


@pytest.mark.asyncio
async def test_event_step_does_not_require_acknowledgement_support() -> None:
    event = SyncEvent(id="1", kind="reset")
    result = await EventSyncStep(
        NoAckImmich([event]),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="incremental",
            generation=52,
            config=SyncStepConfig(),
        ),
        EventScope(),
    )

    assert result.completed == 1
    assert result.counters["events_seen"] == 1


@pytest.mark.asyncio
async def test_event_step_respects_conditionals_and_manual_bypass() -> None:
    event = SyncEvent(id="1", kind="reset")
    immich = FakeImmich([event])
    assets = FakeAssets()
    config = SyncStepConfig(
        conditionals=SyncStepConditionals(enabled=False),
    )

    skipped = await EventSyncStep(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="incremental",
            generation=53,
            config=config,
        ),
        EventScope(),
    )
    assert skipped.skipped is True
    assert immich.cursors == []

    manual = await EventSyncStep(
        immich,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
    ).run(
        SyncStepContext(
            mode="incremental",
            generation=54,
            config=config,
            manual=True,
            respect_conditionals=False,
        ),
        EventScope(),
    )
    assert manual.skipped is False
    assert manual.completed == 1
    assert immich.cursors == [None]

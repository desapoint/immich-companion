from datetime import UTC, datetime, timedelta
from uuid import UUID

from companion.models import TaskEventRecord, TaskRecord
from companion.sync_history import build_sync_history_item
from companion.sync_telemetry import SyncTelemetryCollector, telemetry_key

TASK_ID = UUID("11111111-1111-4111-8111-111111111111")


def runtime_settings() -> dict[str, object]:
    return {
        "full_batch_size": 250,
        "full_min_batch_delay_seconds": 0.2,
        "tag_association_concurrency": 4,
        "metadata_request_concurrency": 4,
        "page_prefetch": 1,
        "api_page_size": 1000,
        "incremental_overlap_seconds": 300,
        "incremental_strategy": "automatic",
        "adaptive_throttling": True,
    }


def test_sync_telemetry_accumulates_persisted_and_phase_metrics(monkeypatch) -> None:
    times = iter((10.0, 10.4, 10.4, 10.9, 10.9))
    monkeypatch.setattr("companion.sync_telemetry.perf_counter", lambda: next(times))
    collector = SyncTelemetryCollector(
        {telemetry_key("global", "api_requests"): 3}, phase="assets"
    )
    collector.api_request()
    collector.api_retry(rate_limited=True)
    collector.wait(0.25)
    collector.checkpoint()
    counters: dict[str, int] = {}
    collector.transition("stacks")
    collector.api_request()
    collector.finish()
    collector.write_into(counters, include_live_phase=False)

    assert counters[telemetry_key("global", "api_requests")] == 5
    assert counters[telemetry_key("assets", "api_requests")] == 1
    assert counters[telemetry_key("assets", "duration_ms")] == 400
    assert counters[telemetry_key("stacks", "duration_ms")] == 500
    assert counters[telemetry_key("global", "rate_limits")] == 1
    assert counters[telemetry_key("global", "wait_ms")] == 250


def test_history_projects_global_phase_and_settings_telemetry() -> None:
    created = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    started = created + timedelta(seconds=2)
    completed = started + timedelta(seconds=10)
    counters = {
        "assets_seen": 50,
        "albums_seen": 2,
        "tags_seen": 3,
        telemetry_key("global", "api_requests"): 8,
        telemetry_key("global", "api_retries"): 1,
        telemetry_key("global", "rate_limits"): 1,
        telemetry_key("global", "wait_ms"): 500,
        telemetry_key("global", "checkpoints"): 4,
        telemetry_key("assets", "duration_ms"): 6000,
        telemetry_key("assets", "api_requests"): 6,
        telemetry_key("assets", "api_retries"): 1,
        telemetry_key("assets", "rate_limits"): 1,
        telemetry_key("assets", "wait_ms"): 500,
        telemetry_key("assets", "checkpoints"): 2,
    }
    record = TaskRecord(
        id=TASK_ID,
        task_type="asset_sync",
        payload={
            "mode": "full",
            "generation": 12,
            "runtime_settings": runtime_settings(),
        },
        priority=100,
        status="completed",
        lane_key="asset_sync",
        checkpoint={"phase": "finalizing"},
        counters=counters,
        progress={"phase": "complete"},
        result={"status": "completed", "summary": {}, "counters": counters},
        attempt=1,
        created_at=created,
        started_at=started,
        heartbeat_at=completed,
        completed_at=completed,
    )

    item = build_sync_history_item(record, [], now=completed)

    assert item.mode == "full"
    assert item.queue_seconds == 2
    assert item.duration_seconds == 10
    assert item.throughput_per_second == 5
    assert item.api_requests == 8
    assert item.settings is not None
    assert item.settings.api_page_size == 1000
    assets = next(phase for phase in item.phases if phase.phase == "assets")
    assert assets.duration_seconds == 6
    assert assets.processed_items == 50
    assert assets.api_requests == 6
    assert telemetry_key("global", "api_requests") not in item.counters


def test_legacy_history_derives_phase_duration_from_checkpoint_events() -> None:
    created = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    started = created + timedelta(seconds=1)
    completed = started + timedelta(seconds=8)
    record = TaskRecord(
        id=TASK_ID,
        task_type="asset_sync",
        payload={"mode": "incremental", "generation": 4},
        priority=10,
        status="completed",
        lane_key="asset_sync",
        checkpoint={"phase": "finalizing"},
        counters={"assets_seen": 4},
        progress={"phase": "complete"},
        attempt=1,
        created_at=created,
        started_at=started,
        heartbeat_at=completed,
        completed_at=completed,
    )
    events = [
        TaskEventRecord(
            id=UUID(int=2),
            task_id=TASK_ID,
            attempt=1,
            kind="checkpoint",
            details={"checkpoint": {"phase": "assets"}},
            created_at=started,
        ),
        TaskEventRecord(
            id=UUID(int=3),
            task_id=TASK_ID,
            attempt=1,
            kind="checkpoint",
            details={"checkpoint": {"phase": "stacks"}},
            created_at=started + timedelta(seconds=5),
        ),
    ]

    item = build_sync_history_item(record, events, now=completed)

    assert item.settings is None
    assert item.telemetry_available is False
    assert next(phase for phase in item.phases if phase.phase == "assets").duration_seconds == 5
    assert next(phase for phase in item.phases if phase.phase == "stacks").duration_seconds == 3


def test_history_tolerates_invalid_legacy_payload_and_times_active_run() -> None:
    created = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    started = created + timedelta(seconds=2)
    now = started + timedelta(seconds=7)
    record = TaskRecord(
        id=TASK_ID,
        task_type="asset_sync",
        payload={
            "mode": "full",
            "generation": "invalid",
            "runtime_settings": {"api_page_size": -1},
        },
        priority=100,
        status="running",
        lane_key="asset_sync",
        checkpoint={"phase": "assets"},
        counters={"assets_seen": 14},
        progress={"phase": "assets"},
        attempt=1,
        created_at=created,
        started_at=started,
        heartbeat_at=started + timedelta(seconds=1),
    )

    item = build_sync_history_item(record, [], now=now)

    assert item.settings is None
    assert item.generation == 0
    assert item.duration_seconds == 7
    assert item.throughput_per_second == 2

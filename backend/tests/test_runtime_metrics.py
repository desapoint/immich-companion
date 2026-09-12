"""Dependency-free process telemetry regressions."""

from companion.runtime_metrics import (
    ProcessMemorySnapshot,
    process_memory_snapshot,
    reclaim_process_memory,
)


def test_process_memory_snapshot_parses_linux_status(tmp_path) -> None:
    status = tmp_path / "status"
    status.write_text("Name:\tpython\nVmRSS:\t123 kB\nVmHWM:\t456 kB\n", encoding="utf-8")

    snapshot = process_memory_snapshot(status)

    assert snapshot.rss_bytes == 123 * 1024
    assert snapshot.peak_rss_bytes == 456 * 1024


def test_process_memory_snapshot_fails_closed_when_status_is_unavailable(tmp_path) -> None:
    snapshot = process_memory_snapshot(tmp_path / "missing")

    assert snapshot.rss_bytes == 0
    assert snapshot.peak_rss_bytes == 0


def test_reclaim_process_memory_skips_cleanup_below_threshold() -> None:
    collected = False

    def collect() -> int:
        nonlocal collected
        collected = True
        return 0

    result = reclaim_process_memory(
        minimum_rss_bytes=256,
        snapshot=lambda: ProcessMemorySnapshot(rss_bytes=128, peak_rss_bytes=512),
        collect=collect,
        trim=lambda: True,
    )

    assert result is None
    assert collected is False


def test_reclaim_process_memory_reports_actual_rss_reduction() -> None:
    snapshots = iter(
        (
            ProcessMemorySnapshot(rss_bytes=800, peak_rss_bytes=900),
            ProcessMemorySnapshot(rss_bytes=300, peak_rss_bytes=900),
        )
    )

    result = reclaim_process_memory(
        minimum_rss_bytes=256,
        snapshot=lambda: next(snapshots),
        collect=lambda: 17,
        trim=lambda: True,
    )

    assert result is not None
    assert result.before_rss_bytes == 800
    assert result.after_rss_bytes == 300
    assert result.released_bytes == 500
    assert result.collected_objects == 17
    assert result.allocator_trim_attempted is True

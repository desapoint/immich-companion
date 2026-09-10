"""Dependency-free process telemetry regressions."""

from companion.runtime_metrics import process_memory_snapshot


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

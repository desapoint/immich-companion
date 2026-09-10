"""Small dependency-free process metrics shared by profiling and task telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProcessMemorySnapshot:
    rss_bytes: int
    peak_rss_bytes: int


def process_memory_snapshot(
    status_path: Path = Path("/proc/self/status"),
) -> ProcessMemorySnapshot:
    """Read Linux process RSS counters, returning zeroes when unavailable."""

    values: dict[str, int] = {}
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            name, separator, raw = line.partition(":")
            if separator and name in {"VmRSS", "VmHWM"}:
                values[name] = int(raw.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    rss = values.get("VmRSS", 0)
    return ProcessMemorySnapshot(rss_bytes=rss, peak_rss_bytes=values.get("VmHWM", rss))

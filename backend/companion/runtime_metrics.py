"""Small dependency-free process metrics shared by profiling and task telemetry."""

from __future__ import annotations

import ctypes
import gc
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProcessMemorySnapshot:
    rss_bytes: int
    peak_rss_bytes: int


@dataclass(frozen=True, slots=True)
class ProcessMemoryReclaim:
    """Outcome of a best-effort post-task allocator cleanup."""

    before_rss_bytes: int
    after_rss_bytes: int
    peak_rss_bytes: int
    collected_objects: int
    allocator_trim_attempted: bool

    @property
    def released_bytes(self) -> int:
        return max(0, self.before_rss_bytes - self.after_rss_bytes)


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


def _trim_glibc_allocator() -> bool:
    """Return free glibc arenas to the OS when the runtime provides malloc_trim."""

    if not sys.platform.startswith("linux"):
        return False
    try:
        allocator = ctypes.CDLL(None)
        trim = allocator.malloc_trim
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        trim(0)
    except (AttributeError, OSError):
        return False
    return True


def reclaim_process_memory(
    *,
    minimum_rss_bytes: int = 256 * 1024 * 1024,
    snapshot: Callable[[], ProcessMemorySnapshot] = process_memory_snapshot,
    collect: Callable[[], int] = gc.collect,
    trim: Callable[[], bool] = _trim_glibc_allocator,
) -> ProcessMemoryReclaim | None:
    """Reclaim post-task memory only after RSS crosses a meaningful threshold.

    Python and native libraries can free every live object while glibc retains the
    released arenas.  A full collection followed by ``malloc_trim`` makes the idle
    container footprint reflect live allocations again.  Unsupported allocators fail
    closed; normal task completion must never depend on this optimization.
    """

    before = snapshot()
    if before.rss_bytes < minimum_rss_bytes:
        return None
    collected = collect()
    trim_attempted = trim()
    after = snapshot()
    return ProcessMemoryReclaim(
        before_rss_bytes=before.rss_bytes,
        after_rss_bytes=after.rss_bytes,
        peak_rss_bytes=max(before.peak_rss_bytes, after.peak_rss_bytes),
        collected_objects=collected,
        allocator_trim_attempted=trim_attempted,
    )

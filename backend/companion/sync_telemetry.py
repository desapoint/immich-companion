"""Execution-scoped synchronization performance telemetry."""

from __future__ import annotations

from contextvars import ContextVar, Token
from time import perf_counter

SYNC_PHASES = ("catalogs", "assets", "stacks", "relationships", "finalizing")
TELEMETRY_PREFIX = "telemetry__"


def telemetry_key(scope: str, metric: str) -> str:
    return f"{TELEMETRY_PREFIX}{scope}__{metric}"


class SyncTelemetryCollector:
    """Accumulate restart-safe integer metrics in the task counter namespace."""

    def __init__(self, persisted: dict[str, int], phase: str | None = None) -> None:
        self._baseline = {
            key: value for key, value in persisted.items() if key.startswith(TELEMETRY_PREFIX)
        }
        self._values: dict[str, int] = {}
        self._phase = phase if phase in SYNC_PHASES else None
        self._phase_started = perf_counter()

    @property
    def phase(self) -> str | None:
        return self._phase

    def _add(self, scope: str, metric: str, value: int = 1) -> None:
        key = telemetry_key(scope, metric)
        self._values[key] = self._values.get(key, 0) + max(0, value)

    def _record_phase_elapsed(self) -> None:
        if self._phase is None:
            self._phase_started = perf_counter()
            return
        elapsed_ms = round(max(0.0, perf_counter() - self._phase_started) * 1000)
        self._add(self._phase, "duration_ms", elapsed_ms)
        self._phase_started = perf_counter()

    def transition(self, phase: str) -> None:
        if phase not in SYNC_PHASES or phase == self._phase:
            return
        self._record_phase_elapsed()
        self._phase = phase

    def checkpoint(self) -> None:
        self._add("global", "checkpoints")
        if self._phase is not None:
            self._add(self._phase, "checkpoints")

    def api_request(self) -> None:
        self._add("global", "api_requests")
        if self._phase is not None:
            self._add(self._phase, "api_requests")

    def api_retry(self, *, rate_limited: bool) -> None:
        self._add("global", "api_retries")
        if self._phase is not None:
            self._add(self._phase, "api_retries")
        if rate_limited:
            self._add("global", "rate_limits")
            if self._phase is not None:
                self._add(self._phase, "rate_limits")

    def wait(self, seconds: float) -> None:
        wait_ms = round(max(0.0, seconds) * 1000)
        self._add("global", "wait_ms", wait_ms)
        if self._phase is not None:
            self._add(self._phase, "wait_ms", wait_ms)

    def finish(self) -> None:
        self._record_phase_elapsed()
        self._phase = None

    def write_into(self, counters: dict[str, int], *, include_live_phase: bool = True) -> None:
        values = dict(self._values)
        if include_live_phase and self._phase is not None:
            key = telemetry_key(self._phase, "duration_ms")
            values[key] = values.get(key, 0) + round(
                max(0.0, perf_counter() - self._phase_started) * 1000
            )
        for key in set(self._baseline) | set(values):
            counters[key] = self._baseline.get(key, 0) + values.get(key, 0)


_CURRENT_SYNC_TELEMETRY: ContextVar[SyncTelemetryCollector | None] = ContextVar(
    "current_sync_telemetry", default=None
)


def install_sync_telemetry(collector: SyncTelemetryCollector) -> Token:
    return _CURRENT_SYNC_TELEMETRY.set(collector)


def reset_sync_telemetry(token: Token) -> None:
    _CURRENT_SYNC_TELEMETRY.reset(token)


def current_sync_telemetry() -> SyncTelemetryCollector | None:
    return _CURRENT_SYNC_TELEMETRY.get()

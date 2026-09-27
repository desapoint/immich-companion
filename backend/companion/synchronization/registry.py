"""Registry for the canonical first-class synchronization steps."""

from __future__ import annotations

from collections.abc import Iterable

from companion.synchronization.scopes import SYNC_STEP_NAMES, SyncStepName
from companion.synchronization.steps import SyncStep


class SyncStepRegistry:
    """Own one step instance per synchronization domain."""

    def __init__(self, steps: Iterable[SyncStep[object]] = ()) -> None:
        self._steps: dict[SyncStepName, SyncStep[object]] = {}
        for step in steps:
            self.register(step)

    def register(self, step: SyncStep[object]) -> None:
        if step.name not in SYNC_STEP_NAMES:
            raise ValueError(f"Unknown synchronization step: {step.name}")
        if step.name in self._steps:
            raise ValueError(f"Synchronization step already registered: {step.name}")
        self._steps[step.name] = step

    def get(self, name: SyncStepName) -> SyncStep[object]:
        try:
            return self._steps[name]
        except KeyError as error:
            raise KeyError(f"Synchronization step is not registered: {name}") from error

    def names(self) -> tuple[SyncStepName, ...]:
        return tuple(self._steps)


__all__ = ["SyncStepRegistry"]

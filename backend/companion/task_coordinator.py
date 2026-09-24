"""Stable public imports for the canonical task subsystem."""

from companion.tasks.coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskCancelledError,
    TaskContext,
    TaskCoordinator,
    TaskHandler,
    TaskLeaseLostError,
    TaskPausedError,
    TaskRepository,
)

__all__ = [
    "PermanentTaskError",
    "RetryableTaskError",
    "TaskCancelledError",
    "TaskContext",
    "TaskCoordinator",
    "TaskHandler",
    "TaskLeaseLostError",
    "TaskPausedError",
    "TaskRepository",
]

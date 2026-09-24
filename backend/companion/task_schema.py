"""Compatibility imports for the canonical task contracts."""

from companion.tasks.contracts import (
    TaskErrorEvent,
    TaskEvent,
    TaskResult,
    TaskRetry,
    TaskScheduleUpdate,
    TaskScheduleView,
    TaskStatus,
    TaskStatusView,
)

__all__ = [
    "TaskErrorEvent",
    "TaskEvent",
    "TaskResult",
    "TaskRetry",
    "TaskScheduleUpdate",
    "TaskScheduleView",
    "TaskStatus",
    "TaskStatusView",
]

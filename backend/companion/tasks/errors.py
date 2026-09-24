"""Task-control and handler failure taxonomy."""


class RetryableTaskError(RuntimeError):
    """A handler failure that should be retried by the same task."""


class PermanentTaskError(RuntimeError):
    """A handler failure that must not be retried."""


class TaskLeaseLostError(RuntimeError):
    """Raised when a worker attempts to mutate a task it no longer owns."""


class TaskCancelledError(RuntimeError):
    """Raised when a handler observes a cancellation request."""


class TaskPausedError(RuntimeError):
    """Raised when a handler reaches a safe boundary after pause was requested."""


class TaskAlreadyActiveError(RuntimeError):
    """Raised when a scheduled submission coalesces with active work."""


__all__ = [
    "PermanentTaskError",
    "RetryableTaskError",
    "TaskAlreadyActiveError",
    "TaskCancelledError",
    "TaskLeaseLostError",
    "TaskPausedError",
]

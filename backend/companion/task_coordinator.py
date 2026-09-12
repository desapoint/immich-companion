"""V2 compatibility import for durable task coordination.

The V2 branch keeps the previous coordinator byte-for-byte in
``companion.v2.legacy_task_coordinator``. Application code can keep importing this
established module path while receiving the V2-owned coordinator/context implementation.
"""

from companion.v2.task_coordinator import *  # noqa: F403

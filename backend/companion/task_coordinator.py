"""Compatibility import for durable task coordination.

The standardization branch keeps the current coordinator implementation in
``companion.v2.legacy_task_coordinator`` so the established import path can
remain stable while matching the V2 branch's ownership boundary. V2 can later
swap this facade to ``companion.v2.task_coordinator`` without rewriting the
legacy implementation or losing V1 task hardening.
"""

from companion.v2.legacy_task_coordinator import *  # noqa: F403

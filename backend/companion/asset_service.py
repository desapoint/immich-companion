"""Stable public imports for the canonical synchronization package.

Callers keep importing this module while synchronization implementation and task
adapters live under :mod:`companion.synchronization`.
"""

from companion.synchronization.batching import (
    async_batches_with_last,
    async_items_with_last,
    batches,
    prefetch_async,
)
from companion.synchronization.service import (
    ALBUM_MEMBERSHIP_PAGE_SIZE,
    AssetRelationRepairTaskHandler,
    AssetRepairTaskHandler,
    AssetSelectionSyncTaskHandler,
    AssetSyncService,
    AssetSyncTaskHandler,
)

__all__ = [
    "ALBUM_MEMBERSHIP_PAGE_SIZE",
    "AssetRelationRepairTaskHandler",
    "AssetRepairTaskHandler",
    "AssetSelectionSyncTaskHandler",
    "AssetSyncService",
    "AssetSyncTaskHandler",
    "async_batches_with_last",
    "async_items_with_last",
    "batches",
    "prefetch_async",
]

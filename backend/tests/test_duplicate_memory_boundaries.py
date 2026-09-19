"""Architecture guards for bounded V2 duplicate hydration paths."""

from __future__ import annotations

import gc
import inspect
import tracemalloc
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.composite_duplicate_repository import CompositeDuplicateRepository
from companion.composite_duplicate_sync import CompositeDuplicateRebuildTaskHandler
from companion.discovery.base import DiscoveredGroup
from companion.discovery.composite import CompositeGroupDiscoveryProvider
from companion.discovery.immich_duplicates import ImmichDuplicateProvider
from companion.duplicate_service import CrossSourceDuplicateService
from companion.group_decision import DiscoverySource


def test_v2_single_group_and_preset_paths_do_not_call_full_result_hydration() -> None:
    """Keep ordinary V2 mutations off the legacy whole-library result contract."""

    methods = (
        CrossSourceDuplicateService.review_page,
        CrossSourceDuplicateService.review_selected_page,
        CrossSourceDuplicateService.save_review,
        CrossSourceDuplicateService.workspace,
        CrossSourceDuplicateService.save_workspace_selection,
        CrossSourceDuplicateService.apply_rules,
        CrossSourceDuplicateService.reset_workspace_decisions,
        CrossSourceDuplicateService.similarity_reference,
        CrossSourceDuplicateService.apply_workspace_preset,
        CrossSourceDuplicateService.plan,
        CrossSourceDuplicateService.execute_plan,
    )
    for method in methods:
        source = inspect.getsource(method)
        assert "self.result(" not in source
        assert "self._live_groups(" not in source
        assert "await self._snapshot(" not in source


def test_composite_snapshot_publication_consumes_bounded_group_batches() -> None:
    source = inspect.getsource(CompositeDuplicateRepository.replace_snapshot_batches)
    assert "async for groups in batches" in source
    assert "for group in groups" in source
    assert "await session.scalars" in source
    assert "groups = [" not in source


def test_composite_rebuild_prefers_batched_discovery_and_publication() -> None:
    source = inspect.getsource(CompositeDuplicateRebuildTaskHandler.execute)
    assert 'getattr(self._discovery, "discover_batches"' in source
    assert 'getattr(self._repository, "replace_snapshot_batches"' in source


def test_persisted_immich_discovery_pages_before_hydration() -> None:
    source = inspect.getsource(ImmichDuplicateProvider.discover_batches)
    assert '"groups_page"' in source
    assert "yield await self._hydrate_persisted(snapshot)" in source


def test_exact_duplicate_analysis_streams_discovery_batches() -> None:
    from companion.duplicate_service import CrossSourceDuplicateTaskHandler

    handler_source = inspect.getsource(CrossSourceDuplicateTaskHandler.execute)
    assert '"discover_batches"' in handler_source
    assert "groups = await self._discovery.discover()" not in handler_source
    assert "processed_asset_ids" in handler_source


@pytest.mark.asyncio
async def test_composite_streaming_memory_does_not_scale_with_group_payloads() -> None:
    """Exercise high-cardinality streaming and guard against full payload retention."""

    left = SimpleNamespace(id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
    right = SimpleNamespace(id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))
    group_count = 2_000
    batch_size = 40
    payload_bytes = 32 * 1024

    class StreamingProvider:
        async def discover(self):
            raise AssertionError("streaming path must not materialize all groups")

        async def discover_batches(self, *, batch_size: int):
            for start in range(0, group_count, batch_size):
                yield [
                    DiscoveredGroup(
                        group_id=f"immich:memory-{index}",
                        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
                        provider_group_id=f"memory-{index}",
                        assets=(left, right),  # type: ignore[arg-type]
                        provider_metadata={
                            "payload": f"{index:06d}-" + ("x" * payload_bytes)
                        },
                    )
                    for index in range(start, min(group_count, start + batch_size))
                ]

    provider = CompositeGroupDiscoveryProvider(StreamingProvider())  # type: ignore[arg-type]
    gc.collect()
    tracemalloc.start()
    consumed = 0
    try:
        async for batch in provider.discover_batches(batch_size=batch_size):
            consumed += len(batch)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert consumed == group_count
    # Full retention would exceed 64 MiB from metadata payloads alone. Keep enough
    # headroom for interpreter/test-runner allocations while requiring bounded behavior.
    assert peak < 24 * 1024 * 1024

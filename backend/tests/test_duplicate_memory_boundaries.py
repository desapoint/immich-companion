"""Architecture guards for bounded V2 duplicate hydration paths."""

from __future__ import annotations

import gc
import inspect
import tracemalloc
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.composite_duplicate_repository import CompositeDuplicateRepository
from companion.composite_duplicate_sync import CompositeDuplicateRebuildTaskHandler
from companion.discovery.base import DiscoveredGroup
from companion.discovery.composite import CompositeGroupDiscoveryProvider
from companion.discovery.immich_duplicates import ImmichDuplicateProvider
from companion.duplicate_schema import DuplicateAnalysisOptions
from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
)
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


def test_similarity_scan_streams_features_and_candidate_pairs() -> None:
    from companion.similarity_scan_service import SimilarityScanTaskHandler
    from companion.similarity_search_repository import SimilaritySearchRepository

    source = inspect.getsource(SimilarityScanTaskHandler.execute)
    assert "features = await self._features.list_current()" not in source
    assert "candidate_index.pairs" not in source
    assert "retain_pairs=False" in source
    assert "_candidate_feature_batches" in source
    assert "_current_features" in source

    repository_source = inspect.getsource(
        SimilaritySearchRepository.iter_current_candidates
    )
    assert ".limit(batch_size)" in repository_source
    assert "after_asset_id" in repository_source


def test_composite_group_ids_are_bounded_before_database_insert() -> None:
    from companion.composite_duplicate_repository import _validate_composite_group_id
    from companion.duplicate_identity import INDEXED_GROUP_ID_MAX_BYTES

    _validate_composite_group_id("a" * INDEXED_GROUP_ID_MAX_BYTES)
    with pytest.raises(ValueError, match="bounded indexed-key limit"):
        _validate_composite_group_id("a" * (INDEXED_GROUP_ID_MAX_BYTES + 1))


def test_similarity_projection_uses_bounded_repository_reads() -> None:
    from companion.asset_repository import AssetRepository
    from companion.discovery.similarity_duplicates import SimilarityDuplicateProvider
    from companion.similarity_scan_repository import SimilarityScanRepository

    provider_source = inspect.getsource(SimilarityDuplicateProvider._validated_groups)
    assert "iter_grouping_edges" in provider_source
    assert "SimilarityGroupValidator" in provider_source
    assert "edges: list" not in provider_source
    assert "latest_completed()" not in provider_source

    discovery_source = inspect.getsource(SimilarityDuplicateProvider.discover_batches)
    assert "get_immich_assets" in discovery_source

    asset_source = inspect.getsource(AssetRepository.get_immich_assets)
    assert "ASSET_HYDRATION_BATCH_SIZE" in asset_source

    complete_source = inspect.getsource(SimilarityScanRepository.complete)
    assert "SIMILARITY_SCAN_WRITE_BATCH_SIZE" in complete_source


def test_similarity_pair_retention_preserves_scan_metadata_rows() -> None:
    from companion.similarity_scan_repository import SimilarityScanRepository

    source = inspect.getsource(SimilarityScanRepository.prune_completed_pair_evidence)
    assert "delete(SimilarityScanPairRecord)" in source
    assert "delete(SimilarityScanRecord)" not in source
    assert "pair_evidence_pruned_at" in source
    assert ".offset(keep_completed_generations)" in source
    assert ".limit(prune_batch_size)" in source


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


@pytest.mark.asyncio
async def test_composite_repository_publication_does_not_retain_streamed_payloads() -> None:
    """Exercise the real repository publisher with a lightweight transactional adapter."""

    left = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        file_size_bytes=100,
        file_created_at=datetime(2026, 9, 19, tzinfo=UTC),
    )
    right = SimpleNamespace(
        id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        file_size_bytes=100,
        file_created_at=datetime(2026, 9, 19, tzinfo=UTC),
    )
    available_ids = [left.id, right.id]
    group_count = 2_000
    batch_size = 40
    payload_bytes = 32 * 1024

    async def batches():
        for start in range(0, group_count, batch_size):
            yield [
                DiscoveredGroup(
                    group_id=f"immich:publisher-{index}",
                    discovery_source=DiscoverySource.IMMICH_DUPLICATE,
                    provider_group_id=f"publisher-{index}",
                    assets=(left, right),  # type: ignore[arg-type]
                    provider_metadata={
                        "payload": f"{index:06d}-" + ("x" * payload_bytes)
                    },
                )
                for index in range(start, min(group_count, start + batch_size))
            ]

    class ScalarRows:
        def all(self):
            return available_ids

    class Session:
        state = SimpleNamespace(
            authoritative_generation=0,
            group_count=0,
            member_count=0,
            evidence_count=0,
            last_success_at=None,
        )

        @asynccontextmanager
        async def begin(self):
            yield self

        async def scalar(self, _statement):
            return self.state

        async def scalars(self, _statement):
            return ScalarRows()

        async def execute(self, _statement):
            return None

        def add(self, _record):
            return None

        async def flush(self):
            return None

    session = Session()

    class Database:
        @asynccontextmanager
        async def sessions(self):
            yield session

    repository = CompositeDuplicateRepository(Database())  # type: ignore[arg-type]
    gc.collect()
    tracemalloc.start()
    try:
        metadata = await repository.replace_snapshot_batches(batches())
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert metadata.group_count == group_count
    assert peak < 24 * 1024 * 1024


@pytest.mark.asyncio
async def test_exact_analysis_does_not_retain_streamed_group_payloads() -> None:
    """Exercise the real exact-analysis consumer without candidate verification I/O."""

    left = SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        library_id=None,
    )
    right = SimpleNamespace(
        id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        library_id=None,
    )
    group_count = 2_000
    batch_size = 40
    payload_bytes = 32 * 1024

    class Discovery:
        async def discover(self):
            raise AssertionError("streaming exact analysis must not materialize all groups")

        async def discover_batches(self):
            for start in range(0, group_count, batch_size):
                yield [
                    DiscoveredGroup(
                        group_id=f"immich:analysis-{index}",
                        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
                        provider_group_id=f"analysis-{index}",
                        assets=(left, right),  # type: ignore[arg-type]
                        provider_metadata={
                            "payload": f"{index:06d}-" + ("x" * payload_bytes)
                        },
                    )
                    for index in range(start, min(group_count, start + batch_size))
                ]

    class Context:
        async def checkpoint(self, **_kwargs):
            return None

        async def ensure_active(self):
            return None

    handler = CrossSourceDuplicateTaskHandler(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        discovery=Discovery(),  # type: ignore[arg-type]
    )

    gc.collect()
    tracemalloc.start()
    try:
        result = await handler.execute(
            Context(),  # type: ignore[arg-type]
            DuplicateAnalysisOptions().model_dump(mode="json"),
        )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert result.counters["duplicate_groups"] == group_count
    assert result.counters["candidate_files"] == 0
    assert peak < 24 * 1024 * 1024

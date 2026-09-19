"""Architecture guards for bounded V2 duplicate hydration paths."""

from __future__ import annotations

import inspect

from companion.composite_duplicate_repository import CompositeDuplicateRepository
from companion.composite_duplicate_sync import CompositeDuplicateRebuildTaskHandler
from companion.discovery.immich_duplicates import ImmichDuplicateProvider
from companion.duplicate_service import CrossSourceDuplicateService


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

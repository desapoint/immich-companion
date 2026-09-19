"""Architecture guards for bounded V2 duplicate hydration paths."""

from __future__ import annotations

import inspect

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

from companion.composite_duplicate_repository import CompositeDuplicateRepository


def test_composite_snapshot_publication_does_not_materialize_full_row_copies() -> None:
    source = inspect.getsource(CompositeDuplicateRepository.replace_snapshot)
    assert "member_rows = [" not in source
    assert "evidence_rows = [" not in source
    assert "group_rows = []" not in source
    assert "member_values.clear()" in source
    assert "evidence_values.clear()" in source

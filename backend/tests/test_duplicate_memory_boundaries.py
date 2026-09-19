"""Architecture guards for bounded V2 duplicate hydration paths."""

from __future__ import annotations

import inspect

from companion.duplicate_service import CrossSourceDuplicateService


def test_v2_single_group_and_preset_paths_do_not_call_full_result_hydration() -> None:
    """Keep ordinary V2 mutations off the legacy whole-library result contract."""

    methods = (
        CrossSourceDuplicateService.save_review,
        CrossSourceDuplicateService.similarity_reference,
        CrossSourceDuplicateService.apply_workspace_preset,
    )
    for method in methods:
        source = inspect.getsource(method)
        assert "self.result(" not in source
        assert "self._live_groups(" not in source

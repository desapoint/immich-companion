"""Regression guards for the backend domain decomposition boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1] / "companion"


def test_extracted_duplicate_mixins_do_not_import_the_facade() -> None:
    for name in ("duplicate_evidence.py", "duplicate_resolution.py"):
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert "companion.duplicate_service" not in imports


def test_extracted_repository_modules_have_expected_owners() -> None:
    search = (ROOT / "asset_repository_search.py").read_text(encoding="utf-8")
    selection = (ROOT / "asset_repository_selection.py").read_text(encoding="utf-8")
    assert "class AssetSearchMixin" in search
    assert "class AssetSelectionMixin" in selection


def test_neutral_similarity_helper_is_runtime_importable() -> None:
    from companion.duplicate_contracts import same_normalized_pixels

    assert same_normalized_pixels(None, None) is False

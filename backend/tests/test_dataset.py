"""Deterministic corpus invariants used by the disposable environment."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def generator_module() -> ModuleType:
    path = Path(__file__).parents[2] / "tools" / "generate_test_media.py"
    spec = importlib.util.spec_from_file_location("generate_test_media", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_corpus_is_repeatable_rich_and_larger_than_default_page(tmp_path: Path) -> None:
    generator = generator_module()
    first = tmp_path / "first"
    second = tmp_path / "second"

    manifest = generator.generate(first)
    generator.generate(second)

    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    for record in manifest["files"]:
        assert (first / record["path"]).read_bytes() == (second / record["path"]).read_bytes()
    for record in manifest["relationships"]["analysis_fixtures"]:
        assert (first / record["path"]).read_bytes() == (second / record["path"]).read_bytes()

    expected = manifest["expected"]
    relationships = manifest["relationships"]
    assert expected["unique_assets"] > expected["default_page_size"]
    assert expected["minimum_search_pages"] >= 2
    assert expected["trashed_assets"] > 0
    assert len(relationships["albums"]) >= 3
    assert len(relationships["stacks"]) >= 2
    assert len(relationships["tags"]) >= 3
    assert expected["tagged_assets"] > 0
    assert any(
        set(first_tag["paths"]) & set(second_tag["paths"])
        for index, first_tag in enumerate(relationships["tags"])
        for second_tag in relationships["tags"][index + 1 :]
    )
    assert relationships["pixel_identical_groups"]
    assert relationships["visually_similar_groups"]
    assert {
        record["expected_case"] for record in relationships["analysis_fixtures"]
    } == {"healthy", "trailing-bytes", "truncated-segment", "missing-soi"}
    assert all(
        record["upload_to_immich"] is False
        for record in relationships["analysis_fixtures"]
    )
    assert any(record["has_alpha"] for record in manifest["files"])
    assert len({record["aspect_ratio"] for record in manifest["files"]}) >= 4

    parsed = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert parsed == manifest

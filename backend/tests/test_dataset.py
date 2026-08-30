"""Deterministic corpus invariants used by the disposable environment."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType

from PIL import Image

from companion.image_decode import decode_image
from companion.integrity import FileIntegrityAnalyzer


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
    stale_external = first / "external-library" / "retired-fixture.jpg"
    stale_external.write_bytes(b"retired")
    regenerated = generator.generate(first)

    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    assert regenerated == manifest
    assert not stale_external.exists()
    for record in manifest["files"]:
        assert (first / record["path"]).read_bytes() == (second / record["path"]).read_bytes()
    for record in manifest["external_files"]:
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
    assert len(relationships["external_libraries"]) == 1
    assert relationships["external_libraries"][0]["read_only"] is True
    duplicate_groups = {
        fixture["case"]: fixture for fixture in relationships["duplicate_demo_groups"]
    }
    assert set(duplicate_groups) == {
        "byte-perfect-cross-source",
        "pixel-identical-different-bytes",
        "decodable-png-trailing-data",
        "same-filename-different-content",
        "same-filesize-different-content",
        "similar-brightness-darker",
        "similar-brightness-lighter",
        "similar-color-balance",
        "similar-small-occlusion",
        "similar-crop",
        "similar-resize",
    }
    for fixture in duplicate_groups.values():
        upload = (first / fixture["upload_path"]).read_bytes()
        external = (first / fixture["external_path"]).read_bytes()
        assert (upload == external) is (fixture["expected_byte_relation"] == "equal")
        with Image.open(io.BytesIO(upload)) as upload_image:
            upload_pixels = upload_image.convert("RGBA").tobytes()
        with Image.open(io.BytesIO(external)) as external_image:
            external_pixels = external_image.convert("RGBA").tobytes()
        assert (upload_pixels == external_pixels) is (
            fixture["expected_pixel_relation"] == "equal"
        )
    same_dimensions_similarity = {
        "similar-brightness-darker",
        "similar-brightness-lighter",
        "similar-color-balance",
        "similar-small-occlusion",
    }
    for case in same_dimensions_similarity:
        fixture = duplicate_groups[case]
        with Image.open(first / fixture["upload_path"]) as upload_image:
            upload_pixels = upload_image.convert("RGB").tobytes()
        with Image.open(first / fixture["external_path"]) as external_image:
            external_pixels = external_image.convert("RGB").tobytes()
        mean_absolute_delta = sum(
            abs(left - right) for left, right in zip(upload_pixels, external_pixels, strict=True)
        ) / len(upload_pixels)
        assert 0 < mean_absolute_delta < 16
    for case in {"similar-crop", "similar-resize"}:
        fixture = duplicate_groups[case]
        with Image.open(first / fixture["upload_path"]) as upload_image:
            upload_size = upload_image.size
        with Image.open(first / fixture["external_path"]) as external_image:
            external_size = external_image.size
        assert upload_size != external_size
    same_size = duplicate_groups["same-filesize-different-content"]
    assert (first / same_size["upload_path"]).stat().st_size == (
        first / same_size["external_path"]
    ).stat().st_size
    trailing = duplicate_groups["decodable-png-trailing-data"]
    assert (first / trailing["external_path"]).read_bytes().endswith(
        b"COMPANION-DEMO-TRAILING-DATA"
    )
    trailing_bytes = (first / trailing["external_path"]).read_bytes()
    analyzer = FileIntegrityAnalyzer("image/png", None)
    analyzer.update(trailing_bytes)
    integrity = analyzer.finalize()
    decoded = decode_image(io.BytesIO(trailing_bytes), integrity.detected_format)
    assert integrity.classification == "malformed"
    assert integrity.structurally_valid is False
    assert integrity.trailing_byte_count == len(b"COMPANION-DEMO-TRAILING-DATA")
    assert decoded.valid is True
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

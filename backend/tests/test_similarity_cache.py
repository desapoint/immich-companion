"""Bounded cache lifecycle and source-key regressions."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from companion.similarity_cache import BoundedPreviewCache, CachedPreview


def preview(content: bytes) -> CachedPreview:
    return CachedPreview(
        content=content,
        media_type="image/jpeg",
        etag='"preview-etag"',
        cache_control="private, max-age=300",
    )


def test_preview_cache_survives_recreation_and_tracks_hits(tmp_path) -> None:
    cache = BoundedPreviewCache(tmp_path, max_bytes=1024, max_age_seconds=3600)
    assert cache.get("asset:preview:v1") is None
    assert cache.put("asset:preview:v1", preview(b"preview-bytes")) is True

    restarted = BoundedPreviewCache(tmp_path, max_bytes=1024, max_age_seconds=3600)
    restored = restarted.get("asset:preview:v1")

    assert restored == preview(b"preview-bytes")
    assert restarted.status().hits == 1
    assert restarted.status().entry_count == 1


def test_preview_cache_evicts_least_recently_used_entries(tmp_path) -> None:
    cache = BoundedPreviewCache(tmp_path, max_bytes=256, max_age_seconds=3600)
    assert cache.put("first", preview(b"1" * 100)) is True
    assert cache.put("second", preview(b"2" * 100)) is True

    assert cache.get("first") is None
    assert cache.get("second") is not None
    assert cache.status().used_bytes <= 256
    assert cache.status().evictions == 1


def test_preview_cache_expires_old_entries(tmp_path) -> None:
    cache = BoundedPreviewCache(tmp_path, max_bytes=1024, max_age_seconds=60)
    assert cache.put("old", preview(b"old")) is True
    data_path = next(tmp_path.glob("*.data"))
    metadata_path = data_path.with_suffix(".json")
    old = datetime.now(UTC).timestamp() - 120
    os.utime(data_path, (old, old))
    os.utime(metadata_path, (old, old))

    assert cache.get("old") is None
    assert cache.status().entry_count == 0


def test_preview_cache_rejects_an_entry_larger_than_its_budget(tmp_path) -> None:
    cache = BoundedPreviewCache(tmp_path, max_bytes=100, max_age_seconds=60)

    assert cache.put("too-large", preview(b"1" * 100)) is False
    assert cache.status().entry_count == 0


def test_preview_cache_clear_does_not_touch_unrelated_files(tmp_path) -> None:
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    cache = BoundedPreviewCache(tmp_path, max_bytes=1024, max_age_seconds=60)
    cache.put("preview", preview(b"bytes"))

    assert cache.clear() == 1
    assert unrelated.read_text(encoding="utf-8") == "keep"

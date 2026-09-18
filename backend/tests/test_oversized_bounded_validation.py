"""Unified libvips visual normalization regressions."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
import shutil
from types import SimpleNamespace
from uuid import UUID

import pyvips
import pytest
from PIL import Image

from companion.immich import ImmichAsset
from companion.similarity_bounded_state import synchronized_source_identity
from companion.similarity_detail_service import SimilarityDetailMaintainer
from companion.similarity_index_service import SimilarityIndexMaintainer, _failure_is_retryable
from companion.similarity_visual_normalization import (
    DEFAULT_VISUAL_SOURCE_MAX_BYTES,
    SimilarityVisualNormalizer,
)

ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")
MODIFIED = datetime(2026, 9, 16, tzinfo=UTC)


def encoded_jpeg(size: tuple[int, int] = (640, 480)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (40, 80, 120)).save(output, format="JPEG")
    return output.getvalue()


def encoded_png(*, alpha: bool, size: tuple[int, int] = (1200, 800)) -> bytes:
    output = BytesIO()
    mode = "RGBA" if alpha else "RGB"
    color = (40, 80, 120, 128) if alpha else (40, 80, 120)
    Image.new(mode, size, color).save(output, format="PNG")
    return output.getvalue()


def image_source(**overrides: object) -> ImmichAsset:
    payload: dict[str, object] = {
        "id": str(ASSET_ID),
        "type": "IMAGE",
        "originalFileName": "large.jpg",
        "originalMimeType": "image/jpeg",
        "checksum": "source-checksum",
        "fileCreatedAt": MODIFIED.isoformat(),
        "fileModifiedAt": MODIFIED.isoformat(),
        "width": 18_000,
        "height": 10_000,
        "exifInfo": {"fileSizeInByte": 50_000_000},
    }
    payload.update(overrides)
    return ImmichAsset.model_validate(payload)


class Context:
    async def ensure_active(self) -> None:
        return None


def original_stream(content: bytes):
    @asynccontextmanager
    async def stream(_asset_id):
        async def chunks():
            yield content[: max(1, len(content) // 2)]
            yield content[max(1, len(content) // 2) :]

        yield SimpleNamespace(content_length=len(content), chunks=chunks())

    return stream


@pytest.mark.asyncio
async def test_oversized_original_is_normalized_directly_with_libvips(monkeypatch) -> None:
    monkeypatch.setattr(
        "companion.similarity_visual_normalization.MAX_VISUAL_DIMENSION",
        600,
    )
    original = encoded_jpeg((1200, 800))
    source = image_source(width=1800, height=1200)

    class Immich:
        stream_original = staticmethod(original_stream(original))

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            pytest.fail("Unified normalization must not request Immich full-size")

        async def get_bounded_preview(self, *_args, **_kwargs):
            pytest.fail("A decodable original must not use the preview fallback")

    normalizer = SimilarityVisualNormalizer(Immich())  # type: ignore[arg-type]
    normalized = await normalizer.normalize(
        Context(), ASSET_ID, source  # type: ignore[arg-type]
    )

    assert normalized.source_kind == "original"
    assert normalized.search_origin == "original"
    assert normalized.detail_origin == "original"
    assert (normalized.width, normalized.height) == (600, 400)
    assert normalized.resized is True


@pytest.mark.asyncio
async def test_unified_index_writes_search_and_detail_from_same_original_normalization() -> None:
    original = encoded_jpeg()
    source = image_source()

    class Immich:
        stream_original = staticmethod(original_stream(original))

        async def get_asset(self, _asset_id):
            return source

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            pytest.fail("Similarity indexing must not depend on Immich full-size")

        async def get_bounded_preview(self, *_args, **_kwargs):
            pytest.fail("A decodable original must not use preview fallback")

    class Assets:
        async def refresh_asset(self, *_args, **_kwargs):
            return None

    class Features:
        origin = None
        alpha_state = None
        media_sha256 = None

        async def save(
            self,
            asset,
            media_sha256,
            feature,
            *,
            origin="preview",
            source_alpha_state="unknown_alpha",
        ):
            assert asset.id == ASSET_ID
            assert feature.pixel_sha256 is None
            self.origin = origin
            self.alpha_state = source_alpha_state
            self.media_sha256 = media_sha256
            return True

        async def mark_unavailable(self, *_args, **_kwargs):
            return True

    class Details:
        source_identity = None
        origin = None
        feature = None

        async def save(self, source_identity, asset_id, feature, origin):
            assert asset_id == ASSET_ID
            self.source_identity = source_identity
            self.origin = origin
            self.feature = feature
            return True

    features = Features()
    details = Details()
    maintainer = SimilarityIndexMaintainer(
        Immich(),  # type: ignore[arg-type]
        Assets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        details=details,  # type: ignore[arg-type]
    )

    succeeded, reason = await maintainer._fingerprint_unbounded(
        Context(), ASSET_ID, source, attempt="test"  # type: ignore[arg-type]
    )

    assert succeeded is True
    assert reason is None
    assert features.origin == "original"
    assert features.alpha_state == "confirmed_opaque"
    assert len(features.media_sha256) == 64
    assert details.origin == "original"
    assert details.feature is not None
    assert details.feature.width == 640
    assert details.feature.height == 480
    assert maintainer.metrics()["detail_features_generated"] == 1
    assert maintainer.metrics()["original_fingerprints_generated"] == 1


@pytest.mark.asyncio
async def test_alpha_original_stays_alpha_through_libvips_normalization() -> None:
    original = encoded_png(alpha=True)
    source = image_source(
        originalFileName="large.png",
        originalMimeType="image/png",
    )

    class Immich:
        stream_original = staticmethod(original_stream(original))

        async def get_bounded_preview(self, *_args, **_kwargs):
            pytest.fail("Decodable alpha original must not use preview fallback")

    normalizer = SimilarityVisualNormalizer(Immich())  # type: ignore[arg-type]
    normalized = await normalizer.normalize(
        Context(), ASSET_ID, source  # type: ignore[arg-type]
    )

    assert normalized.source_kind == "original"
    assert normalized.has_alpha is True
    assert normalized.content.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_over_128_mib_original_skips_stream_and_uses_preview() -> None:
    preview = encoded_jpeg()
    source = image_source(
        width=4000,
        height=3000,
        exifInfo={"fileSizeInByte": DEFAULT_VISUAL_SOURCE_MAX_BYTES + 1},
    )

    class Immich:
        original_calls = 0
        preview_calls = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Known over-budget original must not be opened")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            pytest.fail("Full-size endpoint is not part of the unified pipeline")

        async def get_bounded_preview(self, _asset_id, *, max_bytes):
            assert max_bytes == DEFAULT_VISUAL_SOURCE_MAX_BYTES
            self.preview_calls += 1
            return preview

    immich = Immich()
    normalizer = SimilarityVisualNormalizer(immich)  # type: ignore[arg-type]
    normalized = await normalizer.normalize(
        Context(), ASSET_ID, source  # type: ignore[arg-type]
    )

    assert immich.original_calls == 0
    assert immich.preview_calls == 1
    assert normalized.source_kind == "preview"
    assert normalized.search_origin == "preview"
    assert normalized.detail_origin == "preview_fallback"


@pytest.mark.asyncio
async def test_detail_repair_uses_same_libvips_original_normalizer() -> None:
    original = encoded_png(alpha=False)
    source = image_source(
        originalFileName="large.png",
        originalMimeType="image/png",
    )
    search = SimpleNamespace(
        fingerprint_origin="original",
        width=source.width,
        height=source.height,
        source_identity="adapter-source",
        source_file_modified_at=source.file_modified_at,
        source_file_size_bytes=source.file_size_bytes,
        source_checksum=source.checksum,
    )

    class Immich:
        stream_original = staticmethod(original_stream(original))

        async def get_asset(self, _asset_id):
            return source

        async def get_bounded_preview(self, *_args, **_kwargs):
            pytest.fail("Decodable original must not use preview fallback")

    class Details:
        saved_origin = None

        async def save(self, source_identity, asset_id, feature, origin):
            assert source_identity == "adapter-source"
            assert asset_id == ASSET_ID
            assert feature.width == 1200
            assert feature.height == 800
            self.saved_origin = origin
            return True

    details = Details()
    maintainer = SimilarityDetailMaintainer(
        Immich(), details  # type: ignore[arg-type]
    )

    saved = await maintainer._extract_one(
        Context(), ASSET_ID, search, 1  # type: ignore[arg-type]
    )

    assert saved is True
    assert details.saved_origin == "original"
    assert maintainer.counters["detail_original_sources"] == 1
    assert maintainer.counters["preview_fallback_validations"] == 0


@pytest.mark.asyncio
async def test_visual_normalizer_keeps_128_mib_preview_fallback_budget() -> None:
    preview = encoded_jpeg()
    source = image_source(
        exifInfo={"fileSizeInByte": DEFAULT_VISUAL_SOURCE_MAX_BYTES + 1},
    )
    seen_max_bytes = None

    class Immich:
        async def get_bounded_preview(self, _asset_id, *, max_bytes):
            nonlocal seen_max_bytes
            seen_max_bytes = max_bytes
            return preview

    normalizer = SimilarityVisualNormalizer(Immich())  # type: ignore[arg-type]
    await normalizer.normalize(
        Context(), ASSET_ID, source  # type: ignore[arg-type]
    )

    assert DEFAULT_VISUAL_SOURCE_MAX_BYTES == 128 * 1024 * 1024
    assert seen_max_bytes == 128 * 1024 * 1024


def test_packaged_libvips_has_required_image_loaders() -> None:
    required = ("jpegload_buffer", "pngload_buffer", "heifload_buffer")
    missing = [
        operation
        for operation in required
        if not pyvips.type_find("VipsOperation", operation)
    ]
    direct_raw = bool(pyvips.type_find("VipsOperation", "dcrawload_buffer"))
    delegated_raw = bool(
        pyvips.type_find("VipsOperation", "magickload_buffer")
        and shutil.which("dcraw")
    )
    assert missing == []
    assert direct_raw or delegated_raw


def test_source_identity_invalidates_on_source_dimension_or_checksum_change() -> None:
    original = image_source()
    resized = image_source(width=17_999)
    changed = image_source(checksum="changed")
    assert synchronized_source_identity(original) != synchronized_source_identity(resized)
    assert synchronized_source_identity(original) != synchronized_source_identity(changed)


def test_normalized_decode_failures_are_deterministic() -> None:
    assert _failure_is_retryable("normalized_visual_feature_decode_failed") is False
    assert _failure_is_retryable("visual_source_decode_failed: invalid") is False
    assert _failure_is_retryable("visual_normalization_unavailable: HTTP 503") is True

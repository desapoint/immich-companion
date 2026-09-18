"""Oversized images use one bounded visual source for every similarity stage."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image

from companion.immich import ImmichAsset
from companion.similarity_bounded_state import synchronized_source_identity
from companion.similarity_detail_service import SimilarityDetailMaintainer
from companion.similarity_index_service import SimilarityIndexMaintainer, _failure_is_retryable
from companion.similarity_transparency import inspect_bounded_alpha
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
    if alpha:
        Image.new("RGBA", size, (40, 80, 120, 128)).save(output, format="PNG")
    else:
        Image.new("RGB", size, (40, 80, 120)).save(output, format="PNG")
    return output.getvalue()


def _bmff_box(box_type: bytes, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + box_type + payload


def encoded_heif_metadata(*, alpha: bool) -> bytes:
    ftyp = _bmff_box(b"ftyp", b"heic\x00\x00\x00\x00heic")
    meta_payload = b"\x00\x00\x00\x00" + _bmff_box(b"hdlr", b"pict")
    if alpha:
        meta_payload += _bmff_box(
            b"auxC",
            b"urn:mpeg:hevc:2015:auxid:1\x00",
        )
    return ftyp + _bmff_box(b"meta", meta_payload) + _bmff_box(b"mdat", b"")


def oversized_source(**overrides: object) -> ImmichAsset:
    payload: dict[str, object] = {
        "id": str(ASSET_ID),
        "type": "IMAGE",
        "originalFileName": "oversized.png",
        "originalMimeType": "image/png",
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


@pytest.mark.asyncio
async def test_oversized_source_normalizes_once_without_original_decode(monkeypatch) -> None:
    monkeypatch.setattr(
        "companion.similarity_visual_normalization.MAX_VISUAL_DIMENSION",
        600,
    )
    fullsize = encoded_jpeg((1200, 800))
    source = oversized_source(width=1800, height=1200)

    class Immich:
        original_calls = 0
        fullsize_calls = 0
        preview_calls = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Oversized visual analysis must never decode the original")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, asset_id, *, max_bytes):
            assert asset_id == ASSET_ID
            assert len(fullsize) < max_bytes
            self.fullsize_calls += 1
            return fullsize

        async def get_bounded_preview(self, *_args, **_kwargs):
            self.preview_calls += 1
            pytest.fail("Valid full-size bounded media should be preferred")

    immich = Immich()
    normalizer = SimilarityVisualNormalizer(immich)  # type: ignore[arg-type]
    normalized = await normalizer.normalize(Context(), ASSET_ID, source)  # type: ignore[arg-type]

    assert immich.original_calls == 0
    assert immich.fullsize_calls == 1
    assert immich.preview_calls == 0
    assert normalized.source_kind == "bounded_fullsize"
    assert normalized.search_origin == "bounded"
    assert normalized.detail_origin == "bounded_fullsize"
    assert (normalized.width, normalized.height) == (600, 400)
    assert normalized.resized is True


@pytest.mark.asyncio
async def test_unified_index_writes_search_and_detail_from_same_normalized_media() -> None:
    fullsize = encoded_jpeg()
    source = oversized_source()

    class Immich:
        async def get_bounded_fullsize(self, _asset_id, *, max_bytes):
            assert len(fullsize) < max_bytes
            return fullsize

        async def get_asset(self, _asset_id):
            return source

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            pytest.fail("Oversized indexing must not read the original")
            yield  # pragma: no cover

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
    assert features.origin == "bounded"
    assert features.alpha_state == "confirmed_opaque"
    assert len(features.media_sha256) == 64
    assert details.origin == "bounded_fullsize"
    assert details.feature is not None
    assert details.feature.width == 640
    assert details.feature.height == 480
    assert maintainer.metrics()["detail_features_generated"] == 1
    assert maintainer.metrics()["bounded_search_fingerprints_generated"] == 1


@pytest.mark.asyncio
async def test_flattened_alpha_capable_bounded_media_still_generates_localized_detail() -> None:
    flattened = encoded_jpeg()
    source = oversized_source(originalMimeType="image/png")

    class Immich:
        async def get_bounded_fullsize(self, *_args, **_kwargs):
            return flattened

        async def get_asset(self, _asset_id):
            return source

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            pytest.fail("Oversized alpha-capable source must remain bounded")
            yield  # pragma: no cover

    class Assets:
        async def refresh_asset(self, *_args, **_kwargs):
            return None

    class Features:
        source_identity = None

        async def save(
            self,
            asset,
            media_sha256,
            _feature,
            *,
            origin="preview",
            source_alpha_state="unknown_alpha",
        ):
            assert origin == "bounded"
            assert source_alpha_state == "confirmed_opaque"
            self.source_identity = (asset.id, media_sha256)
            return True

    class Details:
        saved = False

        async def save(self, _source_identity, _asset_id, _feature, origin):
            assert origin == "bounded_fullsize"
            self.saved = True
            return True

    details = Details()
    maintainer = SimilarityIndexMaintainer(
        Immich(),  # type: ignore[arg-type]
        Assets(),  # type: ignore[arg-type]
        Features(),  # type: ignore[arg-type]
        details=details,  # type: ignore[arg-type]
    )

    succeeded, reason = await maintainer._fingerprint_unbounded(
        Context(), ASSET_ID, source, attempt="test"  # type: ignore[arg-type]
    )

    assert succeeded is True
    assert reason is None
    assert details.saved is True


@pytest.mark.asyncio
async def test_detail_repair_uses_same_bounded_normalizer() -> None:
    fullsize = encoded_png(alpha=False)
    source = oversized_source()
    search = SimpleNamespace(
        fingerprint_origin="bounded",
        width=source.width,
        height=source.height,
        source_identity="adapter-source",
        source_file_modified_at=source.file_modified_at,
        source_file_size_bytes=source.file_size_bytes,
        source_checksum=source.checksum,
    )

    class Immich:
        original_calls = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Oversized detail repair must not decode the original")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            return fullsize

        async def get_asset(self, _asset_id):
            return source

    class Details:
        saved_origin = None

        async def save(self, source_identity, asset_id, feature, origin):
            assert source_identity == "adapter-source"
            assert asset_id == ASSET_ID
            assert feature.width == 1200
            assert feature.height == 800
            self.saved_origin = origin
            return True

    immich = Immich()
    details = Details()
    maintainer = SimilarityDetailMaintainer(immich, details)  # type: ignore[arg-type]

    saved = await maintainer._extract_one(
        Context(), ASSET_ID, search, 1  # type: ignore[arg-type]
    )

    assert saved is True
    assert immich.original_calls == 0
    assert details.saved_origin == "bounded_fullsize"
    assert maintainer.counters["bounded_candidate_validations"] == 1
    assert maintainer.counters["detail_oversized_original_decodes_avoided"] == 1


@pytest.mark.asyncio
async def test_known_over_budget_original_skips_original_stream() -> None:
    fullsize = encoded_jpeg()
    source = oversized_source(
        width=4000,
        height=3000,
        exifInfo={"fileSizeInByte": DEFAULT_VISUAL_SOURCE_MAX_BYTES + 1},
    )

    class Immich:
        original_calls = 0
        fullsize_calls = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Known over-budget original must not be opened")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, _asset_id, *, max_bytes):
            assert max_bytes == DEFAULT_VISUAL_SOURCE_MAX_BYTES
            self.fullsize_calls += 1
            return fullsize

    immich = Immich()
    normalizer = SimilarityVisualNormalizer(immich)  # type: ignore[arg-type]
    normalized = await normalizer.normalize(
        Context(), ASSET_ID, source  # type: ignore[arg-type]
    )

    assert immich.original_calls == 0
    assert immich.fullsize_calls == 1
    assert normalized.source_kind == "bounded_fullsize"
    assert normalized.search_origin == "preview"


@pytest.mark.asyncio
async def test_visual_normalizer_keeps_128_mib_fetch_budget() -> None:
    fullsize = encoded_jpeg()
    source = oversized_source()
    seen_max_bytes = None

    class Immich:
        async def get_bounded_fullsize(self, _asset_id, *, max_bytes):
            nonlocal seen_max_bytes
            seen_max_bytes = max_bytes
            return fullsize

    normalizer = SimilarityVisualNormalizer(Immich())  # type: ignore[arg-type]
    await normalizer.normalize(Context(), ASSET_ID, source)  # type: ignore[arg-type]

    assert DEFAULT_VISUAL_SOURCE_MAX_BYTES == 128 * 1024 * 1024
    assert seen_max_bytes == 128 * 1024 * 1024


def test_transparency_header_states_remain_available_for_other_evidence_paths() -> None:
    assert inspect_bounded_alpha(encoded_jpeg()) == "confirmed_opaque"
    assert inspect_bounded_alpha(encoded_png(alpha=False)) == "confirmed_opaque"
    assert inspect_bounded_alpha(encoded_png(alpha=True)) == "confirmed_alpha"
    assert inspect_bounded_alpha(encoded_heif_metadata(alpha=False)) == "confirmed_opaque"
    assert inspect_bounded_alpha(encoded_heif_metadata(alpha=True)) == "confirmed_alpha"
    assert inspect_bounded_alpha(b"not-an-image") == "unknown_alpha"


def test_source_identity_invalidates_on_source_dimension_or_checksum_change() -> None:
    original = oversized_source()
    resized = oversized_source(width=17_999)
    changed = oversized_source(checksum="changed")
    assert synchronized_source_identity(original) != synchronized_source_identity(resized)
    assert synchronized_source_identity(original) != synchronized_source_identity(changed)


def test_normalized_decode_failures_are_deterministic() -> None:
    assert _failure_is_retryable("image_decode_limit_exceeded") is False
    assert _failure_is_retryable("normalized_visual_feature_decode_failed") is False
    assert _failure_is_retryable("visual_source_decode_failed: invalid") is False
    assert _failure_is_retryable("visual_normalization_unavailable: HTTP 503") is True

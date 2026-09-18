"""Oversized originals stay discoverable through explicitly bounded visual evidence."""

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
from companion.similarity_index_service import (
    SimilarityIndexMaintainer,
    _failure_is_retryable,
)
from companion.similarity_transparency import inspect_bounded_alpha

ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")
MODIFIED = datetime(2026, 9, 16, tzinfo=UTC)


def encoded_jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (640, 480), (40, 80, 120)).save(output, format="JPEG")
    return output.getvalue()


def encoded_png(*, alpha: bool) -> bytes:
    output = BytesIO()
    if alpha:
        Image.new("RGBA", (1200, 800), (40, 80, 120, 128)).save(output, format="PNG")
    else:
        Image.new("RGB", (1200, 800), (40, 80, 120)).save(output, format="PNG")
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
async def test_oversized_alpha_capable_source_uses_search_only_preview() -> None:
    preview = encoded_jpeg()
    source = oversized_source()

    class Immich:
        original_calls = 0

        async def get_bounded_preview(self, asset_id, *, max_bytes):
            assert asset_id == ASSET_ID
            assert len(preview) < max_bytes
            return preview

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Known-oversized original must not be decoded for search indexing")
            yield  # pragma: no cover

        async def get_asset(self, _asset_id):
            return source

    class Assets:
        async def refresh_asset(self, *_args, **_kwargs):
            return None

    class Features:
        origin = None
        alpha_state = None

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
            assert len(media_sha256) == 64
            assert feature.pixel_sha256 is None
            self.origin = origin
            self.alpha_state = source_alpha_state
            return True

        async def mark_unavailable(self, *_args, **_kwargs):
            return True

    immich = Immich()
    features = Features()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        Assets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
    )

    succeeded, reason = await maintainer._fingerprint_unbounded(
        Context(), ASSET_ID, source, attempt="test"  # type: ignore[arg-type]
    )

    assert succeeded is True
    assert reason is None
    assert immich.original_calls == 0
    assert features.origin == "bounded"
    assert features.alpha_state == "unknown_alpha"
    assert maintainer.metrics()["oversized_original_decodes_avoided"] == 1
    assert maintainer.metrics()["alpha_uncertain_bounded_evidence"] == 1
    assert maintainer.metrics()["bounded_search_fingerprints_generated"] == 1


@pytest.mark.asyncio
async def test_alpha_capable_opaque_oversized_source_uses_same_family_fullsize() -> None:
    fullsize = encoded_png(alpha=False)
    source = oversized_source()
    search = SimpleNamespace(
        fingerprint_origin="bounded",
        width=source.width,
        height=source.height,
        source_identity="bounded-source",
        source_file_modified_at=source.file_modified_at,
        source_file_size_bytes=source.file_size_bytes,
        source_checksum=source.checksum,
    )

    class Immich:
        original_calls = 0
        preview_calls = 0
        fullsize_calls = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Known-oversized detail validation must not decode the original")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, asset_id, *, max_bytes):
            assert asset_id == ASSET_ID
            assert len(fullsize) < max_bytes
            self.fullsize_calls += 1
            return fullsize

        async def get_bounded_preview(self, *_args, **_kwargs):
            self.preview_calls += 1
            pytest.fail("Valid full-size bounded evidence should be preferred")

        async def get_asset(self, _asset_id):
            return source

    class Details:
        saved_origin = None

        async def source_alpha_state(self, *_args):
            return "unknown_alpha"

        async def save(self, source_identity, asset_id, feature, origin):
            assert source_identity == "bounded-source"
            assert asset_id == ASSET_ID
            assert feature.width == 1200
            assert feature.height == 800
            self.saved_origin = origin
            return True

        async def mark_unavailable(self, *_args):
            pytest.fail("Valid same-family opaque bounded evidence must not be unavailable")

    immich = Immich()
    details = Details()
    maintainer = SimilarityDetailMaintainer(immich, details)  # type: ignore[arg-type]

    saved = await maintainer._extract_one(
        Context(), ASSET_ID, search, 1  # type: ignore[arg-type]
    )

    assert saved is True
    assert immich.original_calls == 0
    assert immich.fullsize_calls == 1
    assert immich.preview_calls == 0
    assert details.saved_origin == "bounded_fullsize"
    assert maintainer.counters["bounded_candidate_validations"] == 1
    assert maintainer.counters["detail_oversized_original_decodes_avoided"] == 1


@pytest.mark.asyncio
async def test_opaque_oversized_heic_uses_original_metadata_probe_then_jpeg_fullsize() -> None:
    source = oversized_source(
        originalFileName="oversized.heic",
        originalMimeType="image/heic",
    )
    original_prefix = encoded_heif_metadata(alpha=False)
    fullsize = encoded_jpeg()
    search = SimpleNamespace(
        fingerprint_origin="bounded",
        width=source.width,
        height=source.height,
        source_identity="bounded-heic-source",
        source_file_modified_at=source.file_modified_at,
        source_file_size_bytes=source.file_size_bytes,
        source_checksum=source.checksum,
    )

    class Immich:
        prefix_calls = 0
        fullsize_calls = 0
        preview_calls = 0

        async def get_original_prefix(self, asset_id, *, max_bytes):
            assert asset_id == ASSET_ID
            assert len(original_prefix) < max_bytes
            self.prefix_calls += 1
            return original_prefix

        async def get_bounded_fullsize(self, asset_id, *, max_bytes):
            assert asset_id == ASSET_ID
            assert len(fullsize) < max_bytes
            self.fullsize_calls += 1
            return fullsize

        async def get_bounded_preview(self, *_args, **_kwargs):
            self.preview_calls += 1
            pytest.fail("Opaque HEIC metadata should make the full-size JPEG safe")

        async def get_asset(self, _asset_id):
            return source

    class Details:
        saved_origin = None

        async def source_alpha_state(self, *_args):
            return "unknown_alpha"

        async def save(self, source_identity, asset_id, feature, origin):
            assert source_identity == "bounded-heic-source"
            assert asset_id == ASSET_ID
            assert feature.width == 640
            assert feature.height == 480
            self.saved_origin = origin
            return True

        async def mark_unavailable(self, *_args):
            pytest.fail("Opaque HEIC should no longer be stranded as unavailable")

    immich = Immich()
    details = Details()
    maintainer = SimilarityDetailMaintainer(immich, details)  # type: ignore[arg-type]

    assert await maintainer._extract_one(
        Context(), ASSET_ID, search, 1  # type: ignore[arg-type]
    )
    assert immich.prefix_calls == 1
    assert immich.fullsize_calls == 1
    assert immich.preview_calls == 0
    assert details.saved_origin == "bounded_fullsize"
    assert maintainer.counters["detail_alpha_source_probe_confirmed_opaque"] == 1
    assert maintainer.counters["bounded_candidate_validations"] == 1


@pytest.mark.asyncio
async def test_confirmed_alpha_oversized_source_requires_alpha_preserving_bounded_media() -> None:
    fullsize = encoded_png(alpha=True)
    source = oversized_source()
    search = SimpleNamespace(
        fingerprint_origin="bounded",
        width=source.width,
        height=source.height,
        source_identity="bounded-alpha-source",
        source_file_modified_at=source.file_modified_at,
        source_file_size_bytes=source.file_size_bytes,
        source_checksum=source.checksum,
    )

    class Immich:
        @asynccontextmanager
        async def stream_original(self, _asset_id):
            pytest.fail("Confirmed-alpha oversized validation must not decode the original")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            return fullsize

        async def get_bounded_preview(self, *_args, **_kwargs):
            pytest.fail("Alpha-preserving fullsize should win over preview")

        async def get_asset(self, _asset_id):
            return source

    class Details:
        saved_origin = None

        async def source_alpha_state(self, *_args):
            return "confirmed_alpha"

        async def save(self, _source_identity, _asset_id, _feature, origin):
            self.saved_origin = origin
            return True

    details = Details()
    maintainer = SimilarityDetailMaintainer(Immich(), details)  # type: ignore[arg-type]
    assert await maintainer._extract_one(
        Context(), ASSET_ID, search, 1  # type: ignore[arg-type]
    )
    assert details.saved_origin == "bounded_fullsize"
    assert maintainer.counters["bounded_candidate_validations"] == 1


@pytest.mark.asyncio
async def test_unknown_alpha_flattened_bounded_media_is_not_promoted_to_detail() -> None:
    flattened = encoded_jpeg()
    source = oversized_source()
    search = SimpleNamespace(
        fingerprint_origin="bounded",
        width=source.width,
        height=source.height,
        source_identity="bounded-unknown-source",
        source_file_modified_at=source.file_modified_at,
        source_file_size_bytes=source.file_size_bytes,
        source_checksum=source.checksum,
    )

    class Immich:
        original_calls = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Unknown-alpha oversized validation must not decode the original")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            return flattened

        async def get_bounded_preview(self, *_args, **_kwargs):
            return flattened

        async def get_asset(self, _asset_id):
            return source

    class Details:
        unavailable_reason = None

        async def source_alpha_state(self, *_args):
            return "unknown_alpha"

        async def save(self, *_args, **_kwargs):
            pytest.fail("Flattened unknown-alpha evidence must remain search-only")

        async def mark_unavailable(self, _source_identity, _asset_id, reason):
            self.unavailable_reason = reason
            return True

    immich = Immich()
    details = Details()
    maintainer = SimilarityDetailMaintainer(immich, details)  # type: ignore[arg-type]

    assert not await maintainer._extract_one(
        Context(), ASSET_ID, search, 1  # type: ignore[arg-type]
    )
    assert immich.original_calls == 0
    assert details.unavailable_reason == "alpha_preserving_bounded_rendition_unavailable"
    assert maintainer.counters["unavailable_bounded_validations"] == 1
    assert maintainer.counters["deterministic_retries_suppressed"] == 1


@pytest.mark.asyncio
async def test_oversized_preview_decode_failure_persists_and_is_not_retried() -> None:
    source = oversized_source()

    class Immich:
        preview_calls = 0

        async def get_bounded_preview(self, asset_id, *, max_bytes):
            assert asset_id == ASSET_ID
            self.preview_calls += 1
            return b"not-an-image"

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            pytest.fail("Known-oversized original must not be used as failure fallback")
            yield  # pragma: no cover

    class Assets:
        async def get_immich_assets(self, asset_ids):
            return {asset_id: source for asset_id in asset_ids}

    class Features:
        unavailable = False

        async def coverage(self):
            if self.unavailable:
                return 1, 0, 0, 1, 0, 0
            return 1, 0, 0, 0, 1, 0

        async def list_work(self, *, after_asset_id, limit):
            if self.unavailable:
                return []
            return [ASSET_ID] if after_asset_id is None else []

        async def mark_unavailable(self, asset, reason, *, source_alpha_state):
            assert asset.id == ASSET_ID
            assert reason == "bounded_preview_decode_failed"
            assert source_alpha_state == "unknown_alpha"
            self.unavailable = True
            return True

    class MaintenanceContext(Context):
        def __init__(self) -> None:
            self.task = SimpleNamespace(checkpoint={})
            self.checkpoints: list[dict[str, object]] = []

        async def checkpoint(self, **values) -> None:
            self.checkpoints.append(values)

    immich = Immich()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        Assets(),  # type: ignore[arg-type]
        Features(),  # type: ignore[arg-type]
    )

    coverage, completed, unavailable, attempted, reasons = await maintainer.maintain(
        MaintenanceContext()  # type: ignore[arg-type]
    )

    assert coverage.complete is True
    assert completed == 0
    assert unavailable == 1
    assert attempted == {ASSET_ID}
    assert reasons[ASSET_ID] == "bounded_preview_decode_failed"
    assert immich.preview_calls == 1
    assert maintainer.metrics()["deterministic_retries_suppressed"] == 1


def test_transparency_header_states_are_explicit() -> None:
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


def test_deterministic_decode_limit_failure_is_not_retried() -> None:
    assert _failure_is_retryable("image_decode_limit_exceeded") is False
    assert _failure_is_retryable("original exceeds similarity fallback size limit") is False
    assert _failure_is_retryable("bounded_preview_decode_failed") is False
    assert _failure_is_retryable("bounded_rendition_unavailable: HTTP 503") is True

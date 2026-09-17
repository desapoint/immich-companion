"""Oversized originals stay discoverable through explicitly bounded visual evidence."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image

from companion.immich import ImmichAsset
from companion.similarity_detail_service import SimilarityDetailMaintainer
from companion.similarity_index_service import (
    SimilarityIndexMaintainer,
    _failure_is_retryable,
)

ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")
MODIFIED = datetime(2026, 9, 16, tzinfo=UTC)


def encoded_preview() -> bytes:
    output = BytesIO()
    Image.new("RGB", (640, 480), (40, 80, 120)).save(output, format="JPEG")
    return output.getvalue()


def oversized_source() -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(ASSET_ID),
            "type": "IMAGE",
            "originalFileName": "oversized.png",
            "originalMimeType": "image/png",
            "checksum": "source-checksum",
            "fileCreatedAt": MODIFIED.isoformat(),
            "fileModifiedAt": MODIFIED.isoformat(),
            "width": 16320,
            "height": 12240,
            "exifInfo": {"fileSizeInByte": 50_000_000},
        }
    )


class Context:
    async def ensure_active(self) -> None:
        return None


@pytest.mark.asyncio
async def test_oversized_alpha_capable_source_indexes_bounded_preview_without_original() -> None:
    preview = encoded_preview()
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

        async def save(self, asset, media_sha256, feature, *, origin="preview"):
            assert asset.id == ASSET_ID
            assert len(media_sha256) == 64
            assert feature.pixel_sha256 is None
            self.origin = origin
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
    assert maintainer.metrics()["oversized_original_decodes_avoided"] == 1
    assert maintainer.metrics()["bounded_alpha_uncertain_fingerprints"] == 1


@pytest.mark.asyncio
async def test_oversized_candidate_detail_uses_preview_without_original_or_fullsize() -> None:
    preview = encoded_preview()
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
        fullsize_calls = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1
            pytest.fail("Known-oversized detail validation must not decode the original")
            yield  # pragma: no cover

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            self.fullsize_calls += 1
            pytest.fail("Known-oversized detail validation should use the bounded preview")

        async def get_bounded_preview(self, asset_id, *, max_bytes):
            assert asset_id == ASSET_ID
            assert len(preview) < max_bytes
            return preview

        async def get_asset(self, _asset_id):
            return source

    class Details:
        saved_origin = None

        async def save(self, source_identity, asset_id, feature, origin):
            assert source_identity == "bounded-source"
            assert asset_id == ASSET_ID
            assert feature.width == 640
            assert feature.height == 480
            self.saved_origin = origin
            return True

    immich = Immich()
    details = Details()
    maintainer = SimilarityDetailMaintainer(
        immich, details  # type: ignore[arg-type]
    )

    saved = await maintainer._extract_one(
        Context(), ASSET_ID, search  # type: ignore[arg-type]
    )

    assert saved is True
    assert immich.original_calls == 0
    assert immich.fullsize_calls == 0
    assert details.saved_origin == "preview_fallback"
    assert maintainer.counters["detail_oversized_bounded_validations"] == 1
    assert maintainer.counters["detail_oversized_original_decodes_avoided"] == 1


@pytest.mark.asyncio
async def test_oversized_preview_decode_failure_is_not_retried_by_maintenance() -> None:
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
        async def coverage(self):
            return 1, 0, 1, 0

        async def list_work(self, *, after_asset_id, limit):
            return [ASSET_ID] if after_asset_id is None else []

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

    assert coverage.complete is False
    assert completed == 0
    assert unavailable == 1
    assert attempted == {ASSET_ID}
    assert "bounded preview could not produce coarse visual evidence" in reasons[ASSET_ID]
    assert immich.preview_calls == 1


def test_deterministic_decode_limit_failure_is_not_retried() -> None:
    assert _failure_is_retryable("image_decode_limit_exceeded") is False
    assert _failure_is_retryable("original exceeds similarity fallback size limit") is False
    assert _failure_is_retryable("ImmichApiError: generated preview unavailable") is True

"""Regression coverage for a realistic 180 MP opaque JPEG source."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image

from companion.immich import ImmichAsset
from companion.similarity_index_service import SimilarityIndexMaintainer

ASSET_ID = UUID("22222222-2222-4222-8222-222222222222")
MODIFIED = datetime(2026, 9, 16, tzinfo=UTC)


def jpeg_preview() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1600, 900), (90, 110, 130)).save(output, format="JPEG")
    return output.getvalue()


def source() -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(ASSET_ID),
            "type": "IMAGE",
            "originalFileName": "180mp.jpg",
            "originalMimeType": "image/jpeg",
            "checksum": "opaque-jpeg-source",
            "fileCreatedAt": MODIFIED.isoformat(),
            "fileModifiedAt": MODIFIED.isoformat(),
            "width": 18_000,
            "height": 10_000,
            "exifInfo": {"fileSizeInByte": 78_000_000},
        }
    )


class Context:
    async def ensure_active(self) -> None:
        return None


@pytest.mark.asyncio
async def test_180mp_metadata_jpeg_uses_original_libvips_normalization() -> None:
    asset = source()
    preview = jpeg_preview()

    class Immich:
        original_calls = 0

        async def get_bounded_preview(self, *_args, **_kwargs):
            pytest.fail("Decodable original must not use preview fallback")

        @asynccontextmanager
        async def stream_original(self, asset_id):
            assert asset_id == ASSET_ID
            self.original_calls += 1

            async def chunks():
                yield preview

            yield SimpleNamespace(content_length=len(preview), chunks=chunks())

        async def get_asset(self, _asset_id):
            return asset

    class Assets:
        async def refresh_asset(self, *_args, **_kwargs):
            return None

    class Features:
        origin = None
        alpha_state = None

        async def save(
            self,
            _asset,
            _media_sha256,
            _feature,
            *,
            origin="preview",
            source_alpha_state="unknown_alpha",
        ):
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
        Context(), ASSET_ID, asset, attempt="test"  # type: ignore[arg-type]
    )

    assert succeeded is True
    assert reason is None
    assert immich.original_calls == 1
    assert features.origin == "original"
    assert features.alpha_state == "confirmed_opaque"
    assert maintainer.metrics()["original_fingerprints_generated"] == 1

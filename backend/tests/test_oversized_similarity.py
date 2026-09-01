"""Regression coverage for bounded oversized-image similarity evidence."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.immich import ImmichAsset
from companion.integrity_service import (
    PREVIEW_PIXEL_NORMALIZATION_VERSION,
    IntegrityTaskHandler,
)
from companion.similarity_features import (
    SIMILARITY_FEATURE_VERSION,
    SIMILARITY_MODEL_VERSION,
    VisualFeatureResult,
)

ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")


def oversized_asset() -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(ASSET_ID),
            "type": "IMAGE",
            "originalFileName": "200mp.jpg",
            "originalMimeType": "image/jpeg",
            "checksum": "checksum",
            "fileCreatedAt": datetime.now(UTC).isoformat(),
            "fileModifiedAt": datetime.now(UTC).isoformat(),
            "width": 16320,
            "height": 12240,
            "exifInfo": {"fileSizeInByte": 50_000_000},
        }
    )


def preview_feature() -> VisualFeatureResult:
    return VisualFeatureResult(
        model_version=SIMILARITY_MODEL_VERSION,
        feature_version=SIMILARITY_FEATURE_VERSION,
        width=1440,
        height=1080,
        luminance_vector=bytes([128] * 256),
        perceptual_hash="0" * 16,
        color_histogram=bytes([0] * 48),
        thumbnail_sha256="2" * 64,
        pixel_normalization_version=1,
        pixel_sha256="3" * 64,
        bit_depth=8,
        channel_count=3,
        has_alpha=False,
        color_space="RGB",
        orientation=None,
        icc_profile_present=False,
        has_exif=False,
        has_capture_time=False,
        has_camera_info=False,
        has_gps=False,
        has_orientation_metadata=False,
        metadata_richness=0,
    )


class FakeImmich:
    def __init__(self) -> None:
        self.requests: list[tuple[UUID, str]] = []

    async def get_thumbnail(self, asset_id: UUID, *, size: str):
        self.requests.append((asset_id, size))
        return SimpleNamespace(content=b"bounded-preview")


@pytest.mark.asyncio
async def test_oversized_similarity_uses_bounded_preview_without_exact_pixel_identity(
    monkeypatch,
) -> None:
    immich = FakeImmich()
    handler = IntegrityTaskHandler(immich, object(), object())
    seen: list[tuple[bytes, str]] = []
    expected = preview_feature()

    def extract(stream, detected_format):
        seen.append((stream.read(), detected_format))
        return expected

    monkeypatch.setattr("companion.integrity_service.extract_visual_features", extract)

    result = await handler._oversized_preview_feature(oversized_asset())

    assert result is not None
    assert immich.requests == [(ASSET_ID, "preview")]
    assert seen == [(b"bounded-preview", "jpeg")]
    assert result.width == 16320
    assert result.height == 12240
    assert result.pixel_normalization_version == PREVIEW_PIXEL_NORMALIZATION_VERSION
    assert result.pixel_normalization_version != expected.pixel_normalization_version

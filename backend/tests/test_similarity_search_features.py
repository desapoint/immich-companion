"""Preview search evidence never acts as original-file verification."""

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

from PIL import Image

from companion.immich import ImmichAsset
from companion.similarity_search_features import (
    SEARCH_FEATURE_VERSION,
    extract_search_feature,
    search_source_identity,
)


def _asset(*, modified: datetime | None = None) -> ImmichAsset:
    timestamp = modified or datetime(2026, 9, 12, tzinfo=UTC)
    return ImmichAsset.model_validate(
        {
            "id": str(UUID(int=1)),
            "type": "IMAGE",
            "originalFileName": "fixture.jpg",
            "fileCreatedAt": timestamp.isoformat(),
            "fileModifiedAt": timestamp.isoformat(),
            "exifInfo": {"fileSizeInByte": 1_000_000},
            "width": 4000,
            "height": 3000,
        }
    )


def test_search_feature_uses_normalized_visual_input_without_exact_pixel_hash() -> None:
    output = BytesIO()
    Image.new("RGB", (64, 48), (30, 90, 150)).save(output, format="PNG")

    feature = extract_search_feature(output.getvalue())

    assert feature is not None
    assert SEARCH_FEATURE_VERSION == 4
    assert feature.feature_version == 3
    assert feature.width == 64
    assert feature.height == 48
    assert len(feature.luminance_vector) == 512
    assert len(feature.color_histogram) == 48
    assert len(feature.perceptual_hash) == 16
    assert feature.pixel_sha256 is None


def test_search_feature_rejects_empty_or_invalid_normalized_media() -> None:
    assert extract_search_feature(b"") is None
    assert extract_search_feature(b"not an image") is None


def test_search_identity_is_not_original_hash_and_changes_with_source_or_preview() -> None:
    asset = _asset()
    first = search_source_identity(asset, "1" * 64)

    assert len(first) == 64
    assert first == search_source_identity(asset, "1" * 64)
    assert first != search_source_identity(asset, "2" * 64)
    assert first != search_source_identity(asset, "1" * 64, origin="original")
    assert first != search_source_identity(
        _asset(modified=datetime(2026, 9, 13, tzinfo=UTC)), "1" * 64
    )

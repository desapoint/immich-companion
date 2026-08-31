"""Regression corpus for compact exposure-tolerant visual features."""

from io import BytesIO

import pytest
from PIL import Image, ImageCms, ImageDraw, ImageEnhance

from companion.similarity_features import (
    COLOR_HISTOGRAM_LENGTH,
    LUMINANCE_VECTOR_LENGTH,
    compare_visual_features,
    extract_visual_features,
)


def scene() -> Image.Image:
    image = Image.new("RGB", (192, 128), (28, 42, 58))
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, 91, 106), fill=(210, 88, 42))
    draw.ellipse((100, 20, 174, 94), fill=(55, 176, 128))
    draw.line((8, 118, 184, 8), fill=(238, 222, 130), width=7)
    return image


def features(image: Image.Image):
    payload = BytesIO()
    image.save(payload, format="PNG")
    result = extract_visual_features(payload, "png")
    assert result is not None
    return result


def test_visual_features_are_fixed_size_and_deterministic() -> None:
    first = features(scene())
    second = features(scene())

    assert first == second
    assert len(first.luminance_vector) == LUMINANCE_VECTOR_LENGTH
    assert len(first.perceptual_hash) == 16
    assert len(first.color_histogram) == COLOR_HISTOGRAM_LENGTH
    assert len(first.thumbnail_sha256) == 64
    assert len(first.pixel_sha256) == 64
    comparison = compare_visual_features(first, second)
    assert comparison.similarity_percent == 100
    assert comparison.color_percent == 100
    assert comparison.normalized_luminance_mae == 0
    assert comparison.normalized_luminance_rmse == 0
    assert comparison.normalized_luminance_ssim == 1
    assert comparison.aspect_ratio_difference == 0
    assert comparison.dimensions_equal is True


def test_lossless_container_and_opaque_alpha_share_normalized_pixels() -> None:
    rgb = scene()
    opaque_rgba = rgb.convert("RGBA")

    rgb_payload = BytesIO()
    rgb.save(rgb_payload, format="TIFF")
    rgba_payload = BytesIO()
    opaque_rgba.save(rgba_payload, format="PNG")

    rgb_result = extract_visual_features(rgb_payload, "tiff")
    rgba_result = extract_visual_features(rgba_payload, "png")

    assert rgb_result is not None
    assert rgba_result is not None
    assert rgb_result.pixel_sha256 == rgba_result.pixel_sha256
    assert rgb_result.has_alpha is False
    assert rgba_result.has_alpha is True


def test_meaningful_alpha_and_dimensions_change_normalized_pixel_identity() -> None:
    opaque = scene().convert("RGBA")
    translucent = opaque.copy()
    translucent.putalpha(127)

    opaque_result = features(opaque)
    translucent_result = features(translucent)
    resized_result = features(opaque.resize((96, 256)))

    assert opaque_result.pixel_sha256 != translucent_result.pixel_sha256
    assert opaque_result.pixel_sha256 != resized_result.pixel_sha256


def test_palette_transparency_is_retained_in_normalized_pixels() -> None:
    palette = scene().convert("P", palette=Image.Palette.ADAPTIVE, colors=16)
    palette.info["transparency"] = 0
    payload = BytesIO()
    palette.save(payload, format="PNG", transparency=0)

    result = extract_visual_features(payload, "png")

    assert result is not None
    assert result.has_alpha is True


def test_compact_metadata_preservation_facts_are_extracted() -> None:
    payload = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    exif[36867] = "2026:08:31 12:34:56"
    exif[271] = "Companion Camera"
    exif[272] = "Test Model"
    scene().save(payload, format="JPEG", exif=exif)

    result = extract_visual_features(payload, "jpeg")

    assert result is not None
    assert result.has_exif is True
    assert result.has_capture_time is True
    assert result.has_camera_info is True
    assert result.has_orientation_metadata is True
    assert result.orientation == 6
    assert result.has_gps is False
    assert result.metadata_richness == 4


def test_embedded_color_profile_is_preserved_as_compact_evidence() -> None:
    payload = BytesIO()
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    scene().save(payload, format="PNG", icc_profile=profile)

    result = extract_visual_features(payload, "png")

    assert result is not None
    assert result.icc_profile_present is True
    assert result.metadata_richness == 1


@pytest.mark.parametrize("factor", [0.95, 1.05])
def test_mild_brightness_changes_remain_very_similar(factor: float) -> None:
    base = features(scene())
    changed = features(ImageEnhance.Brightness(scene()).enhance(factor))

    comparison = compare_visual_features(base, changed)

    assert comparison.similarity_percent >= 94
    assert comparison.structural_percent >= 98
    assert comparison.normalized_luminance_rmse <= 0.03
    assert comparison.normalized_luminance_ssim >= 0.99


def test_mild_color_change_remains_similar_but_is_not_pixel_identical() -> None:
    base_image = scene()
    red, green, blue = base_image.split()
    changed_image = Image.merge(
        "RGB",
        (
            red.point(lambda value: min(255, round(value * 1.06))),
            green,
            blue.point(lambda value: round(value * 0.94)),
        ),
    )
    base = features(base_image)
    changed = features(changed_image)

    comparison = compare_visual_features(base, changed)

    assert comparison.similarity_percent >= 90
    assert base.thumbnail_sha256 != changed.thumbnail_sha256


def test_resize_preserves_appearance_features() -> None:
    base = features(scene())
    resized = features(scene().resize((96, 64), Image.Resampling.LANCZOS))

    comparison = compare_visual_features(base, resized)

    assert comparison.similarity_percent >= 98
    assert comparison.aspect_ratio_difference == 0
    assert comparison.dimensions_equal is False


def test_unrelated_composition_scores_materially_lower() -> None:
    unrelated = Image.new("RGB", (192, 128), (230, 230, 230))
    draw = ImageDraw.Draw(unrelated)
    for offset in range(0, 192, 16):
        draw.rectangle((offset, 0, offset + 7, 127), fill=(20, 30, 180))

    comparison = compare_visual_features(features(scene()), features(unrelated))

    assert comparison.similarity_percent < 80
    assert comparison.normalized_luminance_rmse > 0.2
    assert comparison.normalized_luminance_ssim < 0.5


def test_corrupt_or_unsupported_input_has_no_visual_feature() -> None:
    assert extract_visual_features(BytesIO(b"not an image"), "png") is None
    assert extract_visual_features(BytesIO(b"plain bytes"), "unknown") is None

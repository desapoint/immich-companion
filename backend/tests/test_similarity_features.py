"""Regression corpus for compact exposure-tolerant visual features."""

from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageEnhance

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
    assert compare_visual_features(first, second).similarity_percent == 100


@pytest.mark.parametrize("factor", [0.95, 1.05])
def test_mild_brightness_changes_remain_very_similar(factor: float) -> None:
    base = features(scene())
    changed = features(ImageEnhance.Brightness(scene()).enhance(factor))

    comparison = compare_visual_features(base, changed)

    assert comparison.similarity_percent >= 94
    assert comparison.structural_percent >= 98


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

    assert compare_visual_features(base, resized).similarity_percent >= 98


def test_unrelated_composition_scores_materially_lower() -> None:
    unrelated = Image.new("RGB", (192, 128), (230, 230, 230))
    draw = ImageDraw.Draw(unrelated)
    for offset in range(0, 192, 16):
        draw.rectangle((offset, 0, offset + 7, 127), fill=(20, 30, 180))

    assert compare_visual_features(
        features(scene()), features(unrelated)
    ).similarity_percent < 80


def test_corrupt_or_unsupported_input_has_no_visual_feature() -> None:
    assert extract_visual_features(BytesIO(b"not an image"), "png") is None
    assert extract_visual_features(BytesIO(b"plain bytes"), "unknown") is None

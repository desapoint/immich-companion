"""Bounded, versioned visual features for later similarity discovery."""

from __future__ import annotations

import hashlib
import math
import warnings
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from companion.image_decode import SUPPORTED_FORMATS
from companion.integrity import DetectedFormat

SIMILARITY_MODEL_VERSION = "appearance-v1"
SIMILARITY_FEATURE_VERSION = 1
LUMINANCE_VECTOR_SIDE = 16
LUMINANCE_VECTOR_LENGTH = LUMINANCE_VECTOR_SIDE**2
COLOR_HISTOGRAM_BINS = 16
COLOR_HISTOGRAM_LENGTH = COLOR_HISTOGRAM_BINS * 3


@dataclass(frozen=True, slots=True)
class VisualFeatureResult:
    """Compact appearance evidence derived from one fully decoded image."""

    model_version: str
    feature_version: int
    width: int
    height: int
    luminance_vector: bytes
    perceptual_hash: str
    color_histogram: bytes
    thumbnail_sha256: str


@dataclass(frozen=True, slots=True)
class VisualSimilarityResult:
    """Explainable feature-space comparison; never exact-file proof."""

    similarity_percent: float
    structural_percent: float
    perceptual_percent: float
    color_percent: float


def _srgb_image(image: Image.Image) -> Image.Image:
    """Apply embedded ICC data when Pillow can convert it, then orient as RGB."""

    oriented = ImageOps.exif_transpose(image)
    icc_profile = oriented.info.get("icc_profile")
    if isinstance(icc_profile, bytes) and icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(BytesIO(icc_profile))
            destination_profile = ImageCms.createProfile("sRGB")
            return ImageCms.profileToProfile(
                oriented,
                source_profile,
                destination_profile,
                outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass
    return oriented.convert("RGB")


def _normalized_luminance(image: Image.Image) -> bytes:
    grayscale = ImageOps.grayscale(image).resize(
        (LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE),
        Image.Resampling.LANCZOS,
    )
    values = list(grayscale.get_flattened_data())
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    deviation = math.sqrt(variance)
    if deviation < 1e-6:
        return bytes([128] * LUMINANCE_VECTOR_LENGTH)
    return bytes(
        round((max(-3.0, min(3.0, (value - mean) / deviation)) + 3.0) / 6.0 * 255)
        for value in values
    )


def _difference_hash(image: Image.Image) -> str:
    grayscale = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(grayscale.get_flattened_data())
    value = 0
    for row in range(8):
        offset = row * 9
        for column in range(8):
            value = (value << 1) | int(
                pixels[offset + column] > pixels[offset + column + 1]
            )
    return f"{value:016x}"


def _color_histogram(image: Image.Image) -> bytes:
    sample = image.resize((LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE), Image.Resampling.LANCZOS)
    pixels = list(sample.get_flattened_data())
    channel_histograms = [[0] * COLOR_HISTOGRAM_BINS for _ in range(3)]
    for pixel in pixels:
        for channel, value in enumerate(pixel):
            channel_histograms[channel][min(value * COLOR_HISTOGRAM_BINS // 256, 15)] += 1
    scale = 255 / len(pixels)
    return bytes(
        round(count * scale)
        for histogram in channel_histograms
        for count in histogram
    )


def extract_visual_features(
    stream: BinaryIO,
    detected_format: DetectedFormat,
) -> VisualFeatureResult | None:
    """Decode one trusted spool and return fixed-size features, or no feature."""

    if detected_format not in SUPPORTED_FORMATS:
        return None
    try:
        stream.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(stream) as source:
                source.load()
                image = _srgb_image(source)
                width, height = image.size
                thumbnail = image.resize(
                    (LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE),
                    Image.Resampling.LANCZOS,
                )
                thumbnail_sha256 = hashlib.sha256(
                    thumbnail.tobytes(), usedforsecurity=False
                ).hexdigest()
                return VisualFeatureResult(
                    model_version=SIMILARITY_MODEL_VERSION,
                    feature_version=SIMILARITY_FEATURE_VERSION,
                    width=width,
                    height=height,
                    luminance_vector=_normalized_luminance(image),
                    perceptual_hash=_difference_hash(image),
                    color_histogram=_color_histogram(image),
                    thumbnail_sha256=thumbnail_sha256,
                )
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ):
        return None


def compare_visual_features(
    left: VisualFeatureResult,
    right: VisualFeatureResult,
) -> VisualSimilarityResult:
    """Compare compatible compact features with exposure-tolerant structure."""

    if (
        left.model_version != right.model_version
        or left.feature_version != right.feature_version
    ):
        raise ValueError("Visual feature versions are incompatible.")
    structural = 1 - sum(
        abs(a - b) for a, b in zip(left.luminance_vector, right.luminance_vector, strict=True)
    ) / (len(left.luminance_vector) * 255)
    hash_distance = (
        int(left.perceptual_hash, 16) ^ int(right.perceptual_hash, 16)
    ).bit_count()
    perceptual = 1 - hash_distance / 64
    color = sum(
        min(a, b) for a, b in zip(left.color_histogram, right.color_histogram, strict=True)
    ) / (3 * 255)
    combined = 0.65 * structural + 0.25 * perceptual + 0.10 * color
    return VisualSimilarityResult(
        similarity_percent=round(max(0.0, min(1.0, combined)) * 100, 2),
        structural_percent=round(structural * 100, 2),
        perceptual_percent=round(perceptual * 100, 2),
        color_percent=round(color * 100, 2),
    )

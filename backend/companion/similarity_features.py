"""Bounded, versioned visual features for later similarity discovery."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import struct
import warnings
from dataclasses import dataclass
from io import BytesIO
from time import perf_counter
from typing import BinaryIO

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from companion.image_decode import (
    MAX_DECODED_PIXELS,
    SUPPORTED_FORMATS,
    ImageDecodeResult,
)
from companion.integrity import DetectedFormat
from companion.preservation_features import PIXEL_NORMALIZATION_VERSION
from companion.raw_isolation import decode_raw_isolated
from companion.similarity_generation import SIMILARITY_EVIDENCE_CODE_GENERATION

SIMILARITY_MODEL_VERSION = "appearance-v1"
SIMILARITY_FEATURE_VERSION = 3
LUMINANCE_VECTOR_SIDE = 16
LUMINANCE_PLANE_LENGTH = LUMINANCE_VECTOR_SIDE**2
# Feature v3 stores normalized visible luminance followed by the raw alpha plane.
LUMINANCE_VECTOR_LENGTH = LUMINANCE_PLANE_LENGTH * 2
ALPHA_STRUCTURAL_PENALTY = 0.25
COLOR_HISTOGRAM_BINS = 16
COLOR_HISTOGRAM_LENGTH = COLOR_HISTOGRAM_BINS * 3
PIXEL_HASH_ROWS_PER_CHUNK = 64
SIMILARITY_CONFIG_FINGERPRINT = hashlib.sha256(
    json.dumps(
        {
            "model": SIMILARITY_MODEL_VERSION,
            "feature_version": SIMILARITY_FEATURE_VERSION,
            "evidence_code_generation": SIMILARITY_EVIDENCE_CODE_GENERATION,
            "pixel_normalization_version": PIXEL_NORMALIZATION_VERSION,
            "luminance_side": LUMINANCE_VECTOR_SIDE,
            "luminance_planes": ("premultiplied_srgb", "alpha"),
            "alpha_structural_penalty": ALPHA_STRUCTURAL_PENALTY,
            "histogram_bins": COLOR_HISTOGRAM_BINS,
            "histogram_weighting": "premultiplied-alpha-visible-mass-v1",
            "weights": {"structural": 0.65, "perceptual": 0.25, "color": 0.10},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode(),
    usedforsecurity=False,
).hexdigest()

logger = logging.getLogger("uvicorn.error")


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
    pixel_normalization_version: int
    pixel_sha256: str | None
    bit_depth: int
    channel_count: int
    has_alpha: bool
    color_space: str
    orientation: int | None
    icc_profile_present: bool
    has_exif: bool
    has_capture_time: bool
    has_camera_info: bool
    has_gps: bool
    has_orientation_metadata: bool
    metadata_richness: int


@dataclass(frozen=True, slots=True)
class VisualSimilarityResult:
    """Explainable feature-space comparison; never exact-file proof."""

    similarity_percent: float
    structural_percent: float
    perceptual_percent: float
    color_percent: float
    normalized_luminance_mae: float
    normalized_luminance_rmse: float
    normalized_luminance_ssim: float
    aspect_ratio_difference: float
    dimensions_equal: bool


def _normalized_luminance_evidence(
    left: bytes,
    right: bytes,
) -> tuple[float, float, float]:
    """Return normalized MAE/RMSE and standard global SSIM for compact samples."""

    if len(left) != len(right) or not left:
        raise ValueError("Luminance samples must have the same non-zero length.")
    count = len(left)
    differences = [float(a) - float(b) for a, b in zip(left, right, strict=True)]
    mae = sum(abs(value) for value in differences) / count / 255
    rmse = math.sqrt(sum(value * value for value in differences) / count) / 255

    left_mean = sum(left) / count
    right_mean = sum(right) / count
    left_variance = sum((value - left_mean) ** 2 for value in left) / count
    right_variance = sum((value - right_mean) ** 2 for value in right) / count
    covariance = sum(
        (a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True)
    ) / count
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    numerator = (2 * left_mean * right_mean + c1) * (2 * covariance + c2)
    denominator = (left_mean**2 + right_mean**2 + c1) * (
        left_variance + right_variance + c2
    )
    ssim = numerator / denominator if denominator else 1.0
    return (
        round(max(0.0, min(1.0, mae)), 6),
        round(max(0.0, min(1.0, rmse)), 6),
        round(max(-1.0, min(1.0, ssim)), 6),
    )


def _srgb_image(image: Image.Image) -> Image.Image:
    """Apply orientation/profile while retaining meaningful alpha."""

    oriented = ImageOps.exif_transpose(image)
    has_alpha = "A" in oriented.getbands() or "transparency" in oriented.info
    alpha = oriented.convert("RGBA").getchannel("A") if has_alpha else None
    rgb = oriented.convert("RGB")
    icc_profile = oriented.info.get("icc_profile")
    if isinstance(icc_profile, bytes) and icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(BytesIO(icc_profile))
            destination_profile = ImageCms.createProfile("sRGB")
            rgb = ImageCms.profileToProfile(
                oriented.convert("RGB") if alpha is not None else oriented,
                source_profile,
                destination_profile,
                outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass
    if alpha is None:
        return rgb
    return Image.merge("RGBA", (*rgb.split(), alpha))


def _alpha_channel(image: Image.Image) -> Image.Image:
    """Return an explicit alpha plane, treating non-alpha images as fully opaque."""

    if "A" in image.getbands() or "transparency" in image.info:
        return image.convert("RGBA").getchannel("A")
    return Image.new("L", image.size, 255)


def _visible_rgb(image: Image.Image) -> Image.Image:
    """Premultiply RGB by alpha so invisible colors cannot influence appearance."""

    rgb = image.convert("RGB")
    if "A" not in image.getbands() and "transparency" not in image.info:
        return rgb
    alpha = image.convert("RGBA").getchannel("A")
    return Image.composite(rgb, Image.new("RGB", image.size, (0, 0, 0)), alpha)


def _appearance_rgba(image: Image.Image) -> Image.Image:
    """Canonical visible color plus alpha used by appearance-only evidence."""

    visible = _visible_rgb(image)
    return Image.merge("RGBA", (*visible.split(), _alpha_channel(image)))


def _normalized_luminance(image: Image.Image) -> bytes:
    grayscale = ImageOps.grayscale(_visible_rgb(image)).resize(
        (LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE),
        Image.Resampling.LANCZOS,
    )
    values = list(grayscale.get_flattened_data())
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    deviation = math.sqrt(variance)
    if deviation < 1e-6:
        return bytes([128] * LUMINANCE_PLANE_LENGTH)
    return bytes(
        round((max(-3.0, min(3.0, (value - mean) / deviation)) + 3.0) / 6.0 * 255)
        for value in values
    )


def _alpha_vector(image: Image.Image) -> bytes:
    alpha = _alpha_channel(image).resize(
        (LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE),
        Image.Resampling.LANCZOS,
    )
    return bytes(alpha.get_flattened_data())


def _appearance_luminance_vector(image: Image.Image) -> bytes:
    return _normalized_luminance(image) + _alpha_vector(image)


def _difference_hash(image: Image.Image) -> str:
    grayscale = ImageOps.grayscale(_visible_rgb(image)).resize(
        (9, 8), Image.Resampling.LANCZOS
    )
    pixels = list(grayscale.get_flattened_data())
    value = 0
    for row in range(8):
        offset = row * 9
        for column in range(8):
            value = (value << 1) | int(pixels[offset + column] > pixels[offset + column + 1])
    return f"{value:016x}"


def _color_histogram(image: Image.Image) -> bytes:
    alpha = _alpha_channel(image)
    if alpha.getextrema() == (255, 255):
        # Preserve the v2/v3 opaque-image histogram byte-for-byte.
        sample = _visible_rgb(image).resize(
            (LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE),
            Image.Resampling.LANCZOS,
        )
        pixels = list(sample.get_flattened_data())
        channel_histograms = [[0] * COLOR_HISTOGRAM_BINS for _ in range(3)]
        for pixel in pixels:
            for channel, value in enumerate(pixel):
                channel_histograms[channel][
                    min(value * COLOR_HISTOGRAM_BINS // 256, 15)
                ] += 1
        scale = 255 / len(pixels)
        return bytes(
            round(count * scale)
            for histogram in channel_histograms
            for count in histogram
        )

    # Transparent color should contribute only in proportion to its visibility.
    # The remainder of each pixel's mass is assigned to the neutral black bin,
    # so hidden RGB cannot act like fully opaque color evidence. The sample is
    # already premultiplied, which also prevents invisible edge color from
    # bleeding into neighboring bins during the bounded resize.
    sample = _appearance_rgba(image).resize(
        (LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE),
        Image.Resampling.LANCZOS,
    )
    pixels = list(sample.get_flattened_data())
    channel_histograms = [[0.0] * COLOR_HISTOGRAM_BINS for _ in range(3)]
    for red, green, blue, alpha_value in pixels:
        visible_weight = alpha_value / 255
        transparent_weight = 1 - visible_weight
        for channel, value in enumerate((red, green, blue)):
            histogram = channel_histograms[channel]
            histogram[0] += transparent_weight
            histogram[min(value * COLOR_HISTOGRAM_BINS // 256, 15)] += visible_weight

    scale = 255 / len(pixels)
    quantized: list[int] = []
    for histogram in channel_histograms:
        scaled = [count * scale for count in histogram]
        values = [math.floor(value) for value in scaled]
        remainder = 255 - sum(values)
        fractions = sorted(
            range(COLOR_HISTOGRAM_BINS),
            key=lambda index: scaled[index] - values[index],
            reverse=True,
        )
        for index in fractions[:remainder]:
            values[index] += 1
        quantized.extend(values)
    return bytes(quantized)


def _bit_depth(image: Image.Image) -> int:
    declared = image.info.get("bits")
    if isinstance(declared, int) and declared > 0:
        return declared
    if image.mode == "1":
        return 1
    if image.mode.startswith("I;16"):
        return 16
    if image.mode in {"I", "F"}:
        return 32
    return 8


def _pixel_sha256(image: Image.Image) -> str:
    canonical = image.convert("RGBA")
    digest = hashlib.sha256(usedforsecurity=False)
    digest.update(struct.pack(">II", *canonical.size))
    width, height = canonical.size
    for top in range(0, height, PIXEL_HASH_ROWS_PER_CHUNK):
        bottom = min(height, top + PIXEL_HASH_ROWS_PER_CHUNK)
        digest.update(canonical.crop((0, top, width, bottom)).tobytes())
    return digest.hexdigest()


def _build_feature(
    image: Image.Image,
    *,
    bit_depth: int,
    channel_count: int,
    has_alpha: bool,
    color_space: str,
    orientation: int | None,
    icc_profile_present: bool,
    has_exif: bool,
    has_capture_time: bool,
    has_camera_info: bool,
    has_gps: bool,
    has_orientation_metadata: bool,
    include_pixel_hash: bool = True,
    timings: dict[str, int] | None = None,
) -> VisualFeatureResult:
    normalized = _srgb_image(image)
    width, height = normalized.size
    thumbnail = _appearance_rgba(normalized).resize(
        (LUMINANCE_VECTOR_SIDE, LUMINANCE_VECTOR_SIDE),
        Image.Resampling.LANCZOS,
    )
    thumbnail_sha256 = hashlib.sha256(
        thumbnail.tobytes(), usedforsecurity=False
    ).hexdigest()
    metadata_richness = sum(
        (
            has_exif,
            has_capture_time,
            has_camera_info,
            has_gps,
            has_orientation_metadata,
            icc_profile_present,
        )
    )
    pixel_hash = None
    if include_pixel_hash:
        started = perf_counter()
        pixel_hash = _pixel_sha256(normalized)
        if timings is not None:
            timings["normalized_pixel_hash_milliseconds"] = round(
                (perf_counter() - started) * 1000
            )
    return VisualFeatureResult(
        model_version=SIMILARITY_MODEL_VERSION,
        feature_version=SIMILARITY_FEATURE_VERSION,
        width=width,
        height=height,
        luminance_vector=_appearance_luminance_vector(normalized),
        perceptual_hash=_difference_hash(normalized),
        color_histogram=_color_histogram(normalized),
        thumbnail_sha256=thumbnail_sha256,
        pixel_normalization_version=PIXEL_NORMALIZATION_VERSION,
        pixel_sha256=pixel_hash,
        bit_depth=bit_depth,
        channel_count=channel_count,
        has_alpha=has_alpha,
        color_space=color_space,
        orientation=orientation,
        icc_profile_present=icc_profile_present,
        has_exif=has_exif,
        has_capture_time=has_capture_time,
        has_camera_info=has_camera_info,
        has_gps=has_gps,
        has_orientation_metadata=has_orientation_metadata,
        metadata_richness=metadata_richness,
    )


def _extract_raw_visual_features(
    stream: BinaryIO, *, include_pixel_hash: bool = True
) -> tuple[ImageDecodeResult, VisualFeatureResult | None]:
    """Render RAW/DNG through a fault-isolated LibRaw worker."""

    result = decode_raw_isolated(
        stream,
        max_decoded_pixels=MAX_DECODED_PIXELS,
        extract_features=True,
        include_pixel_hash=include_pixel_hash,
    )
    decoded = ImageDecodeResult(
        supported=True,
        valid=result.valid,
        width=result.width,
        height=result.height,
        issue=result.issue,
    )
    if result.feature is None:
        return decoded, None
    try:
        return decoded, VisualFeatureResult(**result.feature)
    except TypeError as error:
        logger.warning(
            "RAW similarity worker returned invalid feature evidence: reason=%s",
            error,
        )
        return ImageDecodeResult(
            supported=True,
            valid=None,
            width=result.width,
            height=result.height,
            issue="image_decode_raw_worker_failed",
        ), None


def _feature_from_loaded_image(
    source: Image.Image, *, include_pixel_hash: bool,
    timings: dict[str, int] | None = None,
) -> VisualFeatureResult:
    exif = source.getexif()
    orientation_value = exif.get(274)
    orientation = orientation_value if isinstance(orientation_value, int) else None
    return _build_feature(
        source,
        bit_depth=_bit_depth(source),
        channel_count=len(source.getbands()),
        has_alpha="A" in source.getbands() or "transparency" in source.info,
        color_space=source.mode,
        orientation=orientation,
        icc_profile_present=bool(source.info.get("icc_profile")),
        has_exif=bool(exif),
        has_capture_time=any(exif.get(tag) for tag in (306, 36867, 36868)),
        has_camera_info=bool(exif.get(271) or exif.get(272)),
        has_gps=bool(exif.get(34853)),
        has_orientation_metadata=orientation is not None,
        include_pixel_hash=include_pixel_hash,
        timings=timings,
    )


def decode_and_extract_features(
    stream: BinaryIO,
    detected_format: DetectedFormat,
    *,
    include_pixel_hash: bool = True,
    timings: dict[str, int] | None = None,
) -> tuple[ImageDecodeResult, VisualFeatureResult | None]:
    """Validate and extract from the same decoded original image."""

    if detected_format not in SUPPORTED_FORMATS:
        return ImageDecodeResult(supported=False, valid=None), None
    try:
        decode_started = perf_counter()
        stream.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(stream) as source:
                source.load()
                width, height = source.size
                try:
                    orientation = source.getexif().get(274)
                except (AttributeError, OSError, ValueError):
                    orientation = None
                if orientation in {5, 6, 7, 8}:
                    width, height = height, width
                decoded = ImageDecodeResult(
                    supported=True, valid=True, width=width, height=height
                )
                if timings is not None:
                    timings["decode_milliseconds"] = round(
                        (perf_counter() - decode_started) * 1000
                    )
                try:
                    feature_started = perf_counter()
                    feature = _feature_from_loaded_image(
                        source, include_pixel_hash=include_pixel_hash, timings=timings
                    )
                    if timings is not None:
                        timings["feature_extraction_milliseconds"] = round(
                            (perf_counter() - feature_started) * 1000
                        )
                except (OSError, SyntaxError, ValueError) as error:
                    logger.warning(
                        "Similarity feature extraction failed after decode: "
                        "format=%s error_type=%s reason=%s",
                        detected_format, type(error).__name__, error,
                    )
                    feature = None
                return decoded, feature
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        logger.warning(
            "Similarity feature extraction exceeded image safety limit: %s",
            error,
        )
        return ImageDecodeResult(
            supported=True, valid=None, issue="image_decode_limit_exceeded"
        ), None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        if detected_format == "tiff":
            raw_started = perf_counter()
            decoded, feature = _extract_raw_visual_features(
                stream, include_pixel_hash=include_pixel_hash
            )
            if timings is not None:
                timings["decode_milliseconds"] = round(
                    (perf_counter() - raw_started) * 1000
                )
            return decoded, feature
        logger.warning(
            "Similarity feature extraction failed: format=%s error_type=%s reason=%s",
            detected_format,
            type(error).__name__,
            error,
        )
        return ImageDecodeResult(
            supported=True, valid=False, issue="image_decode_failed"
        ), None


def extract_visual_features(
    stream: BinaryIO,
    detected_format: DetectedFormat,
    *,
    include_pixel_hash: bool = True,
    timings: dict[str, int] | None = None,
) -> VisualFeatureResult | None:
    """Compatibility wrapper for callers that only need visual evidence."""

    _, feature = decode_and_extract_features(
        stream, detected_format, include_pixel_hash=include_pixel_hash, timings=timings
    )
    return feature


def _luminance_and_alpha(
    feature: VisualFeatureResult,
) -> tuple[bytes, bytes | None]:
    """Split v3 appearance evidence while retaining comparison of older generations."""

    if feature.feature_version >= 3:
        if len(feature.luminance_vector) != LUMINANCE_VECTOR_LENGTH:
            raise ValueError("Visual luminance vector dimensions are incompatible.")
        return (
            feature.luminance_vector[:LUMINANCE_PLANE_LENGTH],
            feature.luminance_vector[LUMINANCE_PLANE_LENGTH:],
        )
    if not feature.luminance_vector:
        raise ValueError("Visual luminance vector dimensions are incompatible.")
    return feature.luminance_vector, None


def compare_visual_features(
    left: VisualFeatureResult,
    right: VisualFeatureResult,
) -> VisualSimilarityResult:
    """Compare compatible compact features with exposure-tolerant structure."""

    if left.model_version != right.model_version or left.feature_version != right.feature_version:
        raise ValueError("Visual feature versions are incompatible.")
    left_luminance, left_alpha = _luminance_and_alpha(left)
    right_luminance, right_alpha = _luminance_and_alpha(right)
    if len(left_luminance) != len(right_luminance):
        raise ValueError("Visual luminance vector dimensions are incompatible.")
    luminance_mae, luminance_rmse, luminance_ssim = _normalized_luminance_evidence(
        left_luminance,
        right_luminance,
    )
    structural = 1 - sum(
        abs(a - b) for a, b in zip(left_luminance, right_luminance, strict=True)
    ) / (len(left_luminance) * 255)
    if left_alpha is not None or right_alpha is not None:
        if left_alpha is None or right_alpha is None or len(left_alpha) != len(right_alpha):
            raise ValueError("Visual alpha vector dimensions are incompatible.")
        alpha_difference = sum(
            abs(a - b) for a, b in zip(left_alpha, right_alpha, strict=True)
        ) / (len(left_alpha) * 255)
        structural = max(0.0, structural - ALPHA_STRUCTURAL_PENALTY * alpha_difference)
    hash_distance = (int(left.perceptual_hash, 16) ^ int(right.perceptual_hash, 16)).bit_count()
    perceptual = 1 - hash_distance / 64
    color = min(
        1.0,
        sum(
            min(a, b) for a, b in zip(left.color_histogram, right.color_histogram, strict=True)
        )
        / (3 * 255),
    )
    left_aspect = left.width / left.height
    right_aspect = right.width / right.height
    aspect_ratio_difference = abs(left_aspect - right_aspect) / max(left_aspect, right_aspect)
    combined = 0.65 * structural + 0.25 * perceptual + 0.10 * color
    return VisualSimilarityResult(
        similarity_percent=round(max(0.0, min(1.0, combined)) * 100, 2),
        structural_percent=round(structural * 100, 2),
        perceptual_percent=round(perceptual * 100, 2),
        color_percent=round(color * 100, 2),
        normalized_luminance_mae=luminance_mae,
        normalized_luminance_rmse=luminance_rmse,
        normalized_luminance_ssim=luminance_ssim,
        aspect_ratio_difference=round(aspect_ratio_difference, 6),
        dimensions_equal=(left.width, left.height) == (right.width, right.height),
    )

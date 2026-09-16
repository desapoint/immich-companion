"""Bounded, versioned local-detail evidence for shortlisted visual pairs."""

from __future__ import annotations

import math
import warnings
import zlib
from dataclasses import dataclass
from typing import BinaryIO

import numpy as np
import rawpy
from PIL import Image, ImageFilter, UnidentifiedImageError

from companion.image_decode import MAX_DECODED_PIXELS
from companion.integrity import DetectedFormat
from companion.similarity_features import _srgb_image

DETAIL_FEATURE_VERSION = 2
DETAIL_SAMPLE_SIDE = 512
DETAIL_SAMPLE_BYTES = DETAIL_SAMPLE_SIDE * DETAIL_SAMPLE_SIDE * 3
DETAIL_TILE_SIDE = 16
DETAIL_SCALES = ((512, 0.6), (256, 0.3), (128, 0.1))
DETAIL_GRID_SIDE = DETAIL_SAMPLE_SIDE // DETAIL_TILE_SIDE
# A region tile must contain enough changed pixels to look like real interior
# content, rather than antialiasing/compression changes scattered around edges.
DETAIL_REGION_TILE_THRESHOLD = 0.20
# Ignore isolated sub-tile specks that do not cover even 0.1% of the image.
DETAIL_REGION_MIN_FRACTION = 0.001


@dataclass(frozen=True, slots=True)
class DetailFeature:
    width: int
    height: int
    sample: bytes


@dataclass(frozen=True, slots=True)
class DetailComparison:
    similarity_percent: float
    changed_percent: float


@dataclass(frozen=True, slots=True)
class DetailDiagnostics:
    """Read-only explanation of the local evidence used by detail comparison."""

    changed_percent: float
    localized_changed_percent: float
    coherent_changed_percent: float
    largest_changed_region_percent: float
    substantial_region_count: int
    rows: int
    columns: int
    tile_changed_percents: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class _DetailAnalysis:
    changed_fraction: float
    weighted_changed: float
    weighted_difference: float
    local_fraction: float
    coherent_changed_fraction: float
    largest_region_fraction: float
    substantial_region_count: int
    tiles: np.ndarray


def _sample(image: Image.Image) -> DetailFeature:
    normalized = _srgb_image(image)
    width, height = normalized.size
    reduced = normalized.convert("RGB").resize(
        (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), Image.Resampling.LANCZOS
    )
    return DetailFeature(width, height, zlib.compress(reduced.tobytes(), level=3))


def extract_detail_feature(
    stream: BinaryIO, detected_format: DetectedFormat
) -> DetailFeature | None:
    """Decode one original or full-size transcode, without exact-pixel hashing."""

    try:
        stream.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(stream) as image:
                if image.width * image.height > MAX_DECODED_PIXELS:
                    return None
                image.load()
                return _sample(image)
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        if detected_format != "tiff":
            return None
    try:
        stream.seek(0)
        with rawpy.imread(stream) as raw:
            if raw.sizes.width * raw.sizes.height > MAX_DECODED_PIXELS:
                return None
            pixels = raw.postprocess(
                use_camera_wb=True, no_auto_bright=True, output_bps=8
            )
        return _sample(Image.fromarray(pixels, "RGB"))
    except (rawpy.LibRawError, OSError, ValueError):
        return None


def _detail_images(
    left: DetailFeature, right: DetailFeature
) -> tuple[Image.Image, Image.Image]:
    if left.width <= 0 or left.height <= 0 or right.width <= 0 or right.height <= 0:
        raise ValueError("Detail features require positive dimensions")
    left_bytes = _decompress_sample(left.sample)
    right_bytes = _decompress_sample(right.sample)
    if len(left_bytes) != DETAIL_SAMPLE_BYTES or len(right_bytes) != DETAIL_SAMPLE_BYTES:
        raise ValueError("Detail sample dimensions are incompatible")
    # A tiny blur reduces JPEG/HEIC ringing while retaining clothing and face details.
    left_image = Image.frombytes("RGB", (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), left_bytes)
    right_image = Image.frombytes("RGB", (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), right_bytes)
    return (
        left_image.filter(ImageFilter.GaussianBlur(0.5)),
        right_image.filter(ImageFilter.GaussianBlur(0.5)),
    )


def _coherent_region_metrics(tiles: np.ndarray) -> tuple[float, float, int]:
    """Measure filled, connected tile regions while ignoring sparse edge noise."""

    if tiles.shape != (DETAIL_GRID_SIDE, DETAIL_GRID_SIDE):
        raise ValueError("Detail tile grid dimensions are incompatible")
    active = tiles >= DETAIL_REGION_TILE_THRESHOLD
    visited = np.zeros(active.shape, dtype=np.bool_)
    component_fractions: list[float] = []
    rows, columns = active.shape

    for row in range(rows):
        for column in range(columns):
            if not active[row, column] or visited[row, column]:
                continue
            visited[row, column] = True
            pending = [(row, column)]
            changed_weight = 0.0
            while pending:
                current_row, current_column = pending.pop()
                changed_weight += float(tiles[current_row, current_column])
                for row_delta in (-1, 0, 1):
                    for column_delta in (-1, 0, 1):
                        if row_delta == 0 and column_delta == 0:
                            continue
                        next_row = current_row + row_delta
                        next_column = current_column + column_delta
                        if (
                            0 <= next_row < rows
                            and 0 <= next_column < columns
                            and active[next_row, next_column]
                            and not visited[next_row, next_column]
                        ):
                            visited[next_row, next_column] = True
                            pending.append((next_row, next_column))
            fraction = changed_weight / tiles.size
            if fraction >= DETAIL_REGION_MIN_FRACTION:
                component_fractions.append(fraction)

    return (
        sum(component_fractions),
        max(component_fractions, default=0.0),
        len(component_fractions),
    )


def _analyze_detail_features(left: DetailFeature, right: DetailFeature) -> _DetailAnalysis:
    """Run the shared detail math once so scoring and diagnostics cannot drift."""

    left_image, right_image = _detail_images(left, right)
    changed_fraction = 0.0
    weighted_changed = 0.0
    weighted_difference = 0.0
    local_fraction = 0.0
    tiles = np.zeros((DETAIL_GRID_SIDE, DETAIL_GRID_SIDE), dtype=np.float64)
    for side, weight in DETAIL_SCALES:
        if side == DETAIL_SAMPLE_SIDE:
            left_scale, right_scale = left_image, right_image
        else:
            left_scale = left_image.resize((side, side), Image.Resampling.BOX)
            right_scale = right_image.resize((side, side), Image.Resampling.BOX)
        left_pixels = np.asarray(left_scale, dtype=np.int16)
        right_pixels = np.asarray(right_scale, dtype=np.int16)
        differences = np.abs(left_pixels - right_pixels)
        mean_difference = np.mean(differences, axis=2)
        changed = mean_difference >= 24
        fraction = float(np.mean(changed))
        weighted_changed += weight * fraction
        weighted_difference += weight * float(np.mean(mean_difference)) / 255
        if side == DETAIL_SAMPLE_SIDE:
            changed_fraction = fraction
            tiles = changed.reshape(
                side // DETAIL_TILE_SIDE,
                DETAIL_TILE_SIDE,
                side // DETAIL_TILE_SIDE,
                DETAIL_TILE_SIDE,
            ).mean(axis=(1, 3))
            local_fraction = float(np.mean(np.sort(tiles.ravel())[-4:]))
    coherent_changed_fraction, largest_region_fraction, substantial_region_count = (
        _coherent_region_metrics(tiles)
    )
    return _DetailAnalysis(
        changed_fraction=changed_fraction,
        weighted_changed=weighted_changed,
        weighted_difference=weighted_difference,
        local_fraction=local_fraction,
        coherent_changed_fraction=coherent_changed_fraction,
        largest_region_fraction=largest_region_fraction,
        substantial_region_count=substantial_region_count,
        tiles=tiles,
    )


def compare_detail_features(left: DetailFeature, right: DetailFeature) -> DetailComparison:
    """Score bounded multi-scale differences without claiming pixel identity."""

    analysis = _analyze_detail_features(left, right)
    # Broad-area and peak-local terms preserve the previous behavior. The
    # coherent-region term additionally distinguishes filled semantic edits
    # from sparse resize/compression/antialiasing noise. sqrt() intentionally
    # gives a small coherent edit more weight than the same changed area
    # distributed as isolated pixels, while remaining continuous rather than
    # introducing a hard "region changed => mismatch" rule.
    coherent_penalty = (
        24 * math.sqrt(analysis.largest_region_fraction)
        + 10 * analysis.coherent_changed_fraction
    )
    similarity = (
        100
        - 30 * analysis.weighted_changed
        - 2.6 * analysis.local_fraction
        - 6 * analysis.weighted_difference
        - coherent_penalty
    )
    return DetailComparison(
        similarity_percent=round(max(0.0, min(100.0, similarity)), 2),
        changed_percent=round(analysis.changed_fraction * 100, 2),
    )


def detail_diagnostics(left: DetailFeature, right: DetailFeature) -> DetailDiagnostics:
    """Expose the validator's local changed-pixel grid without changing its score."""

    analysis = _analyze_detail_features(left, right)
    tile_changed_percents = tuple(
        tuple(round(float(value) * 100, 2) for value in row)
        for row in analysis.tiles
    )
    return DetailDiagnostics(
        changed_percent=round(analysis.changed_fraction * 100, 2),
        localized_changed_percent=round(analysis.local_fraction * 100, 2),
        coherent_changed_percent=round(analysis.coherent_changed_fraction * 100, 2),
        largest_changed_region_percent=round(analysis.largest_region_fraction * 100, 2),
        substantial_region_count=analysis.substantial_region_count,
        rows=DETAIL_GRID_SIDE,
        columns=DETAIL_GRID_SIDE,
        tile_changed_percents=tile_changed_percents,
    )


def _decompress_sample(sample: bytes) -> bytes:
    """Reject incompatible or oversized persisted samples before allocating them."""

    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(sample, DETAIL_SAMPLE_BYTES + 1)
        if len(pixels) != DETAIL_SAMPLE_BYTES or not decoder.eof or decoder.unused_data:
            raise ValueError("Detail sample dimensions are incompatible")
        return pixels
    except zlib.error as exc:
        raise ValueError("Detail sample dimensions are incompatible") from exc

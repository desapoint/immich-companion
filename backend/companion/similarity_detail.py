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
from companion.similarity_features import _appearance_rgba, _srgb_image

DETAIL_FEATURE_VERSION = 4
DETAIL_SAMPLE_SIDE = 512
DETAIL_SAMPLE_BYTES = DETAIL_SAMPLE_SIDE * DETAIL_SAMPLE_SIDE * 4
DETAIL_TILE_SIDE = 16
DETAIL_SCALES = ((512, 0.6), (256, 0.3), (128, 0.1))
DETAIL_GRID_SIDE = DETAIL_SAMPLE_SIDE // DETAIL_TILE_SIDE
# Alpha is compared separately from premultiplied color so changing visibility
# remains meaningful even when the visible color itself is black.
DETAIL_ALPHA_DIFFERENCE_WEIGHT = 0.25
# A region tile must contain enough changed pixels to look like real interior
# content, rather than antialiasing/compression changes scattered around edges.
DETAIL_REGION_TILE_THRESHOLD = 0.20
# Ignore isolated sub-tile specks that do not cover even 0.1% of the image.
DETAIL_REGION_MIN_FRACTION = 0.001
# Estimate only a modest global frame translation. This is intentionally more
# conservative than general image registration: it compensates handheld/burst
# framing drift without allowing arbitrary warps to manufacture a match.
DETAIL_ALIGNMENT_SIDE = 128
DETAIL_ALIGNMENT_MAX_SHIFT_FRACTION = 0.10
DETAIL_ALIGNMENT_MIN_IMPROVEMENT = 0.08
DETAIL_ALIGNMENT_OVERLAP_PENALTY = 0.25

# Detail similarity is coverage-first: unchanged aligned area should dominate the
# score. One localized semantic change (clothing, face, one object) is therefore
# intentionally cheaper than the same total changed area split across several
# distant zones.
DETAIL_CHANGED_AREA_PENALTY = 25.0
DETAIL_DIFFERENCE_MAGNITUDE_PENALTY = 12.0
DETAIL_EXTRA_ZONE_PENALTY = 0.9
DETAIL_EXTRA_ZONE_CAP = 5
DETAIL_SPREAD_PENALTY = 4.0
DETAIL_SPREAD_FULL_WEIGHT_CHANGED_FRACTION = 0.05


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
    """Read-only explanation of raw viewer evidence plus aligned scoring evidence."""

    changed_percent: float
    localized_changed_percent: float
    coherent_changed_percent: float
    largest_changed_region_percent: float
    substantial_region_count: int
    aligned_changed_percent: float
    alignment_applied: bool
    alignment_shift_percent: float
    alignment_overlap_percent: float
    rows: int
    columns: int
    tile_changed_percents: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class _DetailAlignment:
    shift_x: int = 0
    shift_y: int = 0
    overlap_fraction: float = 1.0
    applied: bool = False


@dataclass(frozen=True, slots=True)
class _DetailAnalysis:
    changed_fraction: float
    weighted_changed: float
    weighted_difference: float
    local_fraction: float
    coherent_changed_fraction: float
    largest_region_fraction: float
    substantial_region_count: int
    spread_fraction: float
    tiles: np.ndarray


def _sample(image: Image.Image) -> DetailFeature:
    normalized = _srgb_image(image)
    width, height = normalized.size
    # Premultiply before resizing so transparent hidden RGB cannot bleed into
    # neighboring visible pixels during resampling. Preserve alpha separately.
    reduced = _appearance_rgba(normalized).resize(
        (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), Image.Resampling.LANCZOS
    )
    return DetailFeature(width, height, zlib.compress(reduced.tobytes(), level=3))


def extract_detail_feature_from_image(image: Image.Image) -> DetailFeature | None:
    """Build localized-detail evidence from already-decoded normalized pixels."""

    if image.width * image.height > MAX_DECODED_PIXELS:
        return None
    try:
        return _sample(image)
    except (OSError, SyntaxError, ValueError):
        return None


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
    # The stored RGB channels are premultiplied, so blurring RGBA keeps transparent
    # edge colors from being promoted into fully visible color evidence.
    left_image = Image.frombytes("RGBA", (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), left_bytes)
    right_image = Image.frombytes("RGBA", (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), right_bytes)
    return (
        left_image.filter(ImageFilter.GaussianBlur(0.5)),
        right_image.filter(ImageFilter.GaussianBlur(0.5)),
    )


def _coherent_region_metrics(tiles: np.ndarray) -> tuple[float, float, int, float]:
    """Measure substantial changed zones and how widely those zones are distributed."""

    if tiles.shape != (DETAIL_GRID_SIDE, DETAIL_GRID_SIDE):
        raise ValueError("Detail tile grid dimensions are incompatible")
    active = tiles >= DETAIL_REGION_TILE_THRESHOLD
    visited = np.zeros(active.shape, dtype=np.bool_)
    component_fractions: list[float] = []
    substantial_tiles: list[tuple[int, int]] = []
    rows, columns = active.shape

    for row in range(rows):
        for column in range(columns):
            if not active[row, column] or visited[row, column]:
                continue
            visited[row, column] = True
            pending = [(row, column)]
            component_tiles: list[tuple[int, int]] = []
            changed_weight = 0.0
            while pending:
                current_row, current_column = pending.pop()
                component_tiles.append((current_row, current_column))
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
                substantial_tiles.extend(component_tiles)

    spread_fraction = 0.0
    if substantial_tiles:
        changed_rows = [row for row, _ in substantial_tiles]
        changed_columns = [column for _, column in substantial_tiles]
        bounding_fraction = (
            (max(changed_rows) - min(changed_rows) + 1)
            * (max(changed_columns) - min(changed_columns) + 1)
            / tiles.size
        )
        occupied_fraction = len(set(substantial_tiles)) / tiles.size
        # A compact region roughly fills its own bounding box and gets almost
        # no spread penalty. Several distant zones enlarge that box without
        # increasing changed coverage by the same amount.
        spread_fraction = max(0.0, bounding_fraction - occupied_fraction)

    return (
        sum(component_fractions),
        max(component_fractions, default=0.0),
        len(component_fractions),
        spread_fraction,
    )


def _alignment_plane(image: Image.Image) -> np.ndarray:
    """Return exposure-normalized luminance for conservative shift estimation."""

    reduced = image.convert("RGB").resize(
        (DETAIL_ALIGNMENT_SIDE, DETAIL_ALIGNMENT_SIDE),
        Image.Resampling.BOX,
    )
    pixels = np.asarray(reduced, dtype=np.float32)
    luminance = (
        pixels[:, :, 0] * 0.2126
        + pixels[:, :, 1] * 0.7152
        + pixels[:, :, 2] * 0.0722
    )
    deviation = float(np.std(luminance))
    if deviation < 1e-6:
        return luminance - float(np.mean(luminance))
    return (luminance - float(np.mean(luminance))) / deviation


def _translation_overlap(
    left: np.ndarray,
    right: np.ndarray,
    shift_x: int,
    shift_y: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return overlapping planes after translating right into left coordinates."""

    height, width = left.shape[:2]
    left_x0, left_x1 = max(0, shift_x), min(width, width + shift_x)
    right_x0, right_x1 = max(0, -shift_x), min(width, width - shift_x)
    left_y0, left_y1 = max(0, shift_y), min(height, height + shift_y)
    right_y0, right_y1 = max(0, -shift_y), min(height, height - shift_y)
    left_crop = left[left_y0:left_y1, left_x0:left_x1]
    right_crop = right[right_y0:right_y1, right_x0:right_x1]
    overlap = (left_crop.shape[0] * left_crop.shape[1]) / (height * width)
    return left_crop, right_crop, overlap


def _translation_error(
    left: np.ndarray,
    right: np.ndarray,
    shift_x: int,
    shift_y: int,
) -> tuple[float, float]:
    left_crop, right_crop, overlap = _translation_overlap(
        left, right, shift_x, shift_y
    )
    if left_crop.size == 0:
        return float("inf"), 0.0
    error = float(np.mean(np.abs(left_crop - right_crop)))
    return error + DETAIL_ALIGNMENT_OVERLAP_PENALTY * (1 - overlap), overlap


def _estimate_alignment(
    left_image: Image.Image,
    right_image: Image.Image,
) -> _DetailAlignment:
    """Find a small global translation only when it materially improves overlap."""

    left = _alignment_plane(left_image)
    right = _alignment_plane(right_image)
    raw_error, _ = _translation_error(left, right, 0, 0)
    if raw_error < 1e-6:
        return _DetailAlignment()

    limit = max(1, round(DETAIL_ALIGNMENT_SIDE * DETAIL_ALIGNMENT_MAX_SHIFT_FRACTION))
    best_error = raw_error
    best_x = 0
    best_y = 0
    # Coarse-to-fine search keeps pair validation bounded while remaining robust
    # to small handheld translations and slight subject movement.
    for shift_y in range(-limit, limit + 1, 2):
        for shift_x in range(-limit, limit + 1, 2):
            error, _ = _translation_error(left, right, shift_x, shift_y)
            if error < best_error:
                best_error, best_x, best_y = error, shift_x, shift_y
    coarse_x, coarse_y = best_x, best_y
    for shift_y in range(max(-limit, coarse_y - 2), min(limit, coarse_y + 2) + 1):
        for shift_x in range(max(-limit, coarse_x - 2), min(limit, coarse_x + 2) + 1):
            error, _ = _translation_error(left, right, shift_x, shift_y)
            if error < best_error:
                best_error, best_x, best_y = error, shift_x, shift_y

    improvement = (raw_error - best_error) / raw_error
    if (best_x == 0 and best_y == 0) or improvement < DETAIL_ALIGNMENT_MIN_IMPROVEMENT:
        return _DetailAlignment()

    scale = DETAIL_SAMPLE_SIDE / DETAIL_ALIGNMENT_SIDE
    shift_x = round(best_x * scale)
    shift_y = round(best_y * scale)
    overlap = (
        (DETAIL_SAMPLE_SIDE - abs(shift_x))
        * (DETAIL_SAMPLE_SIDE - abs(shift_y))
        / (DETAIL_SAMPLE_SIDE * DETAIL_SAMPLE_SIDE)
    )
    return _DetailAlignment(
        shift_x=shift_x,
        shift_y=shift_y,
        overlap_fraction=max(0.0, min(1.0, overlap)),
        applied=True,
    )


def _aligned_detail_images(
    left_image: Image.Image,
    right_image: Image.Image,
    alignment: _DetailAlignment,
) -> tuple[Image.Image, Image.Image]:
    """Crop to valid translated overlap, then normalize only that shared region."""

    if not alignment.applied:
        return left_image, right_image
    width, height = left_image.size
    shift_x, shift_y = alignment.shift_x, alignment.shift_y
    left_box = (
        max(0, shift_x),
        max(0, shift_y),
        min(width, width + shift_x),
        min(height, height + shift_y),
    )
    right_box = (
        max(0, -shift_x),
        max(0, -shift_y),
        min(width, width - shift_x),
        min(height, height - shift_y),
    )
    return (
        left_image.crop(left_box).resize(
            (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), Image.Resampling.LANCZOS
        ),
        right_image.crop(right_box).resize(
            (DETAIL_SAMPLE_SIDE, DETAIL_SAMPLE_SIDE), Image.Resampling.LANCZOS
        ),
    )


def _analyze_images(left_image: Image.Image, right_image: Image.Image) -> _DetailAnalysis:
    """Run the detail math on one already-chosen comparison coordinate space."""

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
        rgb_difference = np.mean(
            np.abs(left_pixels[:, :, :3] - right_pixels[:, :, :3]), axis=2
        )
        alpha_difference = np.abs(left_pixels[:, :, 3] - right_pixels[:, :, 3])
        mean_difference = np.maximum(
            rgb_difference,
            alpha_difference * DETAIL_ALPHA_DIFFERENCE_WEIGHT,
        )
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
    (
        coherent_changed_fraction,
        largest_region_fraction,
        substantial_region_count,
        spread_fraction,
    ) = _coherent_region_metrics(tiles)
    return _DetailAnalysis(
        changed_fraction=changed_fraction,
        weighted_changed=weighted_changed,
        weighted_difference=weighted_difference,
        local_fraction=local_fraction,
        coherent_changed_fraction=coherent_changed_fraction,
        largest_region_fraction=largest_region_fraction,
        substantial_region_count=substantial_region_count,
        spread_fraction=spread_fraction,
        tiles=tiles,
    )


def _analyze_detail_features(
    left: DetailFeature,
    right: DetailFeature,
) -> tuple[_DetailAnalysis, _DetailAnalysis, _DetailAlignment]:
    """Return raw viewer evidence and conservative aligned scoring evidence."""

    left_image, right_image = _detail_images(left, right)
    raw = _analyze_images(left_image, right_image)
    alignment = _estimate_alignment(left_image, right_image)
    aligned_left, aligned_right = _aligned_detail_images(
        left_image, right_image, alignment
    )
    aligned = (
        _analyze_images(aligned_left, aligned_right)
        if alignment.applied
        else raw
    )
    return raw, aligned, alignment


def compare_detail_features(left: DetailFeature, right: DetailFeature) -> DetailComparison:
    """Score bounded multi-scale differences without claiming pixel identity."""

    _raw_analysis, analysis, _alignment = _analyze_detail_features(left, right)
    # Matching coverage dominates the score. A single localized semantic change
    # therefore remains highly similar when the rest of the aligned frame is
    # unchanged. Multiple substantial zones and broad spatial distribution are
    # bounded secondary penalties so equal changed area scores lower when it is
    # scattered around the image.
    changed_area_penalty = DETAIL_CHANGED_AREA_PENALTY * analysis.weighted_changed
    difference_magnitude_penalty = (
        DETAIL_DIFFERENCE_MAGNITUDE_PENALTY * analysis.weighted_difference
    )
    extra_zone_count = max(0, analysis.substantial_region_count - 1)
    zone_count_penalty = DETAIL_EXTRA_ZONE_PENALTY * min(
        extra_zone_count,
        DETAIL_EXTRA_ZONE_CAP,
    )
    spread_weight = min(
        1.0,
        analysis.weighted_changed / DETAIL_SPREAD_FULL_WEIGHT_CHANGED_FRACTION,
    )
    spread_penalty = DETAIL_SPREAD_PENALTY * analysis.spread_fraction * spread_weight
    similarity = (
        100
        - changed_area_penalty
        - difference_magnitude_penalty
        - zone_count_penalty
        - spread_penalty
    )
    return DetailComparison(
        similarity_percent=round(max(0.0, min(100.0, similarity)), 2),
        changed_percent=round(analysis.changed_fraction * 100, 2),
    )


def detail_diagnostics(left: DetailFeature, right: DetailFeature) -> DetailDiagnostics:
    """Expose raw viewer-grid evidence alongside aligned scoring diagnostics."""

    raw, aligned, alignment = _analyze_detail_features(left, right)
    tile_changed_percents = tuple(
        tuple(round(float(value) * 100, 2) for value in row)
        for row in raw.tiles
    )
    shift_fraction = math.hypot(alignment.shift_x, alignment.shift_y) / DETAIL_SAMPLE_SIDE
    return DetailDiagnostics(
        changed_percent=round(raw.changed_fraction * 100, 2),
        localized_changed_percent=round(raw.local_fraction * 100, 2),
        coherent_changed_percent=round(raw.coherent_changed_fraction * 100, 2),
        largest_changed_region_percent=round(raw.largest_region_fraction * 100, 2),
        substantial_region_count=raw.substantial_region_count,
        aligned_changed_percent=round(aligned.changed_fraction * 100, 2),
        alignment_applied=alignment.applied,
        alignment_shift_percent=round(shift_fraction * 100, 2),
        alignment_overlap_percent=round(alignment.overlap_fraction * 100, 2),
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

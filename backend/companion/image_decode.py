"""Bounded image-decoder adapter for streamed Immich originals."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import BinaryIO

import rawpy
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener

from companion.integrity import DetectedFormat

MAX_DECODED_PIXELS = 64_000_000
SUPPORTED_FORMATS = frozenset({"jpeg", "heic", "heif", "avif", "png", "webp", "gif", "tiff"})

register_heif_opener()
Image.MAX_IMAGE_PIXELS = MAX_DECODED_PIXELS


@dataclass(frozen=True, slots=True)
class ImageDecodeResult:
    supported: bool
    valid: bool | None
    width: int | None = None
    height: int | None = None
    issue: str | None = None


def _decode_raw(stream: BinaryIO) -> ImageDecodeResult:
    """Decode a TIFF-signature RAW/DNG stream through LibRaw."""

    try:
        stream.seek(0)
        with rawpy.imread(stream) as raw:
            width = raw.sizes.width
            height = raw.sizes.height
            if width * height > MAX_DECODED_PIXELS:
                return ImageDecodeResult(
                    supported=True,
                    valid=None,
                    issue="image_decode_limit_exceeded",
                )
            pixels = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=True,
                output_bps=8,
            )
        height, width = pixels.shape[:2]
        return ImageDecodeResult(supported=True, valid=True, width=width, height=height)
    except (rawpy.LibRawError, OSError, ValueError):
        return ImageDecodeResult(
            supported=True,
            valid=False,
            issue="image_decode_failed",
        )


def decode_image(stream: BinaryIO, detected_format: DetectedFormat) -> ImageDecodeResult:
    """Fully decode one supported image without accepting arbitrary paths."""

    if detected_format not in SUPPORTED_FORMATS:
        return ImageDecodeResult(supported=False, valid=None)

    try:
        stream.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(stream) as image:
                image.load()
                width, height = image.size
                try:
                    orientation = image.getexif().get(274)
                except (AttributeError, OSError, ValueError):
                    orientation = None
                if orientation in {5, 6, 7, 8}:
                    width, height = height, width
        return ImageDecodeResult(supported=True, valid=True, width=width, height=height)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return ImageDecodeResult(
            supported=True,
            valid=None,
            issue="image_decode_limit_exceeded",
        )
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        if detected_format == "tiff":
            return _decode_raw(stream)
        return ImageDecodeResult(
            supported=True,
            valid=False,
            issue="image_decode_failed",
        )

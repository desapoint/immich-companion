"""Child-process entry point for fault-isolated LibRaw/rawpy decoding."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import BinaryIO


def _apply_memory_limit(limit_bytes: int) -> None:
    if limit_bytes <= 0 or os.name != "posix":
        return
    try:
        import resource

        _, current_hard = resource.getrlimit(resource.RLIMIT_AS)
        hard_is_unlimited = current_hard in {resource.RLIM_INFINITY, -1}
        target = limit_bytes if hard_is_unlimited else min(limit_bytes, current_hard)
        resource.setrlimit(resource.RLIMIT_AS, (target, target))
    except (ImportError, OSError, ValueError) as error:
        print(
            f"RAW worker could not apply memory limit: {type(error).__name__}: {error}",
            file=sys.stderr,
        )


@contextmanager
def _source(*, fd: int | None, input_path: Path | None) -> Iterator[BinaryIO]:
    if fd is not None:
        with os.fdopen(os.dup(fd), "rb", closefd=True) as stream:
            stream.seek(0)
            yield stream
        return
    if input_path is None:
        raise ValueError("RAW worker requires --fd or --input")
    with input_path.open("rb") as stream:
        yield stream


def _feature_payload(feature: object) -> dict[str, object]:
    payload = asdict(feature)
    for field in ("luminance_vector", "color_histogram"):
        value = payload[field]
        if not isinstance(value, bytes):
            raise TypeError(f"feature field {field!r} is not bytes")
        payload[field] = value.hex()
    return payload


def _emit(
    *,
    valid: bool | None,
    width: int | None = None,
    height: int | None = None,
    issue: str | None = None,
    feature: dict[str, object] | None = None,
) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "valid": valid,
                "width": width,
                "height": height,
                "issue": issue,
                "feature": feature,
            },
            separators=(",", ":"),
        )
    )
    sys.stdout.flush()


def _memory_related(error: BaseException) -> bool:
    name = type(error).__name__.lower()
    reason = str(error).lower()
    return "memory" in name or "memory" in reason or "mempool" in name


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=("decode", "features"), required=True)
    parser.add_argument("--max-pixels", type=int, required=True)
    parser.add_argument("--memory-limit", type=int, default=0)
    parser.add_argument("--include-pixel-hash", action="store_true")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fd", type=int)
    source.add_argument("--input", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _apply_memory_limit(args.memory_limit)
    rawpy_module = None

    try:
        import rawpy as rawpy_module

        with _source(fd=args.fd, input_path=args.input) as stream, rawpy_module.imread(
            stream
        ) as raw:
            source_width = raw.sizes.width
            source_height = raw.sizes.height
            if source_width * source_height > args.max_pixels:
                _emit(
                    valid=None,
                    width=source_width,
                    height=source_height,
                    issue="image_decode_limit_exceeded",
                )
                return 0
            pixels = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=True,
                output_bps=8,
            )

        height, width = pixels.shape[:2]
        if args.mode == "decode":
            _emit(valid=True, width=width, height=height)
            return 0

        from PIL import Image

        from companion.similarity_features import _build_feature

        image = Image.fromarray(pixels, "RGB")
        feature = _build_feature(
            image,
            bit_depth=8,
            channel_count=3,
            has_alpha=False,
            color_space="RAW-sRGB",
            orientation=None,
            icc_profile_present=False,
            has_exif=False,
            has_capture_time=False,
            has_camera_info=False,
            has_gps=False,
            has_orientation_metadata=False,
            include_pixel_hash=args.include_pixel_hash,
        )
        _emit(
            valid=True,
            width=feature.width,
            height=feature.height,
            feature=_feature_payload(feature),
        )
        return 0
    except MemoryError as error:
        print(f"RAW worker memory limit reached: {error}", file=sys.stderr)
        _emit(valid=None, issue="image_decode_memory_limit_exceeded")
        return 0
    except Exception as error:
        if rawpy_module is not None and isinstance(error, rawpy_module.LibRawError):
            issue = (
                "image_decode_memory_limit_exceeded"
                if _memory_related(error)
                else "image_decode_failed"
            )
            valid = None if issue == "image_decode_memory_limit_exceeded" else False
            print(
                f"RAW decode failed: {type(error).__name__}: {error}",
                file=sys.stderr,
            )
            _emit(valid=valid, issue=issue)
            return 0

        print(
            f"RAW worker failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        _emit(valid=None, issue="image_decode_raw_worker_failed")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate a small deterministic media seed without runtime dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import zlib
from collections.abc import Callable
from pathlib import Path

RgbPixel = tuple[int, int, int]
RgbaPixel = tuple[int, int, int, int]


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def encode_png(
    width: int,
    height: int,
    pixel: Callable[[int, int], RgbPixel | RgbaPixel],
    *,
    alpha: bool = False,
) -> bytes:
    channels = 4 if alpha else 3
    color_type = 6 if alpha else 2
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        for x in range(width):
            values = pixel(x, y)
            if len(values) != channels:
                raise ValueError("Pixel channel count does not match PNG color type")
            scanlines.extend(values)

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    # Level zero produces stable stored blocks across resets and Python builds.
    compressed = zlib.compress(bytes(scanlines), level=0)
    signature = b"\x89PNG\r\n\x1a\n"
    return (
        signature
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )


def base_scene(x: int, y: int) -> RgbPixel:
    sky = (35 + x // 3, 90 + y // 5, 145 + (x + y) // 8)
    if y > 78:
        return (42 + x // 6, 112 + (y - 78), 58 + x // 12)
    if 28 <= x <= 72 and 35 <= y <= 78:
        return (224, 137, 54)
    if (x - 145) ** 2 + (y - 27) ** 2 <= 14**2:
        return (250, 221, 90)
    return tuple(min(value, 255) for value in sky)  # type: ignore[return-value]


def edited_scene(x: int, y: int) -> RgbPixel:
    if 92 <= x < 105 and 57 <= y < 70:
        return (210, 48, 72)
    return base_scene(x, y)


def crop_scene(x: int, y: int) -> RgbPixel:
    source_x = 16 + (x * 160 // 144)
    source_y = 8 + (y * 104 // 96)
    return base_scene(source_x, source_y)


def negative_scene(x: int, y: int) -> RgbPixel:
    stripe = ((x // 12) + (y // 12)) % 2
    return (32, 38, 48) if stripe else (186, 199, 212)


def alpha_scene(x: int, y: int) -> RgbaPixel:
    distance = abs(x - 80) + abs(y - 60)
    opacity = max(36, 230 - distance * 2)
    return (72 + x, 42 + y, 188, opacity)


def file_record(relative_path: str, payload: bytes, family: str) -> dict[str, str | int]:
    return {
        "path": relative_path,
        "family": family,
        "bytes": len(payload),
        "sha1": hashlib.sha1(payload).hexdigest(),  # noqa: S324 - Immich uses SHA-1 dedupe.
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def generate(output: Path) -> dict[str, object]:
    output = output.resolve()
    if output in {Path("/"), Path.home().resolve(), Path.cwd().resolve()}:
        raise ValueError(f"Refusing unsafe output directory: {output}")

    images = output / "images"
    if images.exists():
        shutil.rmtree(images)
    images.mkdir(parents=True, exist_ok=True)

    base = encode_png(192, 128, base_scene)
    payloads = [
        ("images/base-scene.png", base, "exact-duplicate"),
        ("images/base-scene-copy.png", base, "exact-duplicate"),
        ("images/base-scene-small-edit.png", encode_png(192, 128, edited_scene), "small-edit"),
        ("images/base-scene-crop.png", encode_png(144, 96, crop_scene), "crop-resize"),
        ("images/negative-control.png", encode_png(192, 128, negative_scene), "negative-control"),
        ("images/alpha-overlay.png", encode_png(160, 120, alpha_scene, alpha=True), "alpha"),
    ]

    records: list[dict[str, str | int]] = []
    for relative_path, payload, family in payloads:
        (output / relative_path).write_bytes(payload)
        records.append(file_record(relative_path, payload, family))

    unique_sha1 = {str(record["sha1"]) for record in records}
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": "tools/generate_test_media.py",
        "files": records,
        "expected": {
            "source_files": len(records),
            "unique_assets": len(unique_sha1),
            "exact_duplicate_groups": [
                ["images/base-scene.png", "images/base-scene-copy.png"]
            ],
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = generate(args.output)
    expected = manifest["expected"]
    assert isinstance(expected, dict)
    print(
        "Generated "
        f"{expected['source_files']} deterministic files "
        f"({expected['unique_assets']} unique assets) at {args.output}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a rich deterministic media seed without runtime dependencies."""

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
Pixel = RgbPixel | RgbaPixel
PixelFactory = Callable[[int, int], Pixel]


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def encode_png(
    width: int,
    height: int,
    pixel: PixelFactory,
    *,
    alpha: bool = False,
    comment: str | None = None,
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
    chunks = [png_chunk(b"IHDR", header)]
    if comment is not None:
        chunks.append(png_chunk(b"tEXt", b"Comment\0" + comment.encode("utf-8")))
    chunks.extend((png_chunk(b"IDAT", compressed), png_chunk(b"IEND", b"")))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def base_scene(x: int, y: int) -> RgbPixel:
    sky = (35 + x // 3, 90 + y // 5, 145 + (x + y) // 8)
    if y > 78:
        return (42 + x // 6, 112 + (y - 78), 58 + x // 12)
    if 28 <= x <= 72 and 35 <= y <= 78:
        return (224, 137, 54)
    if (x - 145) ** 2 + (y - 27) ** 2 <= 14**2:
        return (250, 221, 90)
    return tuple(min(value, 255) for value in sky)  # type: ignore[return-value]


def scaled_scene(width: int, height: int) -> PixelFactory:
    def pixel(x: int, y: int) -> RgbPixel:
        source_x = min(191, x * 192 // width)
        source_y = min(127, y * 128 // height)
        return base_scene(source_x, source_y)

    return pixel


def edited_scene(index: int) -> PixelFactory:
    box_x = 18 + (index * 13) % 142
    box_y = 14 + (index * 11) % 88
    box_size = 5 + index % 7
    color = ((53 * index) % 220 + 20, (97 * index) % 210 + 30, (31 * index) % 200 + 40)

    def pixel(x: int, y: int) -> RgbPixel:
        if box_x <= x < box_x + box_size and box_y <= y < box_y + box_size:
            return color
        return base_scene(x, y)

    return pixel


def cropped_scene(index: int, width: int, height: int) -> PixelFactory:
    offset_x = 4 + index * 3
    offset_y = 3 + index * 2
    source_width = 192 - offset_x * 2
    source_height = 128 - offset_y * 2

    def pixel(x: int, y: int) -> RgbPixel:
        source_x = offset_x + x * source_width // width
        source_y = offset_y + y * source_height // height
        return base_scene(min(source_x, 191), min(source_y, 127))

    return pixel


def alpha_scene(index: int) -> PixelFactory:
    center_x = 46 + index * 8
    center_y = 42 + index * 4

    def pixel(x: int, y: int) -> RgbaPixel:
        distance = abs(x - center_x) + abs(y - center_y)
        opacity = max(18, 242 - distance * (2 + index % 3))
        return ((48 + x + index * 9) % 256, (34 + y * 2) % 256, 164 + index * 7, opacity)

    return pixel


def negative_scene(index: int) -> PixelFactory:
    def pixel(x: int, y: int) -> RgbPixel:
        mode = index % 4
        if mode == 0:
            active = ((x // (7 + index % 5)) + (y // (8 + index % 4))) % 2
            return (34, 42, 58) if active else (174 + index * 3, 202, 216)
        if mode == 1:
            return ((x * (index + 3)) % 256, (y * 5 + index * 17) % 256, 52 + index * 7)
        if mode == 2:
            ring = ((x - 96) ** 2 + (y - 64) ** 2) // (110 + index * 5)
            return (220, 70 + index * 4, 42) if ring % 2 else (28, 118, 168)
        diagonal = (x + y + index * 11) % 48
        return (235, 226, 188) if diagonal < 9 else (66, 52 + index * 4, 102)

    return pixel


def file_record(
    relative_path: str,
    payload: bytes,
    family: str,
    width: int,
    height: int,
    *,
    alpha: bool = False,
) -> dict[str, str | int | bool | float]:
    return {
        "path": relative_path,
        "family": family,
        "bytes": len(payload),
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 6),
        "has_alpha": alpha,
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

    payloads: list[tuple[str, bytes, str, int, int, bool]] = []

    base = encode_png(192, 128, base_scene)
    payloads.extend(
        (
            ("images/base-scene.png", base, "pixel-identical", 192, 128, False),
            ("images/base-scene-copy.png", base, "exact-duplicate", 192, 128, False),
        )
    )
    for index in range(1, 10):
        payloads.append(
            (
                f"images/base-scene-metadata-{index:02d}.png",
                encode_png(192, 128, base_scene, comment=f"metadata-variant-{index:02d}"),
                "pixel-identical",
                192,
                128,
                False,
            )
        )

    dimensions = [
        (64, 64), (96, 64), (128, 72), (128, 96), (144, 96), (160, 90),
        (160, 120), (192, 108), (192, 128), (240, 160), (256, 144), (256, 192),
    ]
    for index, (width, height) in enumerate(dimensions, start=1):
        payloads.append(
            (
                f"images/base-scene-resized-{index:02d}-{width}x{height}.png",
                encode_png(
                    width,
                    height,
                    scaled_scene(width, height),
                    comment=f"resized-{width}x{height}",
                ),
                "resize",
                width,
                height,
                False,
            )
        )

    for index in range(1, 13):
        payloads.append(
            (
                f"images/base-scene-edit-{index:02d}.png",
                encode_png(192, 128, edited_scene(index), comment=f"small-edit-{index:02d}"),
                "small-edit-occlusion",
                192,
                128,
                False,
            )
        )

    for index in range(1, 9):
        width = 128 + index * 4
        height = 84 + index * 3
        payloads.append(
            (
                f"images/base-scene-crop-{index:02d}-{width}x{height}.png",
                encode_png(width, height, cropped_scene(index, width, height)),
                "crop",
                width,
                height,
                False,
            )
        )

    for index in range(1, 9):
        width = 128 + index * 4
        height = 96 + index * 3
        payloads.append(
            (
                f"images/alpha-overlay-{index:02d}-{width}x{height}.png",
                encode_png(width, height, alpha_scene(index), alpha=True),
                "alpha",
                width,
                height,
                True,
            )
        )

    for index in range(1, 17):
        width = 144 + (index % 4) * 16
        height = 96 + (index % 3) * 16
        payloads.append(
            (
                f"images/negative-control-{index:02d}-{width}x{height}.png",
                encode_png(width, height, negative_scene(index), comment=f"negative-{index:02d}"),
                "negative-control",
                width,
                height,
                False,
            )
        )

    records: list[dict[str, str | int | bool | float]] = []
    for relative_path, payload, family, width, height, alpha in payloads:
        (output / relative_path).write_bytes(payload)
        records.append(file_record(relative_path, payload, family, width, height, alpha=alpha))

    unique_paths = [
        str(record["path"])
        for record in records
        if record["path"] != "images/base-scene-copy.png"
    ]
    base_family = [
        str(record["path"])
        for record in records
        if record["family"] in {"pixel-identical", "resize", "small-edit-occlusion"}
        and record["path"] != "images/base-scene-copy.png"
    ]
    album_a = base_family[:24]
    album_b = base_family[8:32]
    album_c = [
        str(record["path"])
        for record in records
        if record["family"] in {"crop", "alpha"}
    ]
    dimensions_album = [
        str(record["path"]) for record in records if record["family"] == "resize"
    ]
    alpha_paths = [
        str(record["path"]) for record in records if record["family"] == "alpha"
    ]
    tag_fixtures = [
        {
            "name": "Similar candidate",
            "color": "#2a9d8f",
            "paths": base_family,
        },
        {
            "name": "Transparent",
            "color": "#7c3aed",
            "paths": alpha_paths,
        },
        {
            "name": "Review",
            "color": "#d97706",
            "paths": unique_paths[::5],
        },
        {
            "name": "Exact duplicate",
            "color": "#dc2626",
            "paths": ["images/base-scene.png", "images/base-scene-copy.png"],
        },
    ]
    tagged_paths = {
        str(path)
        for fixture in tag_fixtures
        for path in fixture["paths"]
    }
    tagged_sha1 = {
        str(record["sha1"])
        for record in records
        if str(record["path"]) in tagged_paths
    }
    unique_sha1 = {str(record["sha1"]) for record in records}

    manifest: dict[str, object] = {
        "schema_version": 2,
        "generator": "tools/generate_test_media.py",
        "files": records,
        "relationships": {
            "exact_duplicate_groups": [["images/base-scene.png", "images/base-scene-copy.png"]],
            "pixel_identical_groups": [[
                "images/base-scene.png",
                *[f"images/base-scene-metadata-{index:02d}.png" for index in range(1, 10)],
            ]],
            "visually_similar_groups": [base_family, album_c],
            "albums": [
                {
                    "name": "Companion Test · Album A",
                    "description": "Overlaps Album B for AND/NOT searches.",
                    "paths": album_a,
                },
                {
                    "name": "Companion Test · Album B",
                    "description": "Overlaps Album A and adds variants.",
                    "paths": album_b,
                },
                {
                    "name": "Companion Test · Transparent and crops",
                    "description": "Alpha and crop fixtures.",
                    "paths": album_c,
                },
                {
                    "name": "Companion Test · Multiple dimensions",
                    "description": "Same scene at different dimensions and ratios.",
                    "paths": dimensions_album,
                },
                {
                    "name": "Companion Test · Page two",
                    "description": "Assets beyond the default first search page.",
                    "paths": unique_paths[48:],
                },
            ],
            "stacks": [
                {"paths": base_family[0:4]},
                {"paths": base_family[12:16]},
                {"paths": album_c[0:4]},
            ],
            "tags": tag_fixtures,
            "favorite_paths": unique_paths[4:12],
            "archived_paths": unique_paths[20:27],
            "trashed_paths": unique_paths[-6:],
        },
        "expected": {
            "source_files": len(records),
            "unique_assets": len(unique_sha1),
            "albums": 5,
            "stacks": 3,
            "tags": len(tag_fixtures),
            "tagged_assets": len(tagged_sha1),
            "favorited_assets": 8,
            "archived_assets": 7,
            "trashed_assets": 6,
            "default_page_size": 48,
            "minimum_search_pages": 2,
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

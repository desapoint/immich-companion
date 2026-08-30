#!/usr/bin/env python3
"""Generate a rich deterministic media seed without runtime dependencies."""

from __future__ import annotations

import argparse
import base64
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

# Generated once with Pillow from a 32x24 solid RGB image. Keeping the bytes
# inline preserves the generator's standard-library-only runtime contract.
HEALTHY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8Q"
    "EBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQ"
    "EBAQEBAQEBD/wAARCABAAGADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUF"
    "BAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVW"
    "V1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi"
    "4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAEC"
    "AxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVm"
    "Z2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq"
    "8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5zh0//Zq7Dp/tWxFp/wDs1dh0/wD2a/YqmMPzPB4/zMaLT/8AZq7Fp/tWzDp/+zV2HT/9"
    "muCpjD6vB4/zMaLT/wDZq7Dp/wDs1sRaf/s1dh0//ZrhqYw+qweP8zGi0/8A2auw6f8A7NbMWn+1XYtP/wBmuGpjD6vB4/zMaHT/"
    "APZq7Fp/+zWxFp/tV2HT/wDZrgqYzzPq8Hj/ADMaLT/9mrsWn/7NbMOn/wCzV2HT/wDZrhqYw+qweP8AM8Yi0/8A2auw6f8A7NbE"
    "On/7NXYtP/2a96pjD/PXB4/zOeuLd7aJZI0UksByPY0kU1z/AM8o/wAj/jXRajp/+jJ8v8Y/karQ6f8A7NfjXGXE2YYHMnRw9Zxj"
    "ZaI+4yvFwlBNlOGa5/55R/kf8auwzXP/ADyi/I/41bh0/wD2auxaf/s18XU4yzf/AKCJH2ODxNPTQtw6f/s1ch0//ZrZh0//AGau"
    "xaf/ALNft1TGHr4PH+ZjQ6f/ALNXYdP/ANmtmLT/APZq5Fp/+zXBUxh9Vg8f5mPFp/8As1ci0/2rZi0//Zq7Dp/+zXDUxh9Xg8f5"
    "njEWn+1XYtP/ANmtmHT/APZq5Fp/+zXu1MYf56YPH7anM6jp/wDoyfL/ABj+RqtFp/8As11+oaf/AKMny/xj+RqtDp/+zX4Px7jP"
    "+FeX+GJ95lWP/drUxotP9quw6f8A7NbMWn/7NXIdP/2a+BqYw+yweP21LcWn/wCzVyLT/wDZrZi0/wD2auw6f/s1/RdTGHpYPH7a"
    "mNFp/wDs1dh0/wBq2YdP/wBmrkOn/wCzXBUxh9Xg8ftqY8On/wCzVyHT/wDZrZh0/wD2auxaf/s1w1MYfVYPH7anjEOn/wCzV2LT"
    "/wDZrzSL9rH9nT/ooX/lIvv/AIzVyH9rH9nT/ooX/lIvv/jNfdVMkzz/AKA6v/guf+R/DGD4c4j0/wBgr/8Agqp/8ieizaN9qjEe"
    "duG3ZxmnQ+F/+m//AI5/9euFh/ax/Z04/wCLhf8AlIvv/jNXYf2sf2dP+ihf+Ui+/wDjNfLZlwFicyrOvisvqyltfkqrb0sj6/AZ"
    "FxNBJRwNf/wVP/5E7qHwv/03/wDHP/r1ch8L/wDTf/xz/wCvXDRftY/s6f8ARQv/ACkX3/xmrkX7WH7On/RQv/KRff8AxmvFqeGb"
    "/wChbV/8BrH1uDyXijT/AGGv/wCCZ/8AyJ6ZDp/+zV2LT/8AZrzOH9rD9nT/AKKF/wCUi+/+M1di/aw/Z0/6KF/5SL7/AOM17FTJ"
    "M8/6A6v/AILn/kfSYPhziPT/AGCv/wCCqn/yJ6XFp/tV2LT/APZrzSH9rH9nT/ooX/lIvv8A4zVyH9rH9nT/AKKF/wCUi+/+M1wV"
    "Mkzz/oDq/wDguf8AkfV4PhziPT/YK/8A4Kqf/InpkWn+1XYtP/2a8zi/ax/Z0/6KF/5SL7/4zV2H9rH9nT/ooX/lIvv/AIzXDUyT"
    "PP8AoDq/+C5/5H1eD4c4j0/2Cv8A+Cqn/wAif//Z"
)


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


def brightness_scene(percent: int) -> PixelFactory:
    def pixel(x: int, y: int) -> RgbPixel:
        adjusted = tuple(
            min(255, max(0, value * percent // 100)) for value in base_scene(x, y)
        )
        return adjusted  # type: ignore[return-value]

    return pixel


def color_shift_scene(red_delta: int, blue_delta: int) -> PixelFactory:
    def pixel(x: int, y: int) -> RgbPixel:
        red, green, blue = base_scene(x, y)
        return (
            min(255, max(0, red + red_delta)),
            green,
            min(255, max(0, blue + blue_delta)),
        )

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

    # These directories are wholly owned by this generator. Recreate all of
    # them so renamed fixtures cannot linger and become unexpected Immich
    # external-library assets on the next deterministic reset.
    images = output / "images"
    for generated_directory in (images, output / "external-library", output / "diagnostics"):
        if generated_directory.exists():
            shutil.rmtree(generated_directory)
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

    same_size_upload = encode_png(96, 64, negative_scene(2), comment="same-size-a")
    payloads.extend(
        (
            (
                "images/duplicate-cases/healthy-reference.jpg",
                HEALTHY_JPEG,
                "duplicate-integrity-reference",
                96,
                64,
                False,
            ),
            (
                "images/duplicate-cases/same-name.png",
                encode_png(96, 64, negative_scene(3), comment="same-name-upload"),
                "duplicate-negative-control",
                96,
                64,
                False,
            ),
            (
                "images/duplicate-cases/same-size.png",
                same_size_upload,
                "duplicate-negative-control",
                96,
                64,
                False,
            ),
        )
    )

    records: list[dict[str, str | int | bool | float]] = []
    for relative_path, payload, family, width, height, alpha in payloads:
        media_path = output / relative_path
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(payload)
        records.append(file_record(relative_path, payload, family, width, height, alpha=alpha))

    external_payloads = (
        (
            "external-library/byte-perfect/base-scene-external.png",
            base,
            "cross-source-byte-perfect",
            192,
            128,
            False,
        ),
        (
            "external-library/pixel-identical/base-scene-external-metadata.png",
            encode_png(192, 128, base_scene, comment="external-metadata-variant"),
            "cross-source-pixel-identical",
            192,
            128,
            False,
        ),
        (
            "external-library/integrity/base-scene-with-trailing-data.png",
            base + b"COMPANION-DEMO-TRAILING-DATA",
            "cross-source-integrity-malformed",
            192,
            128,
            False,
        ),
        (
            "external-library/negative-controls/same-name.png",
            encode_png(96, 64, negative_scene(8), comment="same-name-other!"),
            "cross-source-negative-control",
            96,
            64,
            False,
        ),
        (
            "external-library/negative-controls/same-size.png",
            encode_png(96, 64, negative_scene(6), comment="same-size-b"),
            "cross-source-negative-control",
            96,
            64,
            False,
        ),
        (
            "external-library/similarity/brightness-95-percent.png",
            encode_png(192, 128, brightness_scene(95), comment="brightness-95"),
            "cross-source-similarity",
            192,
            128,
            False,
        ),
        (
            "external-library/similarity/brightness-105-percent.png",
            encode_png(192, 128, brightness_scene(105), comment="brightness-105"),
            "cross-source-similarity",
            192,
            128,
            False,
        ),
        (
            "external-library/similarity/warmer-color-balance.png",
            encode_png(192, 128, color_shift_scene(8, -6), comment="warmer-color"),
            "cross-source-similarity",
            192,
            128,
            False,
        ),
        (
            "external-library/similarity/small-occlusion.png",
            encode_png(192, 128, edited_scene(1), comment="small-occlusion"),
            "cross-source-similarity",
            192,
            128,
            False,
        ),
        (
            "external-library/similarity/cropped.png",
            encode_png(160, 104, cropped_scene(1, 160, 104), comment="cropped"),
            "cross-source-similarity",
            160,
            104,
            False,
        ),
        (
            "external-library/similarity/resized.png",
            encode_png(256, 192, scaled_scene(256, 192), comment="resized"),
            "cross-source-similarity",
            256,
            192,
            False,
        ),
    )
    external_records: list[dict[str, str | int | bool | float]] = []
    for relative_path, payload, family, width, height, alpha in external_payloads:
        external_path = output / relative_path
        external_path.parent.mkdir(parents=True, exist_ok=True)
        external_path.write_bytes(payload)
        external_records.append(
            file_record(relative_path, payload, family, width, height, alpha=alpha)
        )

    # These deterministic byte streams document the integrity/corruption cases
    # needed by the later non-exact duplicate workflow. They are intentionally
    # not uploaded: malformed originals are analysis fixtures, not baseline
    # Immich assets, until that guarded workflow is implemented.
    diagnostic_dir = output / "diagnostics"
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    healthy_jpeg = HEALTHY_JPEG
    diagnostic_payloads = (
        ("diagnostics/jpeg-minimal-healthy.jpg", healthy_jpeg, "healthy"),
        (
            "diagnostics/jpeg-trailing-bytes.jpg",
            healthy_jpeg + b"COMPANION-TRAILING-DATA",
            "trailing-bytes",
        ),
        (
            "diagnostics/jpeg-truncated-segment.jpg",
            b"\xff\xd8\xff\xe1\x00\x10truncated",
            "truncated-segment",
        ),
        ("diagnostics/jpeg-missing-soi.jpg", b"not-a-jpeg", "missing-soi"),
    )
    diagnostic_records: list[dict[str, object]] = []
    for relative_path, payload, classification in diagnostic_payloads:
        (output / relative_path).write_bytes(payload)
        diagnostic_records.append(
            {
                "path": relative_path,
                "family": "corruption-diagnostic",
                "expected_case": classification,
                "bytes": len(payload),
                "sha1": hashlib.sha1(payload).hexdigest(),  # noqa: S324
                "sha256": hashlib.sha256(payload).hexdigest(),
                "upload_to_immich": False,
            }
        )

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
        "schema_version": 3,
        "generator": "tools/generate_test_media.py",
        "files": records,
        "external_files": external_records,
        "relationships": {
            "exact_duplicate_groups": [["images/base-scene.png", "images/base-scene-copy.png"]],
            "pixel_identical_groups": [[
                "images/base-scene.png",
                *[f"images/base-scene-metadata-{index:02d}.png" for index in range(1, 10)],
            ]],
            "visually_similar_groups": [base_family, album_c],
            "analysis_fixtures": diagnostic_records,
            "duplicate_demo_groups": [
                {
                    "case": "byte-perfect-cross-source",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/byte-perfect/base-scene-external.png",
                    "expected_byte_relation": "equal",
                    "expected_pixel_relation": "equal",
                    "expected_integrity": "healthy",
                },
                {
                    "case": "pixel-identical-different-bytes",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/pixel-identical/base-scene-external-metadata.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "equal",
                    "expected_integrity": "healthy",
                },
                {
                    "case": "decodable-png-trailing-data",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/integrity/base-scene-with-trailing-data.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "equal",
                    "expected_integrity": "malformed",
                },
                {
                    "case": "same-filename-different-content",
                    "upload_path": "images/duplicate-cases/same-name.png",
                    "external_path": "external-library/negative-controls/same-name.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "different",
                    "expected_integrity": "healthy",
                },
                {
                    "case": "same-filesize-different-content",
                    "upload_path": "images/duplicate-cases/same-size.png",
                    "external_path": "external-library/negative-controls/same-size.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "different",
                    "expected_integrity": "healthy",
                },
                {
                    "case": "similar-brightness-darker",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/similarity/brightness-95-percent.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "similar",
                    "expected_integrity": "healthy",
                    "transformation": "brightness_95_percent",
                },
                {
                    "case": "similar-brightness-lighter",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/similarity/brightness-105-percent.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "similar",
                    "expected_integrity": "healthy",
                    "transformation": "brightness_105_percent",
                },
                {
                    "case": "similar-color-balance",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/similarity/warmer-color-balance.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "similar",
                    "expected_integrity": "healthy",
                    "transformation": "red_plus_8_blue_minus_6",
                },
                {
                    "case": "similar-small-occlusion",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/similarity/small-occlusion.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "similar",
                    "expected_integrity": "healthy",
                    "transformation": "small_occlusion",
                },
                {
                    "case": "similar-crop",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/similarity/cropped.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "similar",
                    "expected_integrity": "healthy",
                    "transformation": "crop_and_resample",
                },
                {
                    "case": "similar-resize",
                    "upload_path": "images/base-scene.png",
                    "external_path": "external-library/similarity/resized.png",
                    "expected_byte_relation": "different",
                    "expected_pixel_relation": "similar",
                    "expected_integrity": "healthy",
                    "transformation": "resize",
                },
            ],
            "external_libraries": [
                {
                    "name": "Companion Demo · External Originals",
                    "import_path": "/external-library",
                    "manifest_prefix": "external-library/",
                    "read_only": True,
                }
            ],
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
            "analysis_fixtures": len(diagnostic_records),
            "external_assets": len(external_records),
            "duplicate_demo_groups": 11,
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

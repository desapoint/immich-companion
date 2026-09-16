"""Deterministic candidate-detail score calibration; no library media is read.

Run with: PYTHONPATH=backend python tools/benchmark_similarity_detail.py
"""

from io import BytesIO

from companion.similarity_detail import (
    DETAIL_FEATURE_VERSION,
    compare_detail_features,
    extract_detail_feature,
)
from PIL import Image, ImageDraw


def encoded(image: Image.Image, image_format: str = "PNG") -> bytes:
    output = BytesIO()
    image.save(output, format=image_format, quality=88)
    return output.getvalue()


def scene() -> Image.Image:
    image = Image.new("RGB", (1024, 1024), (90, 115, 145))
    draw = ImageDraw.Draw(image)
    draw.ellipse((300, 80, 720, 500), fill=(235, 190, 155))
    draw.rectangle((355, 470, 670, 930), fill=(205, 70, 100))
    draw.ellipse((408, 270, 438, 294), fill=(30, 30, 35))
    draw.ellipse((585, 270, 615, 294), fill=(30, 30, 35))
    return image


def variants() -> list[tuple[str, Image.Image, str]]:
    original = scene()
    narrow_strap = original.copy()
    ImageDraw.Draw(narrow_strap).rectangle((472, 470, 492, 615), fill=(30, 80, 180))
    face_accessory = original.copy()
    ImageDraw.Draw(face_accessory).rectangle((405, 265, 620, 330), fill=(35, 35, 45))
    swimsuit = original.copy()
    ImageDraw.Draw(swimsuit).rectangle((390, 590, 640, 850), fill=(45, 95, 180))
    broad_change = original.copy()
    ImageDraw.Draw(broad_change).rectangle((355, 470, 670, 930), fill=(45, 95, 180))
    return [
        ("same PNG", original, "PNG"),
        ("JPEG rendition", original, "JPEG"),
        ("narrow swimsuit strap", narrow_strap, "PNG"),
        ("face accessory", face_accessory, "PNG"),
        ("swimsuit panel", swimsuit, "PNG"),
        ("broad outfit recolor", broad_change, "PNG"),
    ]


def main() -> None:
    reference_image = scene()
    reference = extract_detail_feature(BytesIO(encoded(reference_image)), "png")
    assert reference is not None
    print(f"detail feature version {DETAIL_FEATURE_VERSION}; reference 1024×1024")
    print(f"{'variant':25} {'similarity':>10} {'changed area':>13}")
    for name, image, image_format in variants():
        feature = extract_detail_feature(
            BytesIO(encoded(image, image_format)), image_format.lower()
        )
        assert feature is not None
        comparison = compare_detail_features(reference, feature)
        print(
            f"{name:25} {comparison.similarity_percent:9.2f}% "
            f"{comparison.changed_percent:12.2f}%"
        )


if __name__ == "__main__":
    main()

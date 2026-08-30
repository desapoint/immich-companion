"""Decoder-state regressions for supported Immich image originals."""

import base64
from io import BytesIO

from PIL import Image

from companion.image_decode import decode_image

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
HEIC_1X1 = base64.b64decode(
    "AAAAGGZ0eXBoZWljAAAAAG1pZjFoZWljAAABrW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAHBpY3Q"
    "AAAAAAAAAAAAAAAAAAAAADnBpdG0AAAAAAAIAAAAQaWRhdAAAAAAAAQABAAAAOGlsb2MBAAAAREA"
    "AAgABAAAAAAAAAc0AAQAAAAAAAAAsAAIAAQAAAAAAAAABAAAAAAAAAAgAAAA4aWluZgAAAAAAAgA"
    "AABVpbmZlAgAAAQABAABodmMxAAAAABVpbmZlAgAAAAACAABncmlkAAAAANhpcHJwAAAAtmlwY28"
    "AAAB2aHZjQwEDcAAAAAAAAAAAAB7wAPz9+PgAAA8DIAABABhAAQwB//8DcAAAAwCQAAADAAADAB6"
    "6AkAhAAEAKkIBAQNwAAADAJAAAAMAAAMAHqAggQWW6q6a5uBAQMCAAAADAIAAAAMAhCIAAQAGRAH"
    "Bc8GJAAAAFGlzcGUAAAAAAAAAAQAAAAEAAAAUaXNwZQAAAAAAAABAAAAAQAAAABBwaXhpAAAAAAMI"
    "CAgAAAAaaXBtYQAAAAAAAAACAAECgQMAAgIChAAAABppcmVmAAAAAAAAAA5kaW1nAAIAAQABAAAAN"
    "G1kYXQAAAAoKAGvCchMZYA50NoPIfzz81Qfsm577GJt3lf8kLAr+NbNIoeRR7JeYA=="
)


def test_png_is_fully_decoded_with_dimensions() -> None:
    result = decode_image(BytesIO(PNG_1X1), "png")

    assert result.supported is True
    assert result.valid is True
    assert (result.width, result.height) == (1, 1)
    assert result.issue is None


def test_heic_is_fully_decoded_with_installed_codec() -> None:
    result = decode_image(BytesIO(HEIC_1X1), "heic")

    assert result.supported is True
    assert result.valid is True
    assert (result.width, result.height) == (1, 1)


def test_corrupt_supported_image_is_failed_not_unsupported() -> None:
    result = decode_image(BytesIO(b"\x89PNG\r\n\x1a\ncorrupt"), "png")

    assert result.supported is True
    assert result.valid is False
    assert result.issue == "image_decode_failed"


def test_unknown_format_is_unsupported_without_corruption_conclusion() -> None:
    result = decode_image(BytesIO(b"plain bytes"), "unknown")

    assert result.supported is False
    assert result.valid is None
    assert result.issue is None


def test_pixel_safety_limit_is_unverified_not_failed(monkeypatch) -> None:
    payload = BytesIO()
    Image.new("RGB", (2, 2)).save(payload, format="PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    result = decode_image(payload, "png")

    assert result.supported is True
    assert result.valid is None
    assert result.issue == "image_decode_limit_exceeded"

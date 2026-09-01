"""Deterministic coverage for streaming integrity primitives."""

import base64
import hashlib

import pytest

from companion.integrity import FileIntegrityAnalyzer, decode_immich_sha1, detect_file_format


def analyze(payload: bytes, chunks: list[int], *, mime: str | None = "image/jpeg"):
    checksum = base64.b64encode(hashlib.sha1(payload, usedforsecurity=False).digest()).decode()
    analyzer = FileIntegrityAnalyzer(mime, checksum)
    offset = 0
    for size in chunks:
        analyzer.update(payload[offset : offset + size])
        offset += size
    analyzer.update(payload[offset:])
    return analyzer.finalize()


def jpeg(scan: bytes = b"\x01\xff\x00\x02\xff\xd0\x03") -> bytes:
    return (
        b"\xff\xd8"
        b"\xff\xe0\x00\x04AB"
        b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
        + scan
        + b"\xff\xd9"
    )


def iso_bmff_trailer() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"


@pytest.mark.parametrize("chunks", [[1000], [1] * 64, [1, 2, 3, 5, 8, 13]])
def test_hashes_and_valid_jpeg_are_independent_of_chunk_boundaries(chunks: list[int]) -> None:
    payload = jpeg()

    result = analyze(payload, chunks)

    assert result.byte_size == len(payload)
    assert result.sha1_hex == hashlib.sha1(payload, usedforsecurity=False).hexdigest()
    assert result.sha256_hex == hashlib.sha256(payload).hexdigest()
    assert result.detected_format == "jpeg"
    assert result.format_matches_declared is True
    assert result.classification == "healthy"
    assert result.structurally_valid is True
    assert result.container_valid is True
    assert result.decode_supported is False
    assert result.decode_valid is None
    assert result.jpeg_eoi_offset == len(payload)
    assert result.trailing_byte_count == 0
    assert result.immich_checksum_match is True
    assert result.issues == ()


def test_unknown_jpeg_trailing_bytes_are_informational_not_integrity_warning() -> None:
    base = jpeg()
    payload = base + b"trailing"

    result = analyze(payload, [len(base) - 1, 2, 3])

    assert result.classification == "healthy"
    assert result.structurally_valid is True
    assert result.jpeg_eoi_offset == len(base)
    assert result.trailing_byte_count == 8
    assert result.issues == ("jpeg_trailing_bytes_unknown",)


@pytest.mark.parametrize(
    ("trailer", "expected_issue"),
    [
        (b"\x00\x00MotionPhoto_Data\x00payload", "jpeg_trailing_motion_photo"),
        (b"payload-SEFH-more-SEFT", "jpeg_trailing_samsung_sef"),
        (iso_bmff_trailer(), "jpeg_trailing_iso_bmff"),
        (b"\x00\xff \r\n\t", "jpeg_trailing_padding"),
    ],
)
def test_known_jpeg_trailing_data_is_described_without_warning(
    trailer: bytes,
    expected_issue: str,
) -> None:
    base = jpeg()
    result = analyze(base + trailer, [len(base), 1, 2, 5, 8])

    assert result.classification == "healthy"
    assert result.structurally_valid is True
    assert result.trailing_byte_count == len(trailer)
    assert result.issues == (expected_issue,)


def test_motion_photo_signature_can_be_detected_from_trailer_tail() -> None:
    base = jpeg()
    trailer = b"x" * (64 * 1024 + 32) + b"MotionPhoto_Data"

    result = analyze(base + trailer, [len(base), len(trailer)])

    assert result.classification == "healthy"
    assert result.trailing_byte_count == len(trailer)
    assert result.issues == ("jpeg_trailing_motion_photo",)


@pytest.mark.parametrize("chunks", [[1000], [1] * 32, [7, 4, 3, 2, 1]])
def test_png_trailing_bytes_are_detected_across_chunk_boundaries(chunks: list[int]) -> None:
    payload = b"\x89PNG\r\n\x1a\n" + b"payload" + b"\x00\x00\x00\x00IEND\xaeB\x60\x82"

    healthy = analyze(payload, chunks, mime="image/png")
    trailing = analyze(payload + b"trailing", chunks, mime="image/png")

    assert healthy.classification == "healthy"
    assert healthy.structurally_valid is True
    assert healthy.trailing_byte_count == 0
    assert trailing.classification == "malformed"
    assert trailing.structurally_valid is False
    assert trailing.trailing_byte_count == 8
    assert trailing.issues == ("png_trailing_bytes",)


def test_png_without_iend_is_malformed() -> None:
    result = analyze(b"\x89PNG\r\n\x1a\npayload", [1] * 15, mime="image/png")

    assert result.classification == "malformed"
    assert result.structurally_valid is False
    assert result.issues == ("png_missing_iend",)


@pytest.mark.parametrize(
    ("payload", "issue"),
    [
        (b"\xff\xd8\xff\xe0\x00\x01", "jpeg_invalid_segment_length"),
        (b"\xff\xd8\xff\xe0\x00\x05A", "jpeg_truncated_segment"),
        (b"\xff\xd8\xff\xda\x00\x02scan", "jpeg_missing_eoi"),
    ],
)
def test_malformed_jpeg_conditions_are_classified(payload: bytes, issue: str) -> None:
    result = analyze(payload, [1] * len(payload))

    assert result.classification == "malformed"
    assert result.structurally_valid is False
    assert issue in result.issues


def test_content_magic_enables_jpeg_parsing_when_mime_is_generic() -> None:
    result = analyze(jpeg(), [1, 1, 2, 5], mime="application/octet-stream")

    assert result.detected_format == "jpeg"
    assert result.structurally_valid is True


@pytest.mark.parametrize("payload", [b"", b"\xff", b"not-a-jpeg"])
def test_declared_jpeg_without_jpeg_magic_is_not_called_malformed(payload: bytes) -> None:
    result = analyze(payload, [1] * len(payload))

    assert result.detected_format == "unknown"
    assert result.structurally_valid is None
    assert result.container_valid is None
    assert result.classification == "hash_only"
    assert "jpeg_missing_soi" not in result.issues


@pytest.mark.parametrize(
    ("expected", "payload"),
    [
        ("jpeg", b"\xff\xd8rest"),
        ("png", b"\x89PNG\r\n\x1a\nrest"),
        ("webp", b"RIFF\x08\x00\x00\x00WEBPrest"),
        ("gif", b"GIF89arest"),
        ("tiff", b"II*\x00rest"),
        ("heic", b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1"),
        ("heif", b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00heis"),
        ("avif", b"\x00\x00\x00\x18ftypavif\x00\x00\x00\x00mif1"),
        ("unknown", b"plain bytes"),
    ],
)
def test_common_formats_are_detected_from_content(expected: str, payload: bytes) -> None:
    assert detect_file_format(payload) == expected
    assert analyze(
        payload,
        [1] * len(payload),
        mime="application/octet-stream",
    ).detected_format == expected


def test_heic_declared_as_jpeg_is_a_warning_not_malformed() -> None:
    payload = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1"

    result = analyze(payload, [1] * len(payload), mime="image/jpeg")

    assert result.detected_format == "heic"
    assert result.format_matches_declared is False
    assert result.classification == "warning"
    assert result.structurally_valid is None
    assert result.decode_supported is False
    assert result.decode_valid is None
    assert result.issues == ("mime_format_mismatch",)


def test_non_jpeg_assets_are_hash_only_and_checksum_mismatch_is_a_warning() -> None:
    payload = b"plain bytes"
    analyzer = FileIntegrityAnalyzer("video/mp4", "00" * 20)
    analyzer.update(payload)

    result = analyzer.finalize()

    assert result.detected_format == "unknown"
    assert result.classification == "warning"
    assert result.structurally_valid is None
    assert result.immich_checksum_match is False
    assert result.issues == ("immich_checksum_mismatch",)


def test_known_checksum_encodings_decode_and_unknown_values_do_not() -> None:
    digest = hashlib.sha1(b"fixture", usedforsecurity=False).digest()

    assert decode_immich_sha1(digest.hex()) == digest
    assert decode_immich_sha1(base64.b64encode(digest).decode()) == digest
    assert decode_immich_sha1(base64.b64encode(digest).decode().rstrip("=")) == digest
    assert decode_immich_sha1("base64-checksum") is None
    assert decode_immich_sha1(None) is None


def test_decode_failure_and_dimension_mismatch_update_normalized_classification() -> None:
    base = analyze(b"plain bytes", [2, 3], mime="application/octet-stream")

    failed = base.with_decode(
        supported=True,
        valid=False,
        width=None,
        height=None,
        immich_width=10,
        immich_height=10,
        issue="image_decode_failed",
    )
    mismatched = base.with_decode(
        supported=True,
        valid=True,
        width=10,
        height=20,
        immich_width=20,
        immich_height=10,
        issue=None,
    )

    assert failed.classification == "malformed"
    assert failed.issues == ("image_decode_failed",)
    assert mismatched.classification == "warning"
    assert mismatched.dimensions_match_immich is False
    assert mismatched.issues == ("dimensions_mismatch",)

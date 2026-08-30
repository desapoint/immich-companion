"""Incremental, dependency-free file-integrity analysis utilities."""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from typing import Literal

ANALYZER_VERSION = 2
JPEG_MIME_TYPES = frozenset({"image/jpeg", "image/jpg", "image/pjpeg"})
FORMAT_MIME_TYPES: dict[str, frozenset[str]] = {
    "jpeg": JPEG_MIME_TYPES,
    "heic": frozenset({"image/heic", "image/heic-sequence"}),
    "heif": frozenset({"image/heif", "image/heif-sequence"}),
    "avif": frozenset({"image/avif", "image/avif-sequence"}),
    "png": frozenset({"image/png"}),
    "webp": frozenset({"image/webp"}),
    "gif": frozenset({"image/gif"}),
    "tiff": frozenset({"image/tiff", "image/x-tiff"}),
}
_SIGNATURE_PREFIX_BYTES = 64

IntegrityClassification = Literal["healthy", "warning", "malformed", "hash_only"]
DetectedFormat = Literal["jpeg", "heic", "heif", "avif", "png", "webp", "gif", "tiff", "unknown"]


def detect_file_format(prefix: bytes) -> DetectedFormat:
    """Identify supported containers from a small content prefix."""

    if prefix.startswith(b"\xff\xd8"):
        return "jpeg"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return "webp"
    if prefix.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if prefix.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if len(prefix) >= 12 and prefix[4:8] == b"ftyp":
        brands = {prefix[8:12]}
        brands.update(prefix[offset : offset + 4] for offset in range(16, len(prefix) - 3, 4))
        if brands & {b"avif", b"avis"}:
            return "avif"
        if brands & {b"heic", b"heix", b"hevc", b"hevx"}:
            return "heic"
        if brands & {b"mif1", b"msf1", b"heim", b"heis"}:
            return "heif"
    return "unknown"


def format_matches_mime(detected_format: DetectedFormat, mime_type: str | None) -> bool | None:
    """Compare known content identity with a known declared image MIME type."""

    declared = (mime_type or "").lower().split(";", 1)[0].strip()
    if detected_format == "unknown" or not declared.startswith("image/"):
        return None
    expected = FORMAT_MIME_TYPES.get(detected_format)
    return declared in expected if expected is not None else None


def decode_immich_sha1(value: str | None) -> bytes | None:
    """Decode a recognized hexadecimal or base64 SHA-1 value from Immich."""

    if not value:
        return None
    candidate = value.strip()
    if len(candidate) == 40:
        try:
            decoded = bytes.fromhex(candidate)
        except ValueError:
            pass
        else:
            return decoded if len(decoded) == 20 else None

    padded = candidate + "=" * (-len(candidate) % 4)
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    return decoded if len(decoded) == 20 else None


@dataclass(frozen=True, slots=True)
class FileIntegrityResult:
    """Final immutable facts produced from one complete byte stream."""

    analyzer_version: int
    byte_size: int
    sha1_hex: str
    sha256_hex: str
    detected_format: DetectedFormat
    format_matches_declared: bool | None
    classification: IntegrityClassification
    structurally_valid: bool | None
    container_valid: bool | None
    decode_supported: bool
    decode_valid: bool | None
    jpeg_eoi_offset: int | None
    trailing_byte_count: int
    immich_checksum_match: bool | None
    issues: tuple[str, ...]


class JpegStructureAnalyzer:
    """Validate JPEG marker structure without retaining segment or pixel data."""

    _STANDALONE_MARKERS = frozenset({0x01, *range(0xD0, 0xD9)})

    def __init__(self) -> None:
        self._offset = 0
        self._state = "soi_ff"
        self._segment_marker: int | None = None
        self._segment_remaining = 0
        self._issues: list[str] = []
        self._finished = False
        self._eoi_offset: int | None = None
        self._trailing_bytes = 0

    def _issue(self, code: str) -> None:
        if code not in self._issues:
            self._issues.append(code)

    def update(self, chunk: bytes) -> None:
        for value in chunk:
            self._offset += 1
            if self._finished:
                self._trailing_bytes += 1
                continue

            if self._state == "soi_ff":
                if value != 0xFF:
                    self._issue("jpeg_missing_soi")
                    self._state = "invalid"
                else:
                    self._state = "soi_code"
                continue

            if self._state == "soi_code":
                if value != 0xD8:
                    self._issue("jpeg_missing_soi")
                    self._state = "invalid"
                else:
                    self._state = "marker_ff"
                continue

            if self._state == "invalid":
                continue

            if self._state == "marker_ff":
                if value != 0xFF:
                    self._issue("jpeg_unexpected_data_between_markers")
                    self._state = "invalid"
                else:
                    self._state = "marker_code"
                continue

            if self._state == "marker_code":
                if value == 0xFF:
                    continue
                self._consume_marker(value)
                continue

            if self._state == "length_high":
                self._segment_remaining = value << 8
                self._state = "length_low"
                continue

            if self._state == "length_low":
                self._segment_remaining |= value
                if self._segment_remaining < 2:
                    self._issue("jpeg_invalid_segment_length")
                    self._state = "invalid"
                    continue
                self._segment_remaining -= 2
                if self._segment_remaining:
                    self._state = "segment_data"
                else:
                    self._finish_segment()
                continue

            if self._state == "segment_data":
                self._segment_remaining -= 1
                if self._segment_remaining == 0:
                    self._finish_segment()
                continue

            if self._state == "scan":
                if value == 0xFF:
                    self._state = "scan_marker"
                continue

            if self._state == "scan_marker":
                if value == 0x00 or 0xD0 <= value <= 0xD7:
                    self._state = "scan"
                elif value == 0xFF:
                    pass
                else:
                    self._consume_marker(value)

    def _consume_marker(self, marker: int) -> None:
        if marker == 0x00:
            self._issue("jpeg_invalid_marker")
            self._state = "invalid"
        elif marker == 0xD9:
            self._finished = True
            self._eoi_offset = self._offset
            self._state = "finished"
        elif marker == 0xD8:
            self._issue("jpeg_unexpected_soi")
            self._state = "invalid"
        elif marker in self._STANDALONE_MARKERS:
            self._state = "marker_ff"
        else:
            self._segment_marker = marker
            self._segment_remaining = 0
            self._state = "length_high"

    def _finish_segment(self) -> None:
        self._state = "scan" if self._segment_marker == 0xDA else "marker_ff"
        self._segment_marker = None

    def finalize(self) -> tuple[bool, int | None, int, tuple[str, ...]]:
        if not self._finished:
            if self._state in {"soi_ff", "soi_code"}:
                self._issue("jpeg_missing_soi")
            if self._state in {"length_high", "length_low", "segment_data"}:
                self._issue("jpeg_truncated_segment")
            if "jpeg_missing_soi" not in self._issues:
                self._issue("jpeg_missing_eoi")
        return (
            self._finished and not self._issues,
            self._eoi_offset,
            self._trailing_bytes,
            tuple(self._issues),
        )


class FileIntegrityAnalyzer:
    """Hash bytes and optionally inspect JPEG structure one chunk at a time."""

    def __init__(self, declared_mime_type: str | None, immich_checksum: str | None) -> None:
        self._declared_mime_type = declared_mime_type
        self._immich_sha1 = decode_immich_sha1(immich_checksum)
        self._sha1 = hashlib.sha1(usedforsecurity=False)
        self._sha256 = hashlib.sha256()
        self._size = 0
        self._prefix = bytearray()
        self._jpeg: JpegStructureAnalyzer | None = None

    @property
    def byte_size(self) -> int:
        return self._size

    def update(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._sha1.update(chunk)
        self._sha256.update(chunk)
        self._size += len(chunk)

        needed = max(0, _SIGNATURE_PREFIX_BYTES - len(self._prefix))
        if needed:
            self._prefix.extend(chunk[:needed])

        if self._jpeg is not None:
            self._jpeg.update(chunk)
            return

        if len(self._prefix) >= 2 and self._prefix[:2] == b"\xff\xd8":
            self._jpeg = JpegStructureAnalyzer()
            prefix_from_chunk = min(needed, len(chunk))
            replayed_prefix = bytes(self._prefix)
            self._jpeg.update(replayed_prefix)
            self._jpeg.update(chunk[prefix_from_chunk:])

    def finalize(self) -> FileIntegrityResult:
        sha1_digest = self._sha1.digest()
        checksum_match = (
            None if self._immich_sha1 is None else self._immich_sha1 == sha1_digest
        )
        issues: list[str] = []
        structurally_valid: bool | None = None
        eoi_offset: int | None = None
        trailing_bytes = 0
        detected_format = detect_file_format(bytes(self._prefix))
        mime_matches = format_matches_mime(detected_format, self._declared_mime_type)
        container_valid: bool | None = None
        decode_supported = False
        decode_valid: bool | None = None

        if self._jpeg is not None:
            structurally_valid, eoi_offset, trailing_bytes, jpeg_issues = self._jpeg.finalize()
            container_valid = structurally_valid
            issues.extend(jpeg_issues)
        if mime_matches is False:
            issues.append("mime_format_mismatch")
        if checksum_match is False:
            issues.append("immich_checksum_mismatch")

        if structurally_valid is False:
            classification: IntegrityClassification = "malformed"
        elif trailing_bytes or checksum_match is False or mime_matches is False:
            classification = "warning"
        elif structurally_valid is True:
            classification = "healthy"
        else:
            classification = "hash_only"

        return FileIntegrityResult(
            analyzer_version=ANALYZER_VERSION,
            byte_size=self._size,
            sha1_hex=sha1_digest.hex(),
            sha256_hex=self._sha256.hexdigest(),
            detected_format=detected_format,
            format_matches_declared=mime_matches,
            classification=classification,
            structurally_valid=structurally_valid,
            container_valid=container_valid,
            decode_supported=decode_supported,
            decode_valid=decode_valid,
            jpeg_eoi_offset=eoi_offset,
            trailing_byte_count=trailing_bytes,
            immich_checksum_match=checksum_match,
            issues=tuple(dict.fromkeys(issues)),
        )

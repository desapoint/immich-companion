"""Lightweight transparency classification for bounded similarity evidence."""

from __future__ import annotations

from pathlib import Path

from companion.immich import ImmichAsset
from companion.similarity_bounded_state import SourceAlphaState

OPAQUE_MIME_TYPES = frozenset({"image/jpeg", "image/jpg"})
OPAQUE_SUFFIXES = frozenset({".jpg", ".jpeg", ".jpe"})
ALPHA_CAPABLE_MIME_TYPES = frozenset(
    {
        "image/png",
        "image/webp",
        "image/gif",
        "image/tiff",
        "image/avif",
        "image/heic",
        "image/heif",
    }
)
ALPHA_CAPABLE_SUFFIXES = frozenset(
    {".png", ".webp", ".gif", ".tif", ".tiff", ".avif", ".heic", ".heif"}
)


def source_format_family(source: ImmichAsset) -> str | None:
    mime = (source.original_mime_type or "").split(";", 1)[0].strip().lower()
    suffix = Path(source.original_file_name).suffix.lower()
    if mime in {"image/jpeg", "image/jpg"} or suffix in OPAQUE_SUFFIXES:
        return "jpeg"
    if mime == "image/png" or suffix == ".png":
        return "png"
    if mime == "image/webp" or suffix == ".webp":
        return "webp"
    if mime == "image/gif" or suffix == ".gif":
        return "gif"
    if mime in {"image/tiff", "image/tif"} or suffix in {".tif", ".tiff"}:
        return "tiff"
    if mime in {"image/avif", "image/heic", "image/heif"} or suffix in {
        ".avif", ".heic", ".heif"
    }:
        return "heif"
    return None


def source_can_have_alpha(source: ImmichAsset) -> bool:
    mime = (source.original_mime_type or "").split(";", 1)[0].strip().lower()
    suffix = Path(source.original_file_name).suffix.lower()
    return mime in ALPHA_CAPABLE_MIME_TYPES or suffix in ALPHA_CAPABLE_SUFFIXES


def bounded_media_format(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if content.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "heif"
    return None



def _complete_iso_bmff_box(content: bytes, wanted_type: bytes) -> bytes | None:
    """Return a complete top-level ISO-BMFF box when it is present in this bounded prefix."""

    offset = 0
    while offset + 8 <= len(content):
        size = int.from_bytes(content[offset : offset + 4], "big")
        box_type = content[offset + 4 : offset + 8]
        header_size = 8
        if size == 1:
            if offset + 16 > len(content):
                return None
            size = int.from_bytes(content[offset + 8 : offset + 16], "big")
            header_size = 16
        elif size == 0:
            # A zero-sized box extends to EOF. A bounded prefix cannot prove it is complete.
            return None
        if size < header_size:
            return None
        end = offset + size
        if end > len(content):
            return None
        if box_type == wanted_type:
            return content[offset:end]
        offset = end
    return None


def _inspect_heif_alpha(content: bytes) -> SourceAlphaState:
    """Classify standards-based HEIF/HEIC/AVIF alpha from a complete metadata box."""

    meta = _complete_iso_bmff_box(content, b"meta")
    if meta is None:
        return "unknown_alpha"
    lowered = meta.lower()
    # HEIF/HEIC and AVIF represent alpha as an auxiliary image. These are the
    # standardized auxiliary type strings used by HEVC and AV1 image items.
    alpha_markers = (
        b"urn:mpeg:hevc:2015:auxid:1",
        b"urn:mpeg:mpegb:cicp:systems:auxiliary:alpha",
        b"auxiliary:alpha",
    )
    if any(marker in lowered for marker in alpha_markers):
        return "confirmed_alpha"
    # The complete item metadata is present and declares no alpha auxiliary image.
    return "confirmed_opaque"


def inspect_bounded_alpha(content: bytes) -> SourceAlphaState:
    """Inspect encoded metadata only; never materialize the image raster."""

    family = bounded_media_format(content)
    if family == "jpeg":
        return "confirmed_opaque"
    if family == "png":
        if len(content) < 33 or content[12:16] != b"IHDR":
            return "unknown_alpha"
        color_type = content[25]
        if color_type in {4, 6}:
            return "confirmed_alpha"
        offset = 8
        while offset + 12 <= len(content):
            length = int.from_bytes(content[offset : offset + 4], "big")
            chunk_type = content[offset + 4 : offset + 8]
            if chunk_type == b"tRNS":
                return "confirmed_alpha"
            if chunk_type == b"IDAT":
                return "confirmed_opaque"
            offset += 12 + length
        return "unknown_alpha"
    if family == "webp":
        if b"ALPH" in content:
            return "confirmed_alpha"
        vp8x = content.find(b"VP8X")
        if vp8x >= 0 and vp8x + 9 <= len(content):
            return "confirmed_alpha" if content[vp8x + 8] & 0x10 else "confirmed_opaque"
        return "unknown_alpha"
    if family == "gif":
        offset = 0
        marker = b"\x21\xf9\x04"
        while True:
            offset = content.find(marker, offset)
            if offset < 0:
                return "unknown_alpha"
            if offset + 4 < len(content) and content[offset + 3] & 0x01:
                return "confirmed_alpha"
            offset += len(marker)
    if family == "heif":
        return _inspect_heif_alpha(content)
    return "unknown_alpha"


def classify_source_alpha(
    source: ImmichAsset,
    *,
    bounded_content: bytes | None = None,
) -> SourceAlphaState:
    """Classify source alpha without decoding an oversized original raster."""

    family = source_format_family(source)
    if family == "jpeg":
        return "confirmed_opaque"
    if bounded_content:
        bounded_state = inspect_bounded_alpha(bounded_content)
        bounded_family = bounded_media_format(bounded_content)
        if bounded_state == "confirmed_alpha":
            return "confirmed_alpha"
        # A same-family generated rendition can prove an alpha-capable source is
        # opaque without treating a JPEG-flattened preview as equivalent proof.
        if bounded_state == "confirmed_opaque" and bounded_family == family:
            return "confirmed_opaque"
    return "unknown_alpha"


def bounded_rendition_is_detail_safe(
    source_state: SourceAlphaState,
    content: bytes,
) -> bool:
    """Reject flattened/uncertain bounded media as detailed alpha evidence."""

    rendition_state = inspect_bounded_alpha(content)
    if source_state == "confirmed_opaque":
        return rendition_state != "confirmed_alpha"
    if source_state == "confirmed_alpha":
        return rendition_state == "confirmed_alpha"
    return rendition_state == "confirmed_alpha"

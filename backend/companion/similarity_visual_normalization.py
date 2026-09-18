"""Single libvips normalization source for all Appearance similarity evidence."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from uuid import UUID

import pyvips

from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset
from companion.task_coordinator import TaskContext

MAX_VISUAL_DIMENSION = 2048
DEFAULT_VISUAL_SOURCE_MAX_BYTES = 128 * 1024 * 1024
VISUAL_NORMALIZATION_VERSION = 4
PYVIPS_VERSION = getattr(pyvips, "__version__", "unknown")
LIBVIPS_VERSION = ".".join(str(pyvips.version(part)) for part in range(3))
VISUAL_NORMALIZATION_FINGERPRINT = hashlib.sha256(
    (
        f"visual-normalization-v{VISUAL_NORMALIZATION_VERSION}:"
        f"engine=pyvips-{PYVIPS_VERSION}:libvips-{LIBVIPS_VERSION}:"
        f"max-dimension={MAX_VISUAL_DIMENSION}:"
        f"source-max-bytes={DEFAULT_VISUAL_SOURCE_MAX_BYTES}:"
        "autorotate=on:resize=thumbnail-down:"
        "raw-loader=explicit-dcraw-or-magick:"
        "pixel-output=raw-srgb-uchar"
    ).encode(),
    usedforsecurity=False,
).hexdigest()

# These are one-shot normalization pipelines. Retaining libvips operation graphs
# between assets wastes memory and does not improve cache reuse for this workload.
pyvips.cache_set_max(0)

VisualSourceKind = Literal["original", "preview"]
VisualPixelMode = Literal["RGB", "RGBA"]

CAMERA_RAW_SUFFIXES = frozenset(
    {
        ".3fr",
        ".arw",
        ".cr2",
        ".cr3",
        ".dcr",
        ".dng",
        ".erf",
        ".fff",
        ".iiq",
        ".k25",
        ".kdc",
        ".mef",
        ".mos",
        ".mrw",
        ".nef",
        ".nrw",
        ".orf",
        ".pef",
        ".raf",
        ".raw",
        ".rw2",
        ".rwl",
        ".sr2",
        ".srf",
        ".srw",
        ".x3f",
    }
)
CAMERA_RAW_MIME_TOKENS = (
    "camera-raw",
    "digital-negative",
    "x-raw",
    "dng",
    "cr2",
    "cr3",
    "nef",
    "nrw",
    "arw",
    "raf",
    "rw2",
    "orf",
    "pef",
    "srw",
    "x3f",
)


class VisualNormalizationError(ValueError):
    """No safe visual representation could be normalized."""


@dataclass(frozen=True, slots=True)
class NormalizedVisualImage:
    """Canonical decoded Appearance pixels shared by search and localized detail."""

    pixel_bytes: bytes
    pixel_mode: VisualPixelMode
    media_sha256: str
    source_kind: VisualSourceKind
    width: int
    height: int
    source_width: int | None
    source_height: int | None
    resized: bool
    has_alpha: bool
    source_bytes: int

    @property
    def search_origin(self) -> str:
        return self.source_kind

    @property
    def detail_origin(self) -> str:
        return "original" if self.source_kind == "original" else "preview_fallback"


def source_is_camera_raw(asset: ImmichAsset) -> bool:
    """Identify camera RAW sources so libvips never mistakes DNG for ordinary TIFF."""

    suffix = Path(getattr(asset, "original_file_name", "") or "").suffix.lower()
    mime = (getattr(asset, "original_mime_type", "") or "").lower()
    return suffix in CAMERA_RAW_SUFFIXES or any(token in mime for token in CAMERA_RAW_MIME_TOKENS)


def _safe_suffix(asset: ImmichAsset) -> str:
    filename = getattr(asset, "original_file_name", "") or ""
    suffix = Path(filename).suffix.lower()
    if not suffix or len(suffix) > 16 or any(character in suffix for character in "/\\"):
        return ".img"
    return suffix


def _canonical_vips_image(
    *,
    path: Path | None = None,
    content: bytes | None = None,
    raw_source: bool = False,
) -> tuple[bytes, VisualPixelMode, str, int, int, bool]:
    """Use libvips to autorotate and expose canonical pixels without re-encoding."""

    if (path is None) == (content is None):
        raise ValueError("Provide exactly one visual source")
    try:
        options = {
            "height": MAX_VISUAL_DIMENSION,
            "size": "down",
            "no_rotate": False,
            "fail_on": "error",
        }
        if path is not None:
            if raw_source:
                if pyvips.type_find("VipsOperation", "dcrawload"):
                    image = pyvips.Image.dcrawload(
                        str(path),
                        access="sequential",
                        fail_on="error",
                    )
                elif pyvips.type_find("VipsOperation", "magickload"):
                    image = pyvips.Image.magickload(
                        str(path),
                        access="sequential",
                    )
                else:
                    raise VisualNormalizationError("camera RAW loader is unavailable")
                image = image.autorot()
                scale = min(
                    1.0,
                    MAX_VISUAL_DIMENSION / image.width,
                    MAX_VISUAL_DIMENSION / image.height,
                )
                if scale < 1.0:
                    image = image.resize(scale, kernel="lanczos3")
            else:
                image = pyvips.Image.thumbnail(str(path), MAX_VISUAL_DIMENSION, **options)
        else:
            assert content is not None
            if not content:
                raise VisualNormalizationError("visual source is empty")
            image = pyvips.Image.thumbnail_buffer(
                content,
                MAX_VISUAL_DIMENSION,
                **options,
            )

        if image.width < 1 or image.height < 1:
            raise VisualNormalizationError("visual source has invalid dimensions")

        # libvips keeps extra bands such as alpha while colourspace() converts
        # the visible colour channels. Export the bounded sRGB raster directly
        # instead of JPEG/PNG encoding it only for Pillow to decode it again.
        image = image.colourspace("srgb")
        if image.format != "uchar":
            image = image.cast("uchar")
        has_alpha = bool(image.hasalpha())
        pixel_mode: VisualPixelMode = "RGBA" if has_alpha else "RGB"
        expected_bands = 4 if has_alpha else 3
        if image.bands != expected_bands:
            raise VisualNormalizationError(
                f"normalized visual has unsupported band count: {image.bands}"
            )
        pixel_bytes = bytes(image.write_to_memory())
        expected_bytes = image.width * image.height * expected_bands
        if len(pixel_bytes) != expected_bytes:
            raise VisualNormalizationError(
                "normalized visual pixel buffer has incompatible dimensions"
            )
        digest = hashlib.sha256(usedforsecurity=False)
        digest.update(
            f"raw-srgb-v1:{pixel_mode}:{image.width}x{image.height}\n".encode()
        )
        digest.update(pixel_bytes)
        return (
            pixel_bytes,
            pixel_mode,
            digest.hexdigest(),
            image.width,
            image.height,
            has_alpha,
        )
    except VisualNormalizationError:
        raise
    except pyvips.Error as error:
        raise VisualNormalizationError(f"visual_source_decode_failed: {error}") from error


class SimilarityVisualNormalizer:
    """Normalize originals with libvips; use an Immich preview only as fallback."""

    def __init__(
        self,
        immich: ImmichApiClient,
        *,
        max_bytes: int = DEFAULT_VISUAL_SOURCE_MAX_BYTES,
        cache_path: Path | None = None,
        fetch_slots: asyncio.Semaphore | None = None,
        decode_slots: asyncio.Semaphore | None = None,
    ) -> None:
        if max_bytes < 1:
            raise ValueError("Visual source byte limit must be positive")
        self._immich = immich
        self._max_bytes = max_bytes
        self._cache_path = cache_path
        self._fetch_slots = fetch_slots
        self._decode_slots = decode_slots

    async def _download_original(
        self,
        context: TaskContext,
        asset_id: UUID,
        asset: ImmichAsset,
    ) -> tuple[Path, int]:
        """Spool encoded original bytes without ever materializing the raster in Python."""

        if asset.file_size_bytes is not None and asset.file_size_bytes > self._max_bytes:
            raise VisualNormalizationError("original exceeds visual source size limit")

        temporary_path: Path | None = None
        total = 0
        try:
            with NamedTemporaryFile(
                prefix="immich-companion-visual-",
                suffix=_safe_suffix(asset),
                dir=self._cache_path,
                delete=False,
            ) as spool:
                temporary_path = Path(spool.name)
                async with self._immich.stream_original(asset_id) as media:
                    if (
                        media.content_length is not None
                        and media.content_length > self._max_bytes
                    ):
                        raise VisualNormalizationError(
                            "original exceeds visual source size limit"
                        )
                    async for chunk in media.chunks:
                        await context.ensure_active()
                        total += len(chunk)
                        if total > self._max_bytes:
                            raise VisualNormalizationError(
                                "original exceeds visual source size limit"
                            )
                        spool.write(chunk)
            assert temporary_path is not None
            return temporary_path, total
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    async def _run_vips(
        self,
        *,
        path: Path | None = None,
        content: bytes | None = None,
        raw_source: bool = False,
    ) -> tuple[bytes, VisualPixelMode, str, int, int, bool]:
        if self._decode_slots is None:
            return await asyncio.to_thread(
                _canonical_vips_image,
                path=path,
                content=content,
                raw_source=raw_source,
            )
        async with self._decode_slots:
            return await asyncio.to_thread(
                _canonical_vips_image,
                path=path,
                content=content,
                raw_source=raw_source,
            )

    @staticmethod
    def _was_resized(asset: ImmichAsset, width: int, height: int) -> bool:
        if not asset.width or not asset.height:
            return False
        return width < asset.width or height < asset.height

    async def _normalize_original(
        self,
        context: TaskContext,
        asset_id: UUID,
        asset: ImmichAsset,
    ) -> NormalizedVisualImage:
        if self._fetch_slots is None:
            path, source_bytes = await self._download_original(context, asset_id, asset)
        else:
            async with self._fetch_slots:
                path, source_bytes = await self._download_original(
                    context,
                    asset_id,
                    asset,
                )

        try:
            pixel_bytes, pixel_mode, media_sha256, width, height, has_alpha = await self._run_vips(
                path=path,
                raw_source=source_is_camera_raw(asset),
            )
        finally:
            path.unlink(missing_ok=True)

        return NormalizedVisualImage(
            pixel_bytes=pixel_bytes,
            pixel_mode=pixel_mode,
            media_sha256=media_sha256,
            source_kind="original",
            width=width,
            height=height,
            source_width=asset.width,
            source_height=asset.height,
            resized=self._was_resized(asset, width, height),
            has_alpha=has_alpha,
            source_bytes=source_bytes,
        )

    async def _preview_content(self, asset_id: UUID) -> bytes:
        getter = getattr(self._immich, "get_bounded_preview", None)
        if getter is None:
            raise VisualNormalizationError("Immich preview endpoint is unavailable")
        if self._fetch_slots is None:
            return await getter(asset_id, max_bytes=self._max_bytes)
        async with self._fetch_slots:
            return await getter(asset_id, max_bytes=self._max_bytes)

    async def _normalize_preview(
        self,
        asset_id: UUID,
        asset: ImmichAsset,
    ) -> NormalizedVisualImage:
        content = await self._preview_content(asset_id)
        pixel_bytes, pixel_mode, media_sha256, width, height, has_alpha = await self._run_vips(
            content=content
        )
        return NormalizedVisualImage(
            pixel_bytes=pixel_bytes,
            pixel_mode=pixel_mode,
            media_sha256=media_sha256,
            source_kind="preview",
            width=width,
            height=height,
            source_width=asset.width,
            source_height=asset.height,
            resized=self._was_resized(asset, width, height),
            has_alpha=has_alpha,
            source_bytes=len(content),
        )

    async def normalize(
        self,
        context: TaskContext,
        asset_id: UUID,
        asset: ImmichAsset,
    ) -> NormalizedVisualImage:
        """Normalize the original with libvips, falling back only to Immich preview."""

        await context.ensure_active()
        errors: list[str] = []

        try:
            return await self._normalize_original(context, asset_id, asset)
        except (ImmichApiError, OSError, VisualNormalizationError) as error:
            errors.append(f"original: {error}")

        try:
            return await self._normalize_preview(asset_id, asset)
        except (ImmichApiError, OSError, VisualNormalizationError) as error:
            errors.append(f"preview: {error}")

        await context.ensure_active()
        raise VisualNormalizationError(
            "visual_normalization_unavailable: " + "; ".join(errors)
        )

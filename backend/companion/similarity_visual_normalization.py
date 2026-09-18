"""Single bounded visual source for all Appearance similarity evidence."""

from __future__ import annotations

import asyncio
import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Literal
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError

from companion.image_decode import MAX_DECODED_PIXELS
from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset
from companion.task_coordinator import TaskContext

MAX_VISUAL_DIMENSION = 6000
DEFAULT_VISUAL_SOURCE_MAX_BYTES = 128 * 1024 * 1024
VISUAL_NORMALIZATION_VERSION = 1
VISUAL_NORMALIZATION_FINGERPRINT = hashlib.sha256(
    (
        f"visual-normalization-v{VISUAL_NORMALIZATION_VERSION}:"
        f"max-dimension={MAX_VISUAL_DIMENSION}:"
        f"decode-pixels={MAX_DECODED_PIXELS}"
    ).encode(),
    usedforsecurity=False,
).hexdigest()

VisualSourceKind = Literal["original", "bounded_fullsize", "bounded_preview"]


class VisualNormalizationError(ValueError):
    """No bounded visual representation could be normalized safely."""


@dataclass(frozen=True, slots=True)
class NormalizedVisualImage:
    """Canonical Appearance input shared by search and localized detail."""

    content: bytes
    source_kind: VisualSourceKind
    width: int
    height: int
    source_width: int | None
    source_height: int | None
    resized: bool
    has_alpha: bool
    source_bytes: int

    @property
    def media_sha256(self) -> str:
        return hashlib.sha256(self.content, usedforsecurity=False).hexdigest()

    @property
    def search_origin(self) -> str:
        return "original" if self.source_kind == "original" else "bounded"

    @property
    def detail_origin(self) -> str:
        if self.source_kind == "original":
            return "original"
        if self.source_kind == "bounded_fullsize":
            return "bounded_fullsize"
        return "bounded_preview"


def source_requires_bounded_visual(asset: ImmichAsset) -> bool:
    """Avoid original decode when dimensions are unknown or exceed the visual box."""

    return bool(
        not asset.width
        or not asset.height
        or asset.width > MAX_VISUAL_DIMENSION
        or asset.height > MAX_VISUAL_DIMENSION
    )


def _canonical_content(content: bytes) -> tuple[bytes, int, int, bool, bool]:
    """Orient and cap one safely decodable representation to the canonical visual box."""

    if not content:
        raise VisualNormalizationError("visual source is empty")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.width * source.height > MAX_DECODED_PIXELS:
                    raise VisualNormalizationError("visual_source_decode_limit_exceeded")
                source.load()
                image = ImageOps.exif_transpose(source)
                original_size = image.size
                if image.width > MAX_VISUAL_DIMENSION or image.height > MAX_VISUAL_DIMENSION:
                    image.thumbnail(
                        (MAX_VISUAL_DIMENSION, MAX_VISUAL_DIMENSION),
                        Image.Resampling.LANCZOS,
                    )
                has_alpha = "A" in image.getbands() or "transparency" in image.info
                output = BytesIO()
                if has_alpha:
                    image.convert("RGBA").save(output, format="PNG")
                else:
                    image.convert("RGB").save(
                        output,
                        format="JPEG",
                        quality=95,
                        subsampling=0,
                        optimize=False,
                    )
                return (
                    output.getvalue(),
                    image.width,
                    image.height,
                    has_alpha,
                    image.size != original_size,
                )
    except VisualNormalizationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as error:
        raise VisualNormalizationError(f"visual_source_decode_failed: {error}") from error


class SimilarityVisualNormalizer:
    """Fetch one safe source, then produce the canonical visual representation once."""

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

    async def _original_content(
        self,
        context: TaskContext,
        asset_id: UUID,
    ) -> bytes:
        with SpooledTemporaryFile(
            max_size=4 * 1024 * 1024,
            dir=self._cache_path,
            suffix=".tmp",
        ) as spool:
            total = 0
            async with self._immich.stream_original(asset_id) as media:
                if media.content_length is not None and media.content_length > self._max_bytes:
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
            spool.seek(0)
            return spool.read()

    async def _normalize_content(
        self,
        content: bytes,
        source_kind: VisualSourceKind,
        asset: ImmichAsset,
    ) -> NormalizedVisualImage:
        if self._decode_slots is None:
            normalized, width, height, has_alpha, resized = await asyncio.to_thread(
                _canonical_content,
                content,
            )
        else:
            async with self._decode_slots:
                normalized, width, height, has_alpha, resized = await asyncio.to_thread(
                    _canonical_content,
                    content,
                )
        return NormalizedVisualImage(
            content=normalized,
            source_kind=source_kind,
            width=width,
            height=height,
            source_width=asset.width,
            source_height=asset.height,
            resized=resized,
            has_alpha=has_alpha,
            source_bytes=len(content),
        )

    async def normalize(
        self,
        context: TaskContext,
        asset_id: UUID,
        asset: ImmichAsset,
    ) -> NormalizedVisualImage:
        """Return the only visual input search/detail are allowed to consume."""

        await context.ensure_active()
        errors: list[str] = []

        if not source_requires_bounded_visual(asset):
            try:
                if self._fetch_slots is None:
                    original = await self._original_content(context, asset_id)
                else:
                    async with self._fetch_slots:
                        original = await self._original_content(context, asset_id)
                return await self._normalize_content(original, "original", asset)
            except (ImmichApiError, OSError, VisualNormalizationError) as error:
                errors.append(f"original: {error}")

        for source_kind, getter_name in (
            ("bounded_fullsize", "get_bounded_fullsize"),
            ("bounded_preview", "get_bounded_preview"),
        ):
            getter = getattr(self._immich, getter_name, None)
            if getter is None:
                continue
            try:
                if self._fetch_slots is None:
                    content = await getter(asset_id, max_bytes=self._max_bytes)
                else:
                    async with self._fetch_slots:
                        content = await getter(asset_id, max_bytes=self._max_bytes)
                return await self._normalize_content(content, source_kind, asset)
            except (ImmichApiError, OSError, VisualNormalizationError) as error:
                errors.append(f"{source_kind}: {error}")

        await context.ensure_active()
        raise VisualNormalizationError(
            "visual_normalization_unavailable: " + "; ".join(errors)
        )

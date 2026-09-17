"""Durable on-demand detail evidence for similarity candidate validation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from tempfile import SpooledTemporaryFile
from time import perf_counter
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, delete, or_, select

from companion.database import Database
from companion.immich import ImmichApiError, ImmichAsset, ImmichClient
from companion.integrity_limits import MAX_DECODED_PIXELS
from companion.similarity_bounded_state import (
    BOUNDED_CAPABILITY_VERSION,
    BOUNDED_POLICY_FINGERPRINT,
    AssetSimilarityBoundedStateRecord,
    SourceAlphaState,
)
from companion.similarity_detail_features import (
    DETAIL_FEATURE_VERSION,
    DetailFeature,
    compare_detail_features,
    extract_detail_feature,
)
from companion.similarity_search_features import (
    MAX_SEARCH_PREVIEW_BYTES,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_transparency import bounded_rendition_is_detail_safe
from companion.tasks import PermanentTaskError, RetryableTaskError, TaskContext
from companion.visual_evidence import decode_image_with_limit, detect_file_format

logger = logging.getLogger("uvicorn.error")
DETAIL_STREAM_SPOOL_BYTES = 4 * 1024 * 1024

DetailEvidenceOrigin = Literal[
    "original",
    "transcoded_fullsize",
    "preview_fallback",
    "bounded_fullsize",
    "bounded_preview",
]
DetailEvidenceSource = Literal["original", "transcoded", "preview"]


def _source_exceeds_decode_limit(asset: ImmichAsset) -> bool:
    width = asset.width
    height = asset.height
    return bool(width and height and width * height > MAX_DECODED_PIXELS)


def _bounded_failure_is_retryable(reason: str) -> bool:
    lowered = reason.lower()
    return any(
        marker in lowered
        for marker in (
            "http 429",
            "http 500",
            "http 502",
            "http 503",
            "http 504",
            "timeout",
            "temporar",
            "connection",
            "provider",
            "network",
        )
    )


@dataclass(slots=True, frozen=True)
class StoredDetailDiagnostics:
    structural_similarity: float
    perceptual_similarity: float
    color_similarity: float
    detail_similarity: float
    dimensions_equal: bool
    width: int
    height: int
    source: DetailEvidenceSource
    reduced_fidelity: bool


class AssetSimilarityDetailFeatureRecord:
    """SQLAlchemy model shape is injected dynamically below for local ownership."""


from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from companion.models import Base


class AssetSimilarityDetailFeatureRecord(Base):
    __tablename__ = "asset_similarity_detail_feature"
    __table_args__ = (
        Index("ix_similarity_detail_asset", "asset_id"),
        Index("ix_similarity_detail_source", "source_identity"),
    )

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    source_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_version: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    structural_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    perceptual_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    color_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    detail_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    has_alpha: Mapped[bool] = mapped_column(Boolean, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    reduced_fidelity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SimilarityDetailRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_current_many(
        self, asset_ids: list[UUID]
    ) -> dict[UUID, AssetSimilarityDetailFeatureRecord]:
        if not asset_ids:
            return {}
        async with self._database.session() as session:
            result = await session.execute(
                select(AssetSimilarityDetailFeatureRecord).where(
                    AssetSimilarityDetailFeatureRecord.asset_id.in_(asset_ids),
                    AssetSimilarityDetailFeatureRecord.feature_version == DETAIL_FEATURE_VERSION,
                )
            )
            return {row.asset_id: row for row in result.scalars().all()}

    async def get_current_unavailable_many(
        self,
        asset_ids: list[UUID],
        search_records: dict[UUID, AssetSimilaritySearchFeatureRecord],
    ) -> set[UUID]:
        if not asset_ids:
            return set()
        async with self._database.session() as session:
            result = await session.execute(
                select(AssetSimilarityBoundedStateRecord).where(
                    AssetSimilarityBoundedStateRecord.asset_id.in_(asset_ids),
                    AssetSimilarityBoundedStateRecord.model_version
                    == search_records[next(iter(search_records))].model_version,
                    AssetSimilarityBoundedStateRecord.feature_version
                    == search_records[next(iter(search_records))].feature_version,
                    AssetSimilarityBoundedStateRecord.config_fingerprint
                    == search_records[next(iter(search_records))].config_fingerprint,
                    AssetSimilarityBoundedStateRecord.capability_version
                    == BOUNDED_CAPABILITY_VERSION,
                    AssetSimilarityBoundedStateRecord.policy_fingerprint
                    == BOUNDED_POLICY_FINGERPRINT,
                    AssetSimilarityBoundedStateRecord.detail_status == "unavailable",
                    AssetSimilarityBoundedStateRecord.detail_feature_version
                    == DETAIL_FEATURE_VERSION,
                )
            )
            unavailable: set[UUID] = set()
            for row in result.scalars().all():
                search = search_records.get(row.asset_id)
                if search and row.detail_source_identity == search.source_identity:
                    unavailable.add(row.asset_id)
            return unavailable

    async def source_alpha_state(
        self, asset_id: UUID, source_identity: str
    ) -> SourceAlphaState | None:
        async with self._database.session() as session:
            result = await session.execute(
                select(AssetSimilarityBoundedStateRecord).where(
                    AssetSimilarityBoundedStateRecord.asset_id == asset_id,
                    AssetSimilarityBoundedStateRecord.source_identity == source_identity,
                )
            )
            row = result.scalar_one_or_none()
            return row.alpha_state if row else None

    async def mark_unavailable(
        self, source_identity: str, asset_id: UUID, reason: str
    ) -> bool:
        async with self._database.session() as session:
            async with session.begin():
                result = await session.execute(
                    select(AssetSimilarityBoundedStateRecord)
                    .where(AssetSimilarityBoundedStateRecord.asset_id == asset_id)
                    .with_for_update()
                )
                row = result.scalar_one_or_none()
                if row is None or row.source_identity != source_identity:
                    return False
                row.detail_status = "unavailable"
                row.detail_reason = reason
                row.detail_source_identity = source_identity
                row.detail_feature_version = DETAIL_FEATURE_VERSION
            return True

    async def save(
        self,
        source_identity: str,
        asset_id: UUID,
        feature: DetailFeature,
        origin: DetailEvidenceOrigin,
    ) -> bool:
        async with self._database.session() as session:
            async with session.begin():
                result = await session.execute(
                    select(AssetSimilarityBoundedStateRecord)
                    .where(AssetSimilarityBoundedStateRecord.asset_id == asset_id)
                    .with_for_update()
                )
                state = result.scalar_one_or_none()
                if state is None or state.source_identity != source_identity:
                    return False
                result = await session.execute(
                    select(AssetSimilarityDetailFeatureRecord)
                    .where(AssetSimilarityDetailFeatureRecord.asset_id == asset_id)
                    .with_for_update()
                )
                row = result.scalar_one_or_none()
                if row is None:
                    row = AssetSimilarityDetailFeatureRecord(asset_id=asset_id)
                    session.add(row)
                row.source_identity = source_identity
                row.feature_version = DETAIL_FEATURE_VERSION
                row.width = feature.width
                row.height = feature.height
                row.structural_blob = feature.structural_blob
                row.perceptual_blob = feature.perceptual_blob
                row.color_blob = feature.color_blob
                row.detail_blob = feature.detail_blob
                row.has_alpha = feature.has_alpha
                row.origin = origin
                row.reduced_fidelity = origin in {
                    "preview_fallback",
                    "bounded_fullsize",
                    "bounded_preview",
                }
                state.detail_status = "available"
                state.detail_reason = None
                state.detail_source_identity = source_identity
                state.detail_feature_version = DETAIL_FEATURE_VERSION
            return True

    async def diagnostics(
        self,
        reference_id: UUID,
        member_id: UUID,
    ) -> StoredDetailDiagnostics | None:
        rows = await self.get_current_many([reference_id, member_id])
        reference = rows.get(reference_id)
        member = rows.get(member_id)
        if reference is None or member is None:
            return None
        structural, perceptual, color, detail = compare_detail_features(reference, member)
        origins = {reference.origin, member.origin}
        if origins & {"preview_fallback", "bounded_preview", "bounded_fullsize"}:
            source: DetailEvidenceSource = "preview"
        elif "transcoded_fullsize" in origins:
            source = "transcoded"
        else:
            source = "original"
        return StoredDetailDiagnostics(
            structural_similarity=structural,
            perceptual_similarity=perceptual,
            color_similarity=color,
            detail_similarity=detail,
            dimensions_equal=(reference.width, reference.height) == (member.width, member.height),
            width=member.width,
            height=member.height,
            source=source,
            reduced_fidelity=reference.reduced_fidelity or member.reduced_fidelity,
        )


class SimilarityDetailMaintainer:
    def __init__(
        self,
        immich: ImmichClient,
        details: SimilarityDetailRepository,
        *,
        slots: int = 4,
        max_bytes: int = 64 * 1024 * 1024,
        spool_bytes: int = DETAIL_STREAM_SPOOL_BYTES,
    ) -> None:
        self._immich = immich
        self._details = details
        self._slots = asyncio.Semaphore(max(1, slots))
        self._max_bytes = max_bytes
        self._spool_bytes = spool_bytes
        self.counters: Counter[str] = Counter()

    async def _original_content(
        self, context: TaskContext, asset_id: UUID
    ) -> tuple[bytes | None, str | None]:
        with SpooledTemporaryFile(max_size=self._spool_bytes, suffix=".tmp") as spool:
            total = 0
            async with self._immich.stream_original(asset_id) as original:
                if original.content_length is not None and original.content_length > self._max_bytes:
                    return None, "original_stream_size_limit_exceeded"
                async for chunk in original.chunks:
                    await context.ensure_active()
                    total += len(chunk)
                    if total > self._max_bytes:
                        return None, "original_stream_size_limit_exceeded"
                    spool.write(chunk)
            spool.seek(0)
            return spool.read(), None

    @staticmethod
    def _decode(content: bytes):
        return decode_image_with_limit(
            BytesIO(content),
            detect_file_format(content[:64]),
        )

    async def _preview_content(self, asset_id: UUID) -> bytes:
        return await self._immich.get_bounded_preview(
            asset_id, max_bytes=MAX_SEARCH_PREVIEW_BYTES
        )

    @staticmethod
    def _same_source(live: ImmichAsset, search: AssetSimilaritySearchFeatureRecord) -> bool:
        search_width = getattr(search, "width", None)
        search_height = getattr(search, "height", None)
        return bool(
            live.asset_type == "IMAGE"
            and not live.is_trashed
            and not live.is_offline
            and live.file_modified_at == search.source_file_modified_at
            and live.file_size_bytes == search.source_file_size_bytes
            and live.checksum == search.source_checksum
            and (
                not live.width
                or not live.height
                or not search_width
                or not search_height
                or (live.width == search_width and live.height == search_height)
            )
        )

    async def _stored_alpha_state(
        self, asset_id: UUID, search: AssetSimilaritySearchFeatureRecord
    ) -> SourceAlphaState:
        getter = getattr(self._details, "source_alpha_state", None)
        if getter is None:
            return "unknown_alpha"
        state = await getter(asset_id, search.source_identity)
        return state or "unknown_alpha"

    async def _persist_detail_unavailable(
        self, asset_id: UUID, search: AssetSimilaritySearchFeatureRecord, reason: str
    ) -> None:
        marker = getattr(self._details, "mark_unavailable", None)
        if marker is not None and await marker(search.source_identity, asset_id, reason):
            self.counters["deterministic_retries_suppressed"] += 1

    async def _extract_one(
        self,
        context: TaskContext,
        asset_id: UUID,
        search: AssetSimilaritySearchFeatureRecord,
    ) -> None:
        async with self._slots:
            await context.ensure_active()
            try:
                live = await self._immich.get_asset(asset_id)
                if not self._same_source(live, search):
                    return
                oversized = _source_exceeds_decode_limit(live)
                source_alpha_state = await self._stored_alpha_state(asset_id, search)
                content: bytes | None = None
                origin: DetailEvidenceOrigin | None = None
                failure_reason: str | None = None

                if oversized:
                    self.counters["oversized_original_decodes_avoided"] += 1
                    try:
                        content = await self._immich.get_bounded_fullsize(
                            asset_id, max_bytes=self._max_bytes
                        )
                        if not bounded_rendition_is_detail_safe(source_alpha_state, content):
                            content = None
                            failure_reason = "alpha_preserving_bounded_rendition_unavailable"
                        else:
                            origin = "bounded_fullsize"
                    except (ImmichApiError, ValueError, OSError) as error:
                        failure_reason = f"bounded_rendition_unavailable: {error}"
                    if content is None and failure_reason != "alpha_preserving_bounded_rendition_unavailable":
                        try:
                            preview = await self._preview_content(asset_id)
                            if bounded_rendition_is_detail_safe(source_alpha_state, preview):
                                content = preview
                                origin = "bounded_preview"
                            else:
                                failure_reason = "alpha_preserving_bounded_rendition_unavailable"
                        except (ImmichApiError, ValueError, OSError) as error:
                            failure_reason = f"bounded_rendition_unavailable: {error}"
                else:
                    content, failure_reason = await self._original_content(context, asset_id)
                    if content is not None:
                        origin = "original"
                    if content is not None:
                        try:
                            decoded = await asyncio.to_thread(self._decode, content)
                        except (ValueError, OSError):
                            decoded = None
                        if decoded is None or decoded.valid is not True:
                            try:
                                content = await self._immich.get_bounded_fullsize(
                                    asset_id, max_bytes=self._max_bytes
                                )
                                origin = "transcoded_fullsize"
                            except (ImmichApiError, ValueError, OSError) as error:
                                try:
                                    content = await self._preview_content(asset_id)
                                    origin = "preview_fallback"
                                except (ImmichApiError, ValueError, OSError) as preview_error:
                                    content = None
                                    failure_reason = (
                                        f"rendition_unavailable: {error}; preview_unavailable: {preview_error}"
                                    )

                if content is None or origin is None:
                    if failure_reason and not _bounded_failure_is_retryable(failure_reason):
                        await self._persist_detail_unavailable(asset_id, search, failure_reason)
                    if failure_reason:
                        self.counters["unavailable_bounded_validations"] += int(oversized)
                        logger.warning(
                            "Similarity detail unavailable: asset_id=%s reason=%s",
                            asset_id,
                            failure_reason,
                        )
                    return

                try:
                    decoded = await asyncio.to_thread(self._decode, content)
                except (ValueError, OSError) as error:
                    decoded = None
                    failure_reason = f"detail_decode_failed: {error}"
                if decoded is None or decoded.valid is not True:
                    if failure_reason is None:
                        failure_reason = getattr(decoded, "issue", None) or "detail_decode_failed"
                    if not _bounded_failure_is_retryable(failure_reason):
                        await self._persist_detail_unavailable(asset_id, search, failure_reason)
                    if oversized:
                        self.counters["unavailable_bounded_validations"] += 1
                    logger.warning(
                        "Similarity detail unavailable: asset_id=%s reason=%s",
                        asset_id,
                        failure_reason,
                    )
                    return

                feature = await asyncio.to_thread(extract_detail_feature, decoded)
                await context.ensure_active()
                if await self._details.save(search.source_identity, asset_id, feature, origin):
                    if origin in {"bounded_fullsize", "bounded_preview"}:
                        self.counters["bounded_candidate_validations"] += 1
                    elif origin in {"original", "transcoded_fullsize"}:
                        self.counters["full_resolution_validations"] += 1
            except (PermanentTaskError, RetryableTaskError):
                raise
            except ImmichApiError as error:
                logger.warning(
                    "Similarity detail unavailable: asset_id=%s reason=%s",
                    asset_id,
                    error,
                )

    async def ensure(
        self,
        context: TaskContext,
        asset_ids: list[UUID],
        search_records: dict[UUID, AssetSimilaritySearchFeatureRecord],
    ) -> dict[UUID, AssetSimilarityDetailFeatureRecord]:
        current = await self._details.get_current_many(asset_ids)
        getter = getattr(self._details, "get_current_unavailable_many", None)
        unavailable = (
            await getter(asset_ids, search_records) if getter is not None else set()
        )
        pending = [
            asset_id
            for asset_id in asset_ids
            if asset_id not in current
            and asset_id not in unavailable
            and asset_id in search_records
        ]
        if unavailable:
            self.counters["deterministic_retries_suppressed"] += len(unavailable)
        tasks = [
            asyncio.create_task(self._extract_one(context, asset_id, search_records[asset_id]))
            for asset_id in pending
        ]
        try:
            if tasks:
                await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        return await self._details.get_current_many(asset_ids)

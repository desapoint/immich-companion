"""Candidate-only, bounded original-resolution visual detail extraction."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.image_decode import MAX_DECODED_PIXELS
from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset
from companion.integrity import detect_file_format
from companion.models import (
    AssetRecord,
    AssetSimilarityDetailFeatureRecord,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_bounded_state import (
    BOUNDED_CAPABILITY_VERSION,
    BOUNDED_POLICY_FINGERPRINT,
    AssetSimilarityBoundedStateRecord,
    SourceAlphaState,
)
from companion.similarity_detail import (
    DETAIL_FEATURE_VERSION,
    DetailDiagnostics,
    DetailFeature,
    detail_diagnostics,
    extract_detail_feature,
)
from companion.similarity_search_features import MAX_SEARCH_PREVIEW_BYTES
from companion.similarity_transparency import (
    bounded_rendition_is_detail_safe,
    classify_source_alpha,
)
from companion.task_coordinator import TaskContext

DETAIL_WORK_BATCH_SIZE = 8
DETAIL_SPOOL_MEMORY_BYTES = 4 * 1024 * 1024
# The published score is min(coarse, detail); a lower coarse score cannot be rescued.
DETAIL_COARSE_SCORE_MARGIN = 0.0
logger = logging.getLogger("uvicorn.error")

DetailEvidenceSource = Literal["original", "transcoded", "preview"]


@dataclass(frozen=True, slots=True)
class StoredDetailDiagnostics:
    diagnostics: DetailDiagnostics
    source: DetailEvidenceSource


class SimilarityDetailRepository:
    """Reuse detail samples only with their current coarse source identity."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def get_current_many(
        self, asset_ids: list[UUID]
    ) -> dict[UUID, AssetSimilarityDetailFeatureRecord]:
        if not asset_ids:
            return {}
        statement = (
            select(AssetSimilarityDetailFeatureRecord)
            .join(
                AssetSimilaritySearchFeatureRecord,
                AssetSimilaritySearchFeatureRecord.asset_id
                == AssetSimilarityDetailFeatureRecord.asset_id,
            )
            .where(
                AssetSimilarityDetailFeatureRecord.asset_id.in_(set(asset_ids)),
                AssetSimilarityDetailFeatureRecord.source_identity
                == AssetSimilaritySearchFeatureRecord.source_identity,
                AssetSimilarityDetailFeatureRecord.feature_version == DETAIL_FEATURE_VERSION,
            )
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.asset_id: record for record in records}

    async def get_current_unavailable_many(self, asset_ids: list[UUID]) -> dict[UUID, str]:
        """Return deterministic detail failures still valid for the current source."""

        if not asset_ids:
            return {}
        statement = (
            select(
                AssetSimilarityBoundedStateRecord.asset_id,
                AssetSimilarityBoundedStateRecord.detail_reason,
            )
            .join(
                AssetSimilaritySearchFeatureRecord,
                AssetSimilaritySearchFeatureRecord.asset_id
                == AssetSimilarityBoundedStateRecord.asset_id,
            )
            .where(
                AssetSimilarityBoundedStateRecord.asset_id.in_(set(asset_ids)),
                AssetSimilarityBoundedStateRecord.capability_version
                == BOUNDED_CAPABILITY_VERSION,
                AssetSimilarityBoundedStateRecord.policy_fingerprint
                == BOUNDED_POLICY_FINGERPRINT,
                AssetSimilarityBoundedStateRecord.search_status == "available",
                AssetSimilarityBoundedStateRecord.source_identity
                == AssetSimilaritySearchFeatureRecord.source_identity,
                AssetSimilarityBoundedStateRecord.detail_status == "unavailable",
                AssetSimilarityBoundedStateRecord.detail_source_identity
                == AssetSimilaritySearchFeatureRecord.source_identity,
                AssetSimilarityBoundedStateRecord.detail_feature_version
                == DETAIL_FEATURE_VERSION,
            )
        )
        async with self._database.sessions() as session:
            rows = (await session.execute(statement)).all()
        return {asset_id: reason or "detail unavailable" for asset_id, reason in rows}

    async def source_alpha_state(
        self, asset_id: UUID, source_identity: str
    ) -> SourceAlphaState | None:
        statement = select(AssetSimilarityBoundedStateRecord.alpha_state).where(
            AssetSimilarityBoundedStateRecord.asset_id == asset_id,
            AssetSimilarityBoundedStateRecord.source_identity == source_identity,
            AssetSimilarityBoundedStateRecord.search_status == "available",
            AssetSimilarityBoundedStateRecord.capability_version == BOUNDED_CAPABILITY_VERSION,
            AssetSimilarityBoundedStateRecord.policy_fingerprint == BOUNDED_POLICY_FINGERPRINT,
        )
        async with self._database.sessions() as session:
            value = await session.scalar(statement)
        if value in {"confirmed_opaque", "confirmed_alpha", "unknown_alpha"}:
            return cast(SourceAlphaState, value)
        return None

    async def mark_unavailable(
        self, source_identity: str, asset_id: UUID, reason: str
    ) -> bool:
        """Persist a deterministic bounded-detail failure against its source identity."""

        statement = (
            update(AssetSimilarityBoundedStateRecord)
            .where(
                AssetSimilarityBoundedStateRecord.asset_id == asset_id,
                AssetSimilarityBoundedStateRecord.source_identity == source_identity,
                AssetSimilarityBoundedStateRecord.search_status == "available",
                AssetSimilarityBoundedStateRecord.capability_version
                == BOUNDED_CAPABILITY_VERSION,
                AssetSimilarityBoundedStateRecord.policy_fingerprint
                == BOUNDED_POLICY_FINGERPRINT,
            )
            .values(
                detail_status="unavailable",
                detail_reason=reason,
                detail_source_identity=source_identity,
                detail_feature_version=DETAIL_FEATURE_VERSION,
                updated_at=datetime.now(UTC),
            )
        )
        async with self._database.sessions() as session, session.begin():
            result = await session.execute(statement)
        return bool(result.rowcount)

    async def diagnostics(
        self, selected_asset_id: UUID, reference_asset_id: UUID
    ) -> StoredDetailDiagnostics | None:
        """Compare two already-cached detail samples without generating new work."""

        records = await self.get_current_many([selected_asset_id, reference_asset_id])
        selected = records.get(selected_asset_id)
        reference = records.get(reference_asset_id)
        if selected is None or reference is None:
            return None
        selected_feature = DetailFeature(
            width=selected.width,
            height=selected.height,
            sample=selected.sample,
        )
        reference_feature = DetailFeature(
            width=reference.width,
            height=reference.height,
            sample=reference.sample,
        )
        origins = {selected.origin, reference.origin}
        source: DetailEvidenceSource
        if origins & {"preview_fallback", "bounded_preview", "bounded_fullsize"}:
            source = "preview"
        elif "transcoded_fullsize" in origins:
            source = "transcoded"
        else:
            source = "original"
        return StoredDetailDiagnostics(
            diagnostics=detail_diagnostics(selected_feature, reference_feature),
            source=source,
        )

    async def save(
        self, source_identity: str, asset_id: UUID, feature: DetailFeature, origin: str
    ) -> bool:
        if origin not in {
            "original",
            "transcoded_fullsize",
            "preview_fallback",
            "bounded_fullsize",
            "bounded_preview",
        }:
            raise ValueError("Unsupported detail evidence origin")
        values: dict[str, Any] = {
            "asset_id": asset_id,
            "source_identity": source_identity,
            "feature_version": DETAIL_FEATURE_VERSION,
            "origin": origin,
            "width": feature.width,
            "height": feature.height,
            "sample": feature.sample,
            "analyzed_at": datetime.now(UTC),
        }
        async with self._database.sessions() as session, session.begin():
            search = await session.get(
                AssetSimilaritySearchFeatureRecord, asset_id, with_for_update=True
            )
            asset = await session.get(AssetRecord, asset_id)
            if (
                search is None
                or asset is None
                or search.source_identity != source_identity
                or asset.asset_type != "IMAGE"
                or asset.is_trashed
                or asset.is_offline
                or search.source_file_modified_at != asset.file_modified_at
                or search.source_file_size_bytes != asset.file_size_bytes
                or search.source_checksum != asset.checksum
            ):
                return False
            statement = insert(AssetSimilarityDetailFeatureRecord).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AssetSimilarityDetailFeatureRecord.asset_id],
                    set_={
                        key: getattr(statement.excluded, key)
                        for key in values
                        if key != "asset_id"
                    },
                )
            )
            await session.execute(
                update(AssetSimilarityBoundedStateRecord)
                .where(
                    AssetSimilarityBoundedStateRecord.asset_id == asset_id,
                    AssetSimilarityBoundedStateRecord.source_identity == source_identity,
                )
                .values(
                    detail_status=None,
                    detail_reason=None,
                    detail_source_identity=None,
                    detail_feature_version=None,
                    updated_at=datetime.now(UTC),
                )
            )
        return True


class SimilarityDetailMaintainer:
    """Download only shortlisted assets, with finite batches and durable reuse."""

    def __init__(
        self,
        immich: ImmichApiClient,
        details: SimilarityDetailRepository,
        *,
        max_bytes: int = 128 * 1024 * 1024,
        slots: int = 1,
        cache_path: Path | None = None,
    ) -> None:
        if max_bytes < 1 or slots < 1:
            raise ValueError("Detail extraction limits must be positive")
        self._immich = immich
        self._details = details
        self._max_bytes = max_bytes
        self._slots = asyncio.Semaphore(slots)
        self._cache_path = cache_path
        self.counters: dict[str, int] = {}
        self.reset_counters()

    def reset_counters(self) -> None:
        """Start one task's measurements without discarding durable detail samples."""

        self.counters = {
            "detail_features_reused": 0,
            "detail_features_generated": 0,
            "detail_features_unavailable": 0,
            "detail_original_bytes": 0,
            "detail_transcoded_fallbacks": 0,
            "detail_preview_fallbacks": 0,
            "detail_oversized_bounded_validations": 0,
            "detail_oversized_original_decodes_avoided": 0,
            "bounded_candidate_validations": 0,
            "full_resolution_validations": 0,
            "unavailable_bounded_validations": 0,
            "alpha_uncertain_bounded_evidence": 0,
            "deterministic_retries_suppressed": 0,
        }

    async def _bounded_original(self, context: TaskContext, asset_id: UUID):
        with SpooledTemporaryFile(
            max_size=DETAIL_SPOOL_MEMORY_BYTES, dir=self._cache_path, suffix=".tmp"
        ) as spool:
            prefix = bytearray()
            total = 0
            async with self._immich.stream_original(asset_id) as media:
                if media.content_length is not None and media.content_length > self._max_bytes:
                    raise ValueError("original exceeds detail size limit")
                async for chunk in media.chunks:
                    await context.ensure_active()
                    total += len(chunk)
                    if total > self._max_bytes:
                        raise ValueError("original exceeds detail size limit")
                    if len(prefix) < 64:
                        prefix.extend(chunk[: 64 - len(prefix)])
                    spool.write(chunk)
            self.counters["detail_original_bytes"] += total
            return await asyncio.to_thread(
                extract_detail_feature, spool, detect_file_format(bytes(prefix))
            )

    @staticmethod
    def _requires_bounded_validation(search: AssetSimilaritySearchFeatureRecord) -> bool:
        width = getattr(search, "width", None)
        height = getattr(search, "height", None)
        return bool(
            getattr(search, "fingerprint_origin", "preview") == "bounded"
            or (width and height and width * height > MAX_DECODED_PIXELS)
        )

    @staticmethod
    async def _detail_from_content(content: bytes) -> DetailFeature | None:
        return await asyncio.to_thread(
            extract_detail_feature,
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

    async def _extract_bounded(
        self,
        asset_id: UUID,
        live: ImmichAsset,
        source_state: SourceAlphaState,
    ) -> tuple[DetailFeature | None, str | None, str | None, SourceAlphaState]:
        """Prefer the largest safe rendition and never promote flattened alpha evidence."""

        fullsize_content: bytes | None = None
        fullsize_error: Exception | None = None
        try:
            fullsize_content = await self._immich.get_bounded_fullsize(
                asset_id, max_bytes=self._max_bytes
            )
        except (ImmichApiError, OSError, ValueError) as error:
            fullsize_error = error

        if fullsize_content is not None:
            observed = classify_source_alpha(live, bounded_content=fullsize_content)
            if source_state == "unknown_alpha" or observed == "confirmed_alpha":
                source_state = observed
            if bounded_rendition_is_detail_safe(source_state, fullsize_content):
                feature = await self._detail_from_content(fullsize_content)
                if feature is not None:
                    return feature, "bounded_fullsize", None, source_state
            elif source_state == "unknown_alpha":
                self.counters["alpha_uncertain_bounded_evidence"] += 1

        preview_content: bytes | None = None
        preview_error: Exception | None = None
        try:
            preview_content = await self._preview_content(asset_id)
        except (ImmichApiError, OSError, ValueError) as error:
            preview_error = error

        if preview_content is not None:
            observed = classify_source_alpha(live, bounded_content=preview_content)
            if source_state == "unknown_alpha" or observed == "confirmed_alpha":
                source_state = observed
            if bounded_rendition_is_detail_safe(source_state, preview_content):
                feature = await self._detail_from_content(preview_content)
                if feature is not None:
                    return feature, "bounded_preview", None, source_state
            else:
                self.counters["alpha_uncertain_bounded_evidence"] += 1

        if fullsize_content is not None or preview_content is not None:
            return (
                None,
                None,
                "alpha_preserving_bounded_rendition_unavailable",
                source_state,
            )
        return (
            None,
            None,
            f"bounded_rendition_unavailable: {fullsize_error or preview_error}",
            source_state,
        )

    async def _extract_one(
        self,
        context: TaskContext,
        asset_id: UUID,
        search: AssetSimilaritySearchFeatureRecord,
    ) -> bool:
        async with self._slots:
            await context.ensure_active()
            try:
                live = await self._immich.get_asset(asset_id)
            except ImmichApiError:
                self.counters["detail_features_unavailable"] += 1
                return False
            if not self._same_source(live, search):
                self.counters["detail_features_unavailable"] += 1
                return False

            feature: DetailFeature | None = None
            origin = "original"
            bounded_required = self._requires_bounded_validation(search)
            if bounded_required:
                self.counters["detail_oversized_bounded_validations"] += 1
                self.counters["detail_oversized_original_decodes_avoided"] += 1
                source_state = await self._stored_alpha_state(asset_id, search)
                if source_state == "unknown_alpha":
                    source_state = classify_source_alpha(live)
                feature, bounded_origin, reason, _ = await self._extract_bounded(
                    asset_id, live, source_state
                )
                if feature is None:
                    self.counters["detail_features_unavailable"] += 1
                    self.counters["unavailable_bounded_validations"] += 1
                    if reason == "alpha_preserving_bounded_rendition_unavailable":
                        await self._persist_detail_unavailable(asset_id, search, reason)
                        logger.warning(
                            "Candidate bounded detail unavailable: asset_id=%s reason=%s",
                            asset_id,
                            reason,
                        )
                    return False
                origin = bounded_origin or "bounded_preview"
                self.counters["bounded_candidate_validations"] += 1
            else:
                with suppress(ImmichApiError, OSError, ValueError):
                    feature = await self._bounded_original(context, asset_id)
                if feature is not None:
                    self.counters["full_resolution_validations"] += 1
                if feature is None:
                    try:
                        content = await self._immich.get_bounded_fullsize(
                            asset_id, max_bytes=self._max_bytes
                        )
                        feature = await self._detail_from_content(content)
                        if feature is not None:
                            origin = "transcoded_fullsize"
                    except (ImmichApiError, OSError, ValueError):
                        pass
                if feature is None:
                    try:
                        content = await self._preview_content(asset_id)
                        feature = await self._detail_from_content(content)
                        if feature is not None:
                            origin = "preview_fallback"
                    except (ImmichApiError, OSError, ValueError):
                        pass
            if feature is None:
                self.counters["detail_features_unavailable"] += 1
                logger.warning("Candidate detail unavailable after attempted analysis: asset_id=%s", asset_id)
                return False

            await context.ensure_active()
            if origin == "transcoded_fullsize" and (
                not live.width
                or not live.height
                or sorted((feature.width, feature.height))
                != sorted((live.width, live.height))
            ):
                origin = "preview_fallback"
            saved = await self._details.save(search.source_identity, asset_id, feature, origin)
            if saved and origin == "transcoded_fullsize":
                self.counters["detail_transcoded_fallbacks"] += 1
            elif saved and origin in {"preview_fallback", "bounded_preview"}:
                self.counters["detail_preview_fallbacks"] += 1
            self.counters[
                "detail_features_generated" if saved else "detail_features_unavailable"
            ] += 1
            return saved

    async def ensure(
        self,
        context: TaskContext,
        asset_ids: list[UUID],
        search_features: dict[UUID, AssetSimilaritySearchFeatureRecord],
        *,
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> None:
        ordered = sorted(set(asset_ids), key=lambda item: item.int)
        for offset in range(0, len(ordered), DETAIL_WORK_BATCH_SIZE):
            await context.ensure_active()
            page = ordered[offset : offset + DETAIL_WORK_BATCH_SIZE]
            current = await self._details.get_current_many(page)
            self.counters["detail_features_reused"] += len(current)
            unavailable_getter = getattr(self._details, "get_current_unavailable_many", None)
            unavailable = (
                await unavailable_getter(page) if unavailable_getter is not None else {}
            )
            self.counters["deterministic_retries_suppressed"] += len(unavailable)
            pending = [
                asset_id
                for asset_id in page
                if asset_id not in current
                and asset_id not in unavailable
                and asset_id in search_features
            ]
            tasks = [
                asyncio.create_task(
                    self._extract_one(context, asset_id, search_features[asset_id])
                )
                for asset_id in pending
            ]
            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            if on_progress is not None:
                await on_progress(min(offset + len(page), len(ordered)), len(ordered))

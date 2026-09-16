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
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.immich import ImmichApiClient, ImmichApiError
from companion.integrity import detect_file_format
from companion.models import (
    AssetRecord,
    AssetSimilarityDetailFeatureRecord,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_detail import (
    DETAIL_FEATURE_VERSION,
    DetailDiagnostics,
    DetailFeature,
    detail_diagnostics,
    extract_detail_feature,
)
from companion.similarity_search_features import MAX_SEARCH_PREVIEW_BYTES
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
        if "preview_fallback" in origins:
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
        if origin not in {"original", "transcoded_fullsize", "preview_fallback"}:
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
                        for key in values if key != "asset_id"
                    },
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
                        prefix.extend(chunk[:64 - len(prefix)])
                    spool.write(chunk)
            self.counters["detail_original_bytes"] += total
            return await asyncio.to_thread(
                extract_detail_feature, spool, detect_file_format(bytes(prefix))
            )

    async def _extract_one(
        self, context: TaskContext, asset_id: UUID,
        search: AssetSimilaritySearchFeatureRecord,
    ) -> bool:
        async with self._slots:
            await context.ensure_active()
            feature = None
            origin = "original"
            with suppress(ImmichApiError, OSError, ValueError):
                feature = await self._bounded_original(context, asset_id)
            if feature is None:
                try:
                    content = await self._immich.get_bounded_fullsize(
                        asset_id, max_bytes=self._max_bytes
                    )
                    feature = await asyncio.to_thread(
                        extract_detail_feature,
                        BytesIO(content), detect_file_format(content[:64]),
                    )
                    if feature is not None:
                        origin = "transcoded_fullsize"
                except (ImmichApiError, OSError, ValueError):
                    pass
            if feature is None:
                try:
                    content = await self._immich.get_bounded_preview(
                        asset_id, max_bytes=MAX_SEARCH_PREVIEW_BYTES
                    )
                    feature = await asyncio.to_thread(
                        extract_detail_feature,
                        BytesIO(content), detect_file_format(content[:64]),
                    )
                    if feature is not None:
                        origin = "preview_fallback"
                except (ImmichApiError, OSError, ValueError):
                    pass
            if feature is None:
                self.counters["detail_features_unavailable"] += 1
                logger.warning("Candidate detail unavailable: asset_id=%s", asset_id)
                return False
            await context.ensure_active()
            try:
                live = await self._immich.get_asset(asset_id)
            except ImmichApiError:
                self.counters["detail_features_unavailable"] += 1
                return False
            if (
                live.asset_type != "IMAGE" or live.is_trashed or live.is_offline
                or live.file_modified_at != search.source_file_modified_at
                or live.file_size_bytes != search.source_file_size_bytes
                or live.checksum != search.source_checksum
            ):
                self.counters["detail_features_unavailable"] += 1
                return False
            if origin == "transcoded_fullsize" and (
                not live.width or not live.height
                or sorted((feature.width, feature.height))
                != sorted((live.width, live.height))
            ):
                # Some servers can serve a reduced rendition for this endpoint.
                # Keep its useful visual evidence without calling it full-size.
                origin = "preview_fallback"
            saved = await self._details.save(search.source_identity, asset_id, feature, origin)
            if saved and origin == "transcoded_fullsize":
                self.counters["detail_transcoded_fallbacks"] += 1
            elif saved and origin == "preview_fallback":
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
            pending = [
                asset_id for asset_id in page
                if asset_id not in current and asset_id in search_features
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

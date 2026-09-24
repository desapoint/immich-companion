"""Cached localized-detail evidence from the unified visual representation."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from companion.database import DatabaseManager
from companion.duplicate_discovery_settings import DuplicateDiscoverySettingsRepository
from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset
from companion.models import (
    AssetRecord,
    AssetSimilarityDetailFeatureRecord,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_bounded_state import AssetSimilarityBoundedStateRecord
from companion.similarity_detail import (
    DETAIL_FEATURE_VERSION,
    DetailDiagnostics,
    DetailFeature,
    detail_diagnostics,
    extract_detail_feature_from_image,
)
from companion.similarity_generation import (
    SimilarityEvidenceEpochRepository,
    SimilarityEvidenceGenerationState,
    SimilarityEvidenceRebuildResult,
)
from companion.similarity_search_features import (
    SEARCH_CONFIG_FINGERPRINT,
    SEARCH_FEATURE_VERSION,
    SEARCH_MODEL_VERSION,
    search_source_identity,
)
from companion.similarity_visual_normalization import (
    SimilarityVisualNormalizer,
    VisualNormalizationError,
)
from companion.task_coordinator import TaskContext

DETAIL_WORK_BATCH_SIZE = 8
logger = logging.getLogger("uvicorn.error")

DetailEvidenceSource = Literal["original", "transcoded", "preview"]


def _accepts_parameter(callable_object: object, parameter: str) -> bool:
    try:
        return parameter in inspect.signature(callable_object).parameters
    except (TypeError, ValueError):
        return True


@dataclass(frozen=True, slots=True)
class StoredDetailDiagnostics:
    diagnostics: DetailDiagnostics
    source: DetailEvidenceSource
    comparison_max_displacement_percent: int = 10
    comparison_max_rotation_degrees: int = 0
    comparison_max_zoom_percent: int = 0


class SimilarityDetailRepository:
    """Reuse detail samples only with their current coarse source identity."""

    def __init__(
        self,
        database: DatabaseManager,
        duplicate_settings: DuplicateDiscoverySettingsRepository | None = None,
    ) -> None:
        self._database = database
        self._evidence_epoch = SimilarityEvidenceEpochRepository(database)
        self._duplicate_settings = duplicate_settings

    async def current_evidence_epoch(self) -> int:
        return await self._evidence_epoch.capture_epoch()

    async def generation_status(self) -> SimilarityEvidenceGenerationState:
        return await self._evidence_epoch.status()

    async def rebuild_evidence(self) -> SimilarityEvidenceRebuildResult:
        return await self._evidence_epoch.rebuild()

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
            .join(AssetRecord, AssetRecord.id == AssetSimilaritySearchFeatureRecord.asset_id)
            .where(
                AssetSimilarityDetailFeatureRecord.asset_id.in_(set(asset_ids)),
                AssetSimilarityDetailFeatureRecord.source_identity
                == AssetSimilaritySearchFeatureRecord.source_identity,
                AssetSimilarityDetailFeatureRecord.feature_version == DETAIL_FEATURE_VERSION,
                AssetRecord.asset_type == "IMAGE",
                AssetRecord.is_trashed.is_(False),
                AssetRecord.is_offline.is_(False),
                AssetSimilaritySearchFeatureRecord.model_version == SEARCH_MODEL_VERSION,
                AssetSimilaritySearchFeatureRecord.feature_version == SEARCH_FEATURE_VERSION,
                AssetSimilaritySearchFeatureRecord.config_fingerprint
                == SEARCH_CONFIG_FINGERPRINT,
                AssetSimilaritySearchFeatureRecord.source_file_modified_at
                == AssetRecord.file_modified_at,
                AssetSimilaritySearchFeatureRecord.source_file_size_bytes.is_not_distinct_from(
                    AssetRecord.file_size_bytes
                ),
                AssetSimilaritySearchFeatureRecord.source_checksum.is_not_distinct_from(
                    AssetRecord.checksum
                ),
            )
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return {record.asset_id: record for record in records}

    async def diagnostics(
        self,
        selected_asset_id: UUID,
        reference_asset_id: UUID,
        *,
        comparison_max_displacement_percent: int | None = None,
        comparison_max_rotation_degrees: int | None = None,
        comparison_max_zoom_percent: int | None = None,
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
        settings = None
        if (
            comparison_max_displacement_percent is None
            or comparison_max_rotation_degrees is None
            or comparison_max_zoom_percent is None
        ):
            settings = (
                await self._duplicate_settings.get()
                if self._duplicate_settings is not None
                else None
            )
        displacement = (
            comparison_max_displacement_percent
            if comparison_max_displacement_percent is not None
            else settings.comparison_max_displacement_percent if settings is not None else 10
        )
        rotation = (
            comparison_max_rotation_degrees
            if comparison_max_rotation_degrees is not None
            else settings.comparison_max_rotation_degrees if settings is not None else 0
        )
        zoom = (
            comparison_max_zoom_percent
            if comparison_max_zoom_percent is not None
            else settings.comparison_max_zoom_percent if settings is not None else 0
        )
        return StoredDetailDiagnostics(
            diagnostics=detail_diagnostics(
                selected_feature,
                reference_feature,
                max_shift_fraction=displacement / 100,
                max_rotation_degrees=rotation,
                max_zoom_percent=zoom,
            ),
            source=source,
            comparison_max_displacement_percent=displacement,
            comparison_max_rotation_degrees=rotation,
            comparison_max_zoom_percent=zoom,
        )

    async def save(
        self,
        source_identity: str,
        asset_id: UUID,
        feature: DetailFeature,
        origin: str,
        *,
        evidence_epoch: int | None = None,
    ) -> bool:
        if origin not in {
            "original",
            "transcoded_fullsize",
            "preview_fallback",
            "bounded_fullsize",
            "bounded_preview",
        }:
            raise ValueError("Unsupported detail evidence origin")
        expected_epoch = (
            evidence_epoch if evidence_epoch is not None else await self.current_evidence_epoch()
        )
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
            await self._evidence_epoch.assert_current(session, expected_epoch)
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
    """Reuse cached detail and repair rare gaps through the unified normalizer."""

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
        self._normalizer = SimilarityVisualNormalizer(
            immich,
            max_bytes=max_bytes,
            cache_path=cache_path,
        )
        self.counters: dict[str, int] = {}
        self.reset_counters()

    def reset_counters(self) -> None:
        """Start one task's measurements without discarding durable detail samples."""

        self.counters = {
            "detail_features_reused": 0,
            "detail_features_generated": 0,
            "detail_features_unavailable": 0,
            "detail_original_bytes": 0,
            "detail_preview_fallbacks": 0,
            "detail_original_sources": 0,
            "preview_fallback_validations": 0,
        }

    @staticmethod
    async def _detail_from_normalized(normalized) -> DetailFeature | None:
        def build() -> DetailFeature | None:
            image = Image.frombytes(
                normalized.pixel_mode,
                (normalized.width, normalized.height),
                normalized.pixel_bytes,
            )
            try:
                return extract_detail_feature_from_image(image)
            finally:
                image.close()

        return await asyncio.to_thread(build)

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

    async def _extract_one(
        self,
        context: TaskContext,
        asset_id: UUID,
        search: AssetSimilaritySearchFeatureRecord,
        evidence_epoch: int,
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

            try:
                normalized = await self._normalizer.normalize(context, asset_id, live)
            except (ImmichApiError, OSError, VisualNormalizationError) as error:
                self.counters["detail_features_unavailable"] += 1
                logger.warning(
                    "Normalized detail unavailable: asset_id=%s reason=%s",
                    asset_id,
                    error,
                )
                return False

            if getattr(search, "media_sha256", None) is not None:
                expected_source_identity = search_source_identity(
                    live,
                    normalized.media_sha256,
                    origin=normalized.search_origin,
                )
                if expected_source_identity != search.source_identity:
                    self.counters["detail_features_unavailable"] += 1
                    return False

            feature = await self._detail_from_normalized(normalized)
            if feature is None:
                self.counters["detail_features_unavailable"] += 1
                return False

            await context.ensure_active()
            saver = self._details.save
            if _accepts_parameter(saver, "evidence_epoch"):
                saved = await saver(
                    search.source_identity,
                    asset_id,
                    feature,
                    normalized.detail_origin,
                    evidence_epoch=evidence_epoch,
                )
            else:
                saved = await saver(
                    search.source_identity,
                    asset_id,
                    feature,
                    normalized.detail_origin,
                )

            if normalized.source_kind == "original":
                self.counters["detail_original_sources"] += 1
                self.counters["detail_original_bytes"] += normalized.source_bytes
            else:
                self.counters["preview_fallback_validations"] += 1
                if saved:
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
        evidence_epoch: int | None = None,
    ) -> None:
        """Repair only genuinely missing detail using the shared visual normalizer."""

        expected_epoch = (
            evidence_epoch
            if evidence_epoch is not None
            else await self._details.current_evidence_epoch()
        )
        ordered = sorted(set(asset_ids), key=lambda item: item.int)
        for offset in range(0, len(ordered), DETAIL_WORK_BATCH_SIZE):
            await context.ensure_active()
            page = ordered[offset : offset + DETAIL_WORK_BATCH_SIZE]
            current = await self._details.get_current_many(page)
            self.counters["detail_features_reused"] += len(current)
            pending = [
                asset_id
                for asset_id in page
                if asset_id not in current and asset_id in search_features
            ]
            tasks = [
                asyncio.create_task(
                    self._extract_one(
                        context,
                        asset_id,
                        search_features[asset_id],
                        expected_epoch,
                    )
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

"""HTTP surface for cached localized similarity evidence and generation control."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException, status

from companion.duplicate_schema import SimilarityScanRequest
from companion.similarity_detail_schema import (
    SimilarityEvidenceDestroyResponse,
    SimilarityEvidenceGenerationResponse,
    SimilarityEvidenceRebuildResponse,
    SimilarityLocalDiagnosticsResponse,
)
from companion.similarity_detail_service import SimilarityDetailRepository


def register_similarity_detail_routes(
    app: FastAPI,
    repository: SimilarityDetailRepository | None,
) -> None:
    """Register diagnostics and explicit whole-generation invalidation."""

    def require_repository() -> SimilarityDetailRepository:
        if repository is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return repository

    def generation_response(generation) -> SimilarityEvidenceGenerationResponse:
        return SimilarityEvidenceGenerationResponse(
            epoch=generation.epoch,
            code_generation=generation.code_generation,
            recorded_descriptor_fingerprint=generation.recorded_descriptor_fingerprint,
            current_descriptor_fingerprint=generation.current_descriptor_fingerprint,
            descriptor_current=generation.descriptor_current,
            rebuilt_at=generation.rebuilt_at,
        )

    @app.get(
        "/api/v2/duplicates/similarity-local-changes",
        response_model=SimilarityLocalDiagnosticsResponse,
    )
    async def similarity_local_change_diagnostics(
        selected_asset_id: UUID,
        reference_asset_id: UUID,
    ) -> SimilarityLocalDiagnosticsResponse:
        stored = await require_repository().diagnostics(
            selected_asset_id,
            reference_asset_id,
        )
        if stored is None:
            return SimilarityLocalDiagnosticsResponse(
                available=False,
                selected_asset_id=selected_asset_id,
                reference_asset_id=reference_asset_id,
            )

        diagnostics = stored.diagnostics
        return SimilarityLocalDiagnosticsResponse(
            available=True,
            selected_asset_id=selected_asset_id,
            reference_asset_id=reference_asset_id,
            changed_percent=diagnostics.changed_percent,
            localized_changed_percent=diagnostics.localized_changed_percent,
            coherent_changed_percent=diagnostics.coherent_changed_percent,
            largest_changed_region_percent=diagnostics.largest_changed_region_percent,
            substantial_region_count=diagnostics.substantial_region_count,
            aligned_changed_percent=diagnostics.aligned_changed_percent,
            raw_similarity_percent=diagnostics.raw_similarity_percent,
            aligned_similarity_percent=diagnostics.aligned_similarity_percent,
            alignment_applied=diagnostics.alignment_applied,
            alignment_shift_percent=diagnostics.alignment_shift_percent,
            alignment_overlap_percent=diagnostics.alignment_overlap_percent,
            rows=diagnostics.rows,
            columns=diagnostics.columns,
            cells=[list(row) for row in diagnostics.tile_changed_percents],
            source=stored.source,
        )

    @app.get(
        "/api/v2/duplicates/similarity-evidence/generation",
        response_model=SimilarityEvidenceGenerationResponse,
    )
    async def similarity_evidence_generation() -> SimilarityEvidenceGenerationResponse:
        generation = await require_repository().generation_status()
        return generation_response(generation)

    @app.post(
        "/api/v2/duplicates/similarity-evidence/destroy",
        response_model=SimilarityEvidenceDestroyResponse,
    )
    async def destroy_similarity_evidence() -> SimilarityEvidenceDestroyResponse:
        detail_repository = require_repository()
        result = await detail_repository._evidence_epoch.destroy()  # noqa: SLF001
        return SimilarityEvidenceDestroyResponse(
            generation=generation_response(result.state),
            cancelled_task_count=result.cancelled_task_count,
            removed_counts=result.removed_counts,
        )

    @app.post(
        "/api/v2/duplicates/similarity-evidence/rebuild",
        response_model=SimilarityEvidenceRebuildResponse,
    )
    async def rebuild_similarity_evidence(
        scan_request: SimilarityScanRequest,
    ) -> SimilarityEvidenceRebuildResponse:
        detail_repository = require_repository()
        # The epoch repository owns the atomic transaction that invalidates old evidence
        # and inserts the replacement similarity-scan task. Keeping both operations there
        # prevents a lost HTTP response or browser shutdown from stranding an empty epoch.
        result = await detail_repository._evidence_epoch.rebuild(  # noqa: SLF001
            scan_request.model_dump(mode="json")
        )
        return SimilarityEvidenceRebuildResponse(
            generation=generation_response(result.state),
            cancelled_task_count=result.cancelled_task_count,
            removed_counts=result.removed_counts,
            task_id=result.task_id,
        )

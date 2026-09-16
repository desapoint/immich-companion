"""Read-only HTTP surface for cached localized similarity evidence."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, status

from companion.similarity_detail_schema import SimilarityLocalDiagnosticsResponse
from companion.similarity_detail_service import SimilarityDetailRepository


def register_similarity_detail_routes(
    app: FastAPI,
    repository: SimilarityDetailRepository | None,
) -> None:
    """Register diagnostics without creating or refreshing any detail samples."""

    def require_repository() -> SimilarityDetailRepository:
        if repository is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return repository

    @app.get(
        "/api/v2/duplicates/similarity-local-changes",
        response_model=SimilarityLocalDiagnosticsResponse,
    )
    async def similarity_local_change_diagnostics(
        selected_asset_id: UUID = Query(...),
        reference_asset_id: UUID = Query(...),
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
            rows=diagnostics.rows,
            columns=diagnostics.columns,
            cells=[list(row) for row in diagnostics.tile_changed_percents],
            source=stored.source,
        )

"""HTTP surface for arbitrary read-only similarity diagnostics."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from companion.similarity_debug_schema import SimilarityDebugRequest, SimilarityDebugResponse
from companion.similarity_debug_service import SimilarityDebugService
from companion.similarity_detail_service import SimilarityDetailRepository
from companion.similarity_repository import SimilarityRepository
from companion.similarity_search_repository import SimilaritySearchRepository


def register_similarity_debug_routes(
    app: FastAPI,
    features: SimilaritySearchRepository | None,
    similarity: SimilarityRepository | None,
    details: SimilarityDetailRepository | None,
) -> None:
    service = (
        SimilarityDebugService(features, similarity, details)
        if features is not None and similarity is not None
        else None
    )

    @app.post(
        "/api/v2/similarity-debug/compare",
        response_model=SimilarityDebugResponse,
    )
    async def compare_similarity_debug(
        request: SimilarityDebugRequest,
    ) -> SimilarityDebugResponse:
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The companion database is not configured.",
            )
        return await service.compare(request)

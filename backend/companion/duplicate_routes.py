"""Duplicate review, integrity, cache, and resolution route registration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Response,
    status,
)

from companion.duplicate_schema import (
    CrossSourceDuplicateResult,
    CrossSourceDuplicateTaskStart,
    DuplicateAnalysisOptions,
    DuplicateGroupDraft,
    DuplicateGroupDraftUpdate,
    DuplicateGroupIdsResult,
    DuplicateKeeperSelectionRequest,
    DuplicateKeeperSelectionResult,
    DuplicateResolutionExecuteRequest,
    DuplicateResolutionPlan,
    DuplicateResolutionPlanRequest,
    DuplicateReviewUpdate,
    DuplicateSearchPage,
    DuplicateSimilarityReferenceRequest,
    DuplicateWorkspaceMembership,
    DuplicateWorkspaceMembershipRequest,
    DuplicateWorkspacePresetRequest,
    DuplicateWorkspaceResetRequest,
    DuplicateWorkspaceSelectionDelta,
    DuplicateWorkspaceSelectionUpdate,
    DuplicateWorkspaceState,
    ExactDuplicateGroup,
    SimilarityCacheClearRequest,
    SimilarityCacheClearResult,
    SimilarityCacheStatus,
    SimilarityIndexCoverage,
    SimilarityIndexTaskStart,
    SimilarityScanRequest,
    SimilarityScanSummary,
    SimilarityScanTaskStart,
)
from companion.immich import (
    ImmichApiError,
)


def register_duplicate_routes(
    app: FastAPI,
    *,
    build_similarity_cache_status,
    similarity_cache,
    require_similarity_repository,
    require_integrity_service,
    require_duplicate_service,
    duplicate_review_repository,
    duplicate_discovery,
    database,
    v2_duplicate_review_state_refresh_service,
    require_similarity_index_service,
    require_similarity_scan_service,
    map_action_error,
    map_immich_error,
) -> None:
    """Register duplicate review, evidence, history, and resolution endpoints."""

    @app.get("/api/assets/duplicates/cross-source", response_model=CrossSourceDuplicateResult)
    async def cross_source_duplicate_result() -> CrossSourceDuplicateResult:
        try:
            return await require_duplicate_service().review()
        except ImmichApiError as error:
            raise map_immich_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/search", response_model=CrossSourceDuplicateResult
    )
    async def search_cross_source_duplicates(
        request: DuplicateAnalysisOptions,
    ) -> CrossSourceDuplicateResult:
        return await require_duplicate_service().review(request)

    @app.post("/api/assets/duplicates/cross-source/page", response_model=DuplicateSearchPage)
    async def page_cross_source_duplicates(
        request: DuplicateAnalysisOptions,
        page: int = Query(1, ge=1),
        page_size: int = Query(6, ge=1, le=100),
        source: Literal["both", "immich", "similarity"] = "both",
        sort: Literal["reclaimable", "members", "similarity", "date", "discovered"] = "reclaimable",
        direction: Literal["asc", "desc"] = "desc",
        state: Literal[
            "all", "needs_review", "auto_ready", "blocked", "actionable", "needs_decisions"
        ] = "all",
    ) -> DuplicateSearchPage:
        return await require_duplicate_service().review_page(
            request,
            page=page,
            page_size=page_size,
            source=source,
            sort=sort,
            direction=direction,
            state=state,
        )

    @app.post(
        "/api/assets/duplicates/cross-source/selected-page", response_model=DuplicateSearchPage
    )
    async def page_selected_cross_source_duplicates(
        request: DuplicateAnalysisOptions,
        page: int = Query(1, ge=1),
        page_size: int = Query(6, ge=1, le=100),
        source: Literal["both", "immich", "similarity"] = "both",
        sort: Literal["reclaimable", "members", "similarity", "date", "discovered"] = "reclaimable",
        direction: Literal["asc", "desc"] = "desc",
    ) -> DuplicateSearchPage:
        return await require_duplicate_service().review_selected_page(
            request, page=page, page_size=page_size, source=source, sort=sort, direction=direction
        )

    @app.get("/api/assets/duplicates/group-ids", response_model=DuplicateGroupIdsResult)
    async def duplicate_group_ids(
        source: Literal["both", "immich", "similarity"] = "both",
        state: Literal[
            "all", "needs_review", "auto_ready", "blocked", "actionable", "needs_decisions"
        ] = "all",
        limit: int = Query(10_000, ge=1, le=50_000),
    ) -> DuplicateGroupIdsResult:
        if duplicate_discovery is None:
            raise HTTPException(
                status_code=503, detail="The persisted duplicate projection is unavailable."
            )
        group_ids = await duplicate_discovery.resolve_matching_group_ids(
            source=source, state=state, limit=min(50_001, limit + 1)
        )
        return DuplicateGroupIdsResult(
            group_ids=group_ids[:limit], limit_exceeded=len(group_ids) > limit
        )

    @app.post(
        "/api/assets/duplicates/cross-source/analyze",
        response_model=CrossSourceDuplicateTaskStart,
        status_code=202,
    )
    async def analyze_cross_source_duplicates(
        request: DuplicateAnalysisOptions | None = None,
    ) -> CrossSourceDuplicateTaskStart:
        return await require_duplicate_service().start(request or DuplicateAnalysisOptions())

    @app.post(
        "/api/assets/duplicates/similarity-scan",
        response_model=SimilarityScanTaskStart,
        status_code=202,
    )
    async def start_similarity_scan(request: SimilarityScanRequest) -> SimilarityScanTaskStart:
        return await require_similarity_scan_service().start(request)

    @app.post(
        "/api/assets/duplicates/similarity-index",
        response_model=SimilarityIndexTaskStart,
        status_code=202,
    )
    async def start_similarity_index() -> SimilarityIndexTaskStart:
        return await require_similarity_index_service().start()

    @app.get(
        "/api/assets/duplicates/similarity-index/coverage", response_model=SimilarityIndexCoverage
    )
    async def similarity_index_coverage() -> SimilarityIndexCoverage:
        return await require_similarity_index_service().coverage()

    @app.get(
        "/api/assets/duplicates/similarity-scan/latest", response_model=SimilarityScanSummary | None
    )
    async def latest_similarity_scan() -> SimilarityScanSummary | None:
        return await require_similarity_scan_service().latest()

    @app.get("/api/assets/duplicates/cache", response_model=SimilarityCacheStatus)
    async def similarity_cache_status() -> SimilarityCacheStatus:
        return await build_similarity_cache_status()

    @app.get("/api/assets/duplicates/history")
    async def duplicate_resolution_history(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
        days: int | None = Query(None, ge=1, le=3650),
    ) -> dict[str, object]:
        if duplicate_review_repository is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        since = datetime.now(UTC) - timedelta(days=days) if days is not None else None
        records, total = await duplicate_review_repository.history(
            since=since, page=page, page_size=page_size
        )
        items = [
            {
                "id": str(record.id),
                "occurred_at": record.last_reviewed_at or record.updated_at,
                "discovery_source": record.discovery_source,
                "provider_group_id": record.provider_group_id,
                "review_status": record.review_status,
                "manual_action": record.manual_action,
                "member_count": len(record.member_decisions or []),
                "member_asset_ids": [
                    str(decision["asset_id"])
                    for decision in (record.member_decisions or [])
                    if isinstance(decision, dict) and decision.get("asset_id")
                ],
            }
            for record in records
        ]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    @app.delete("/api/assets/duplicates/history")
    async def clear_all_duplicate_resolution_history() -> dict[str, int]:
        if database is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        from companion.duplicate_resolution_history import clear_all_completed_resolutions

        cleared = await clear_all_completed_resolutions(database)
        if v2_duplicate_review_state_refresh_service is not None:
            await v2_duplicate_review_state_refresh_service.refresh_after_change()
        return {"cleared": cleared}

    @app.delete("/api/assets/duplicates/history/{resolution_id}", status_code=204)
    async def clear_duplicate_resolution_history(resolution_id: UUID) -> Response:
        if database is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        from companion.duplicate_resolution_history import clear_completed_resolution

        if not await clear_completed_resolution(database, resolution_id):
            raise HTTPException(
                status_code=404, detail="The completed duplicate resolution was not found."
            )
        if v2_duplicate_review_state_refresh_service is not None:
            await v2_duplicate_review_state_refresh_service.refresh_after_change()
        return Response(status_code=204)

    @app.post(
        "/api/assets/duplicates/cache/clear",
        response_model=SimilarityCacheClearResult,
    )
    async def clear_similarity_cache(
        request: SimilarityCacheClearRequest,
    ) -> SimilarityCacheClearResult:
        if request.cache == "previews":
            removed = await asyncio.to_thread(similarity_cache.preview.clear)
        elif request.cache == "decode":
            removed = await asyncio.to_thread(similarity_cache.clear_decode)
        else:
            removed = await require_similarity_repository().clear_cache(request.cache)
        return SimilarityCacheClearResult(
            cache=request.cache,
            removed_count=removed,
            status=await build_similarity_cache_status(),
        )

    @app.put(
        "/api/assets/duplicates/cross-source/review",
        response_model=ExactDuplicateGroup,
    )
    async def save_cross_source_duplicate_review(
        request: DuplicateReviewUpdate,
    ) -> ExactDuplicateGroup:
        try:
            return await require_duplicate_service().save_review(
                request,
                request.options,
            )
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.get(
        "/api/assets/duplicates/workspace",
        response_model=DuplicateWorkspaceState,
    )
    async def duplicate_workspace() -> DuplicateWorkspaceState:
        try:
            return await require_duplicate_service().workspace()
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.put(
        "/api/assets/duplicates/workspace/selection",
        response_model=DuplicateWorkspaceState,
    )
    async def save_duplicate_workspace_selection(
        request: DuplicateWorkspaceSelectionUpdate,
    ) -> DuplicateWorkspaceState:
        try:
            return await require_duplicate_service().save_workspace_selection(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.patch(
        "/api/assets/duplicates/workspace/selection",
        response_model=DuplicateWorkspaceState,
    )
    async def update_duplicate_workspace_selection(
        request: DuplicateWorkspaceSelectionDelta,
    ) -> DuplicateWorkspaceState:
        try:
            return await require_duplicate_service().update_workspace_selection(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/workspace/membership",
        response_model=DuplicateWorkspaceMembership,
    )
    async def duplicate_workspace_membership(
        request: DuplicateWorkspaceMembershipRequest,
    ) -> DuplicateWorkspaceMembership:
        try:
            return await require_duplicate_service().workspace_membership(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.put(
        "/api/assets/duplicates/workspace/group",
        response_model=DuplicateGroupDraft,
    )
    async def save_duplicate_group_draft(
        request: DuplicateGroupDraftUpdate,
    ) -> DuplicateGroupDraft:
        try:
            return await require_duplicate_service().save_group_draft(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/workspace/apply-rules",
        response_model=DuplicateWorkspaceState,
    )
    async def apply_duplicate_workspace_rules(
        request: DuplicateAnalysisOptions,
    ) -> DuplicateWorkspaceState:
        try:
            return await require_duplicate_service().apply_rules(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/workspace/reset",
        response_model=DuplicateWorkspaceState,
    )
    async def reset_duplicate_workspace_decisions(
        request: DuplicateWorkspaceResetRequest,
    ) -> DuplicateWorkspaceState:
        try:
            return await require_duplicate_service().reset_workspace_decisions(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/workspace/auto-select/preview",
        response_model=DuplicateKeeperSelectionResult,
    )
    async def preview_duplicate_keeper_selection(
        request: DuplicateKeeperSelectionRequest,
    ) -> DuplicateKeeperSelectionResult:
        try:
            return await require_duplicate_service().preview_keeper_selection(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/workspace/auto-select/apply",
        response_model=DuplicateKeeperSelectionResult,
    )
    async def apply_duplicate_keeper_selection(
        request: DuplicateKeeperSelectionRequest,
    ) -> DuplicateKeeperSelectionResult:
        try:
            return await require_duplicate_service().apply_keeper_selection(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/workspace/preset",
        response_model=DuplicateWorkspaceState,
    )
    async def apply_duplicate_workspace_preset(
        request: DuplicateWorkspacePresetRequest,
    ) -> DuplicateWorkspaceState:
        try:
            return await require_duplicate_service().apply_workspace_preset(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/{group_id}/similarity-reference",
        response_model=ExactDuplicateGroup,
    )
    async def switch_cross_source_similarity_reference(
        group_id: str,
        request: DuplicateSimilarityReferenceRequest,
    ) -> ExactDuplicateGroup:
        try:
            return await require_duplicate_service().similarity_reference(
                group_id,
                request,
            )
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/plan",
        response_model=DuplicateResolutionPlan,
    )
    async def plan_duplicate_resolution(
        request: DuplicateResolutionPlanRequest,
    ) -> DuplicateResolutionPlan:
        try:
            return await require_duplicate_service().plan(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except RuntimeError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/duplicates/cross-source/execute",
        response_model=CrossSourceDuplicateTaskStart,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def execute_duplicate_resolution(
        request: DuplicateResolutionExecuteRequest,
    ) -> CrossSourceDuplicateTaskStart:
        try:
            return await require_duplicate_service().start_resolution(request)
        except RuntimeError as error:
            raise map_action_error(error) from error

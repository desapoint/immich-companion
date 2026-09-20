"""Asset search, restore, and summary route registration."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, status

from companion.asset_schema import (
    AlbumOption,
    AssetSearchMatchRequest,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetSortDirection,
    AssetSortField,
    AssetSummary,
    StructuredAssetSearchQuery,
)
from companion.duplicate_schema import DuplicateDiscoverySummary
from companion.immich import ImmichApiError


def register_asset_routes(
    app: FastAPI,
    *,
    require_asset_repository: Callable[[], object],
    require_immich: Callable[[], object],
    map_immich_error: Callable[[ImmichApiError], HTTPException],
    add_public_asset_urls: Callable[[AssetSearchResponse], AssetSearchResponse],
    add_public_asset_url: Callable[[AssetSummary | None], AssetSummary | None],
    composite_duplicate_repository: object | None,
) -> None:
    """Register search, restore, and asset summary endpoints."""

    @app.get("/api/assets", response_model=AssetSearchResponse)
    async def search_assets(
        query: str | None = Query(default=None, max_length=500),
        asset_type: Literal["IMAGE", "VIDEO", "AUDIO", "OTHER"] | None = Query(
            default=None,
            alias="type",
        ),
        taken_after: datetime | None = None,
        taken_before: datetime | None = None,
        min_width: int | None = Query(default=None, ge=1),
        max_width: int | None = Query(default=None, ge=1),
        min_height: int | None = Query(default=None, ge=1),
        max_height: int | None = Query(default=None, ge=1),
        min_aspect_ratio: float | None = Query(default=None, gt=0),
        max_aspect_ratio: float | None = Query(default=None, gt=0),
        favorite: bool | None = None,
        archived: bool | None = None,
        trashed: bool | None = None,
        sort_field: AssetSortField = "taken_at",
        sort_direction: AssetSortDirection = "desc",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=48, ge=1, le=200),
    ) -> AssetSearchResponse:
        repository = require_asset_repository()
        criteria = AssetSearchQuery(
            query=query,
            asset_type=asset_type,
            taken_after=taken_after,
            taken_before=taken_before,
            min_width=min_width,
            max_width=max_width,
            min_height=min_height,
            max_height=max_height,
            min_aspect_ratio=min_aspect_ratio,
            max_aspect_ratio=max_aspect_ratio,
            favorite=favorite,
            archived=archived,
            trashed=trashed,
            sort_field=sort_field,
            sort_direction=sort_direction,
            page=page,
            page_size=page_size,
        )
        return add_public_asset_urls(await repository.search(criteria))

    @app.post("/api/assets/search", response_model=AssetSearchResponse)
    async def search_assets_structured(
        criteria: StructuredAssetSearchQuery,
    ) -> AssetSearchResponse:
        repository = require_asset_repository()
        return add_public_asset_urls(await repository.search_structured(criteria))

    @app.get("/api/restore", response_model=AssetSearchResponse)
    async def search_restore_assets(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=48, ge=1, le=200),
    ) -> AssetSearchResponse:
        """List trashed assets directly from Immich, without local index data."""

        try:
            trashed_assets = [asset async for asset in require_immich().iter_trashed_assets()]
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        total = len(trashed_assets)
        offset = (page - 1) * page_size
        return AssetSearchResponse(
            items=[
                add_public_asset_url(AssetSummary.from_immich(asset))
                for asset in trashed_assets[offset : offset + page_size]
            ],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @app.post(
        "/api/assets/{asset_id}/search-match",
        response_model=AssetSummary | None,
    )
    async def match_asset_search(
        asset_id: UUID,
        criteria: AssetSearchMatchRequest,
    ) -> AssetSummary | None:
        repository = require_asset_repository()
        return add_public_asset_url(await repository.find_structured_match(asset_id, criteria))

    @app.get(
        "/api/assets/duplicates/summary",
        response_model=DuplicateDiscoverySummary,
    )
    async def duplicate_discovery_summary() -> DuplicateDiscoverySummary:
        if composite_duplicate_repository is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The persisted duplicate projection is unavailable.",
            )
        metadata = await composite_duplicate_repository.metadata()
        group_count, member_count = (
            await composite_duplicate_repository.unresolved_counts()
        )
        return DuplicateDiscoverySummary(
            authoritative_generation=metadata.authoritative_generation,
            group_count=group_count,
            member_count=member_count,
            evidence_count=metadata.evidence_count,
            last_success_at=metadata.last_success_at,
        )

    @app.get(
        "/api/assets/{asset_id}/summary",
        response_model=AssetSummary | None,
    )
    async def asset_summary(asset_id: UUID) -> AssetSummary | None:
        """Return one asset summary independently of the active search."""

        repository = require_asset_repository()
        return add_public_asset_url(await repository.get_asset_summary(asset_id))

    @app.get("/api/albums", response_model=list[AlbumOption])
    async def search_album_options() -> list[AlbumOption]:
        repository = require_asset_repository()
        return await repository.list_albums()

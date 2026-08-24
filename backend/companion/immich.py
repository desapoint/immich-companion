"""Typed, API-only Immich integration boundary."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from companion.config import Settings

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class ImmichApiError(RuntimeError):
    """Safe error raised for a failed Immich API operation."""

    def __init__(self, operation: str, status_code: int | None = None) -> None:
        detail = f"Immich operation {operation!r} failed"
        if status_code is not None:
            detail += f" with HTTP {status_code}"
        super().__init__(detail + ".")
        self.operation = operation
        self.status_code = status_code


class ImmichModel(BaseModel):
    """Base model that tolerates compatible fields added by Immich."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ImmichAsset(ImmichModel):
    """Asset fields used by companion sync, search, cards, and details."""

    id: UUID
    owner_id: UUID | None = Field(default=None, alias="ownerId")
    library_id: UUID | None = Field(default=None, alias="libraryId")
    asset_type: str = Field(alias="type")
    original_file_name: str = Field(alias="originalFileName")
    original_path: str | None = Field(default=None, alias="originalPath")
    original_mime_type: str | None = Field(default=None, alias="originalMimeType")
    checksum: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    thumbhash: str | None = None
    file_created_at: datetime = Field(alias="fileCreatedAt")
    file_modified_at: datetime = Field(alias="fileModifiedAt")
    local_date_time: datetime | None = Field(default=None, alias="localDateTime")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    is_favorite: bool = Field(default=False, alias="isFavorite")
    is_archived: bool = Field(default=False, alias="isArchived")
    is_trashed: bool = Field(default=False, alias="isTrashed")
    is_offline: bool = Field(default=False, alias="isOffline")
    is_edited: bool = Field(default=False, alias="isEdited")
    has_metadata: bool = Field(default=False, alias="hasMetadata")
    visibility: str | None = None
    live_photo_video_id: str | None = Field(default=None, alias="livePhotoVideoId")
    exif_info: dict[str, Any] | None = Field(default=None, alias="exifInfo")
    people: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[dict[str, Any]] = Field(default_factory=list)
    stack: dict[str, Any] | None = None


class ImmichAlbum(ImmichModel):
    """Album metadata plus membership resolved through supported Immich APIs."""

    id: UUID
    album_name: str = Field(alias="albumName")
    description: str = ""
    album_thumbnail_asset_id: UUID | None = Field(default=None, alias="albumThumbnailAssetId")
    asset_count: int = Field(default=0, alias="assetCount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    asset_ids: list[UUID] = Field(default_factory=list, exclude=True)


class ImmichStack(ImmichModel):
    """Stack metadata used to enrich every synchronized member."""

    id: UUID
    primary_asset_id: UUID = Field(alias="primaryAssetId")
    assets: list[ImmichAsset]


class ImmichTag(ImmichModel):
    """Tag metadata plus memberships resolved through supported Immich APIs."""

    id: UUID
    name: str
    value: str
    color: str | None = None
    parent_id: UUID | None = Field(default=None, alias="parentId")
    asset_ids: list[UUID] = Field(default_factory=list, exclude=True)


class ImmichAssetSearchPage(ImmichModel):
    """Asset portion of an Immich metadata search response."""

    count: int
    total: int
    items: list[ImmichAsset]
    next_page: str | None = Field(alias="nextPage")


class ImmichSearchResponse(ImmichModel):
    """Typed metadata search response wrapper."""

    assets: ImmichAssetSearchPage


@dataclass(frozen=True, slots=True)
class ImmichMedia:
    """Binary media returned by Immich with safe response metadata."""

    content: bytes
    media_type: str
    etag: str | None
    cache_control: str | None


class ImmichApiClient:
    """Centralize authentication, retries, typed parsing, and media access."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        if not self._settings.immich_configured:
            raise ImmichApiError("configuration")

        assert self._settings.immich_url is not None
        api_key = self._settings.resolve_immich_api_key()
        assert api_key is not None
        return httpx.AsyncClient(
            base_url=str(self._settings.immich_url).rstrip("/"),
            headers={"x-api-key": api_key},
            timeout=self._settings.immich_timeout_seconds,
            transport=self._transport,
            follow_redirects=False,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        **kwargs: Any,
    ) -> httpx.Response:
        attempts = self._settings.immich_retry_attempts
        for attempt in range(attempts):
            try:
                async with self._client() as client:
                    response = await client.request(method, path, **kwargs)
            except httpx.RequestError as error:
                if attempt + 1 >= attempts:
                    raise ImmichApiError(operation) from error
            else:
                if response.status_code not in TRANSIENT_STATUS_CODES:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as error:
                        raise ImmichApiError(operation, response.status_code) from error
                    return response
                if attempt + 1 >= attempts:
                    raise ImmichApiError(operation, response.status_code)

            backoff = self._settings.immich_retry_backoff_seconds * (2**attempt)
            if backoff:
                await asyncio.sleep(backoff)

        raise ImmichApiError(operation)

    async def check(self) -> dict[str, Any]:
        """Check connectivity without exposing credentials or internal URLs."""

        if not self._settings.immich_configured:
            return {
                "status": "not_configured",
                "configured": False,
                "detail": "Set IMMICH_URL and IMMICH_API_KEY to enable connectivity checks.",
            }

        started = perf_counter()
        try:
            await self._request("GET", "/api/server/ping", operation="ping")
        except ImmichApiError as error:
            detail = (
                f"Immich returned HTTP {error.status_code}."
                if error.status_code is not None
                else "Immich request failed."
            )
            return {"status": "error", "configured": True, "detail": detail}

        return {
            "status": "ok",
            "configured": True,
            "latency_ms": round((perf_counter() - started) * 1000, 1),
        }

    async def search_assets_page(
        self,
        page: int,
        *,
        size: int = 250,
        album_ids: list[UUID] | None = None,
        tag_ids: list[UUID] | None = None,
    ) -> ImmichAssetSearchPage:
        """Retrieve one stable metadata-search page with useful related data."""

        payload: dict[str, Any] = {
            "page": page,
            "size": size,
            "order": "asc",
            "withExif": True,
            "withPeople": True,
            "withStacked": True,
            "withDeleted": True,
        }
        if album_ids:
            payload["albumIds"] = [str(album_id) for album_id in album_ids]
        if tag_ids:
            payload["tagIds"] = [str(tag_id) for tag_id in tag_ids]
        response = await self._request(
            "POST",
            "/api/search/metadata",
            operation="search assets",
            json=payload,
        )
        return ImmichSearchResponse.model_validate(response.json()).assets

    async def iter_assets(self, *, page_size: int = 250) -> AsyncIterator[ImmichAsset]:
        """Yield all assets while guarding against repeated pagination tokens."""

        page_number = 1
        seen_tokens: set[str] = set()
        while True:
            page = await self.search_assets_page(page_number, size=page_size)
            for asset in page.items:
                yield asset

            token = page.next_page
            if token is None:
                return
            if token in seen_tokens:
                raise ImmichApiError("search assets pagination")
            seen_tokens.add(token)
            try:
                page_number = int(token)
            except ValueError as error:
                raise ImmichApiError("search assets pagination") from error

    async def get_asset(self, asset_id: UUID) -> ImmichAsset:
        """Retrieve live details for one Immich asset."""

        response = await self._request(
            "GET",
            f"/api/assets/{asset_id}",
            operation="get asset",
        )
        return ImmichAsset.model_validate(response.json())

    async def get_thumbnail(
        self,
        asset_id: UUID,
        *,
        size: Literal["thumbnail", "preview"] = "thumbnail",
    ) -> ImmichMedia:
        """Retrieve safe thumbnail or preview bytes for browser proxying."""

        response = await self._request(
            "GET",
            f"/api/assets/{asset_id}/thumbnail",
            operation="get asset thumbnail",
            params={"size": size},
        )
        return ImmichMedia(
            content=response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            etag=response.headers.get("etag"),
            cache_control=response.headers.get("cache-control"),
        )

    async def get_original(self, asset_id: UUID) -> ImmichMedia:
        """Retrieve the original/full-size asset for the bounded viewer proxy."""

        response = await self._request(
            "GET",
            f"/api/assets/{asset_id}/original",
            operation="get original asset",
        )
        return ImmichMedia(
            content=response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            etag=response.headers.get("etag"),
            cache_control=response.headers.get("cache-control"),
        )

    async def list_albums(self, assets: list[ImmichAsset]) -> list[ImmichAlbum]:
        """List albums and resolve memberships without direct Immich database access."""

        response = await self._request("GET", "/api/albums", operation="list albums")
        albums = [ImmichAlbum.model_validate(payload) for payload in response.json()]
        synchronized_ids = {asset.id for asset in assets}
        resolved: list[ImmichAlbum] = []
        for album in albums:
            asset_ids: list[UUID] = []
            page_number = 1
            seen_tokens: set[str] = set()
            while True:
                page = await self.search_assets_page(
                    page_number,
                    size=1000,
                    album_ids=[album.id],
                )
                asset_ids.extend(
                    asset.id for asset in page.items if asset.id in synchronized_ids
                )
                if page.next_page is None:
                    break
                if page.next_page in seen_tokens:
                    raise ImmichApiError("album membership pagination")
                seen_tokens.add(page.next_page)
                try:
                    page_number = int(page.next_page)
                except ValueError as error:
                    raise ImmichApiError("album membership pagination") from error
            resolved.append(album.model_copy(update={"asset_ids": asset_ids}))
        return resolved

    async def list_stacks(self) -> list[ImmichStack]:
        """List current stacks through the supported Immich API."""

        response = await self._request("GET", "/api/stacks", operation="list stacks")
        return [ImmichStack.model_validate(payload) for payload in response.json()]

    async def list_tags(self, assets: list[ImmichAsset]) -> list[ImmichTag]:
        """List tags and resolve memberships omitted by general asset traversal."""

        response = await self._request("GET", "/api/tags", operation="list tags")
        tags = [ImmichTag.model_validate(payload) for payload in response.json()]
        synchronized_ids = {asset.id for asset in assets}
        resolved: list[ImmichTag] = []
        for tag in tags:
            asset_ids: list[UUID] = []
            page_number = 1
            seen_tokens: set[str] = set()
            while True:
                page = await self.search_assets_page(
                    page_number,
                    size=1000,
                    tag_ids=[tag.id],
                )
                asset_ids.extend(
                    asset.id for asset in page.items if asset.id in synchronized_ids
                )
                if page.next_page is None:
                    break
                if page.next_page in seen_tokens:
                    raise ImmichApiError("tag membership pagination")
                seen_tokens.add(page.next_page)
                try:
                    page_number = int(page.next_page)
                except ValueError as error:
                    raise ImmichApiError("tag membership pagination") from error
            resolved.append(tag.model_copy(update={"asset_ids": asset_ids}))
        return resolved

    def public_asset_url(self, asset_id: UUID) -> str | None:
        """Build an optional browser-facing link without exposing the API key."""

        if self._settings.immich_public_url is None:
            return None
        return f"{str(self._settings.immich_public_url).rstrip('/')}/photos/{asset_id}"


# Backward-compatible name retained for existing imports while the API client expands.
ImmichHealthClient = ImmichApiClient

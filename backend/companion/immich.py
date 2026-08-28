"""Typed, API-only Immich integration boundary."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from companion.config import Settings
from companion.sync_schema import SyncCapabilities, SyncEvent

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
SUPPORTED_IMMICH_MAJOR = 3
SUPPORTED_IMMICH_MINOR = 1
SUPPORTED_IMMICH_API_VERSION = f"{SUPPORTED_IMMICH_MAJOR}.{SUPPORTED_IMMICH_MINOR}.x"
TRASH_SEARCH_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


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


class ImmichServerVersion(ImmichModel):
    """Version response exposed by the pinned Immich server API."""

    major: int = Field(ge=0)
    minor: int = Field(ge=0)
    patch: int = Field(ge=0)
    prerelease: int | None = Field(default=None, ge=0)

    @property
    def label(self) -> str:
        """Return a safe human-readable version label."""

        suffix = f"-prerelease.{self.prerelease}" if self.prerelease is not None else ""
        return f"{self.major}.{self.minor}.{self.patch}{suffix}"

    @property
    def is_compatible(self) -> bool:
        """Return whether this server matches the supported stable API line."""

        return (
            self.major == SUPPORTED_IMMICH_MAJOR
            and self.minor == SUPPORTED_IMMICH_MINOR
            and self.prerelease is None
        )


class ImmichCompatibilityReport(BaseModel):
    """Safe compatibility information suitable for the companion status API."""

    status: Literal["compatible", "incompatible", "unknown"]
    server_version: ImmichServerVersion | None = None
    supported_api_version: str = SUPPORTED_IMMICH_API_VERSION
    detail: str


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

    @property
    def includes_tags(self) -> bool:
        """Whether the response explicitly included the tags relationship."""

        return "tags" in self.model_fields_set


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
    asset_count: int = Field(default=0, alias="assetCount")
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

    async def get_server_version(self) -> ImmichServerVersion:
        """Retrieve and validate the server version through the API boundary."""

        response = await self._request(
            "GET", "/api/server/version", operation="get server version"
        )
        return ImmichServerVersion.model_validate(response.json())

    async def compatibility_report(self) -> ImmichCompatibilityReport:
        """Report compatibility without exposing remote URLs or request details."""

        if not self._settings.immich_configured:
            return ImmichCompatibilityReport(
                status="unknown",
                detail="Immich is not configured.",
            )

        try:
            server_version = await self.get_server_version()
        except ImmichApiError as error:
            detail = (
                "Immich does not expose the server-version endpoint."
                if error.status_code in {404, 405, 501}
                else "Immich server version could not be determined."
            )
            return ImmichCompatibilityReport(status="unknown", detail=detail)

        if server_version.is_compatible:
            return ImmichCompatibilityReport(
                status="compatible",
                server_version=server_version,
                detail=f"Immich {server_version.label} matches the supported API line.",
            )
        return ImmichCompatibilityReport(
            status="incompatible",
            server_version=server_version,
            detail=(
                f"Immich {server_version.label} is outside the supported "
                f"{SUPPORTED_IMMICH_API_VERSION} API line."
            ),
        )

    async def sync_capabilities(self) -> SyncCapabilities:
        """Probe optional change-stream support without assuming it exists."""

        try:
            response = await self._request(
                "GET", "/api/sync/capabilities", operation="sync capabilities"
            )
        except ImmichApiError as error:
            if error.status_code in {404, 405, 501}:
                return SyncCapabilities()
            raise
        payload = response.json()
        return SyncCapabilities(
            stream=bool(payload.get("stream", False)),
            acknowledgements=bool(payload.get("acknowledgements", False)),
            bounded_updates=bool(payload.get("boundedUpdates", True)),
        )

    async def iter_sync_events(self, cursor: str | None = None) -> AsyncIterator[SyncEvent]:
        """Read optional newline-delimited events; unsupported streams fail safely."""

        response = await self._request(
            "GET",
            "/api/sync/stream",
            operation="sync stream",
            params={"cursor": cursor} if cursor else None,
        )
        for line in response.text.splitlines():
            if line.strip():
                yield SyncEvent.model_validate_json(line)

    async def acknowledge_sync_event(self, event_id: str) -> None:
        """Acknowledge one event only after its local checkpoint is durable."""

        await self._request(
            "POST",
            "/api/sync/ack",
            operation="sync event acknowledgement",
            json={"id": event_id},
        )

    async def search_assets_page(
        self,
        page: int,
        *,
        size: int = 250,
        album_ids: list[UUID] | None = None,
        tag_ids: list[UUID] | None = None,
        trashed: bool | None = None,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
    ) -> ImmichAssetSearchPage:
        """Retrieve one lightweight active-asset metadata-search page."""

        payload: dict[str, Any] = {
            "page": page,
            "size": size,
            "order": "asc",
            "withExif": False,
            "withPeople": False,
            # Immich hides stack children when this is false. Keep the complete
            # inventory here; stack relationships are still synchronized by
            # the separate stack stage and stripped before asset persistence.
            "withStacked": True,
            "withDeleted": bool(trashed),
            "withArchived": True,
        }
        if album_ids:
            payload["albumIds"] = [str(album_id) for album_id in album_ids]
        if tag_ids:
            payload["tagIds"] = [str(tag_id) for tag_id in tag_ids]
        if trashed:
            payload["trashedAfter"] = TRASH_SEARCH_EPOCH.isoformat()
        if updated_after:
            payload["updatedAfter"] = updated_after.isoformat()
        if updated_before:
            payload["updatedBefore"] = updated_before.isoformat()
        response = await self._request(
            "POST",
            "/api/search/metadata",
            operation="search assets",
            json=payload,
        )
        return ImmichSearchResponse.model_validate(response.json()).assets

    async def iter_assets(
        self,
        *,
        page_size: int = 250,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
        start_page: int = 1,
    ) -> AsyncIterator[ImmichAsset]:
        """Yield active lightweight assets while guarding against repeated page tokens."""

        page_number = start_page
        seen_tokens: set[str] = set()
        while True:
            page = await self.search_assets_page(
                page_number,
                size=page_size,
                updated_after=updated_after,
                updated_before=updated_before,
            )
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

    async def iter_trashed_assets(self, *, page_size: int = 1000) -> AsyncIterator[ImmichAsset]:
        """Yield the complete live Immich trash and reject leaked active results."""

        page_number = 1
        seen_tokens: set[str] = set()
        while True:
            page = await self.search_assets_page(page_number, size=page_size, trashed=True)
            for asset in page.items:
                if asset.is_trashed:
                    yield asset

            token = page.next_page
            if token is None:
                return
            if token in seen_tokens:
                raise ImmichApiError("search trashed assets pagination")
            seen_tokens.add(token)
            try:
                page_number = int(token)
            except ValueError as error:
                raise ImmichApiError("search trashed assets pagination") from error

    async def count_assets(
        self,
        *,
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
    ) -> int:
        """Return the bounded asset population used by a sync progress estimate."""

        page = await self.search_assets_page(
            1,
            size=1,
            updated_after=updated_after,
            updated_before=updated_before,
        )
        return page.total

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

    async def remove_assets_from_album(self, album_id: UUID, asset_ids: list[UUID]) -> None:
        """Remove current members from one album through the supported API."""

        await self._request(
            "DELETE",
            f"/api/albums/{album_id}/assets",
            operation="remove assets from album",
            json={"ids": [str(asset_id) for asset_id in asset_ids]},
        )

    async def add_assets_to_album(self, album_id: UUID, asset_ids: list[UUID]) -> None:
        """Add missing members to one album through the supported API."""

        await self._request(
            "PUT",
            f"/api/albums/{album_id}/assets",
            operation="add assets to album",
            json={"ids": [str(asset_id) for asset_id in asset_ids]},
        )

    async def remove_assets_from_tag(self, tag_id: UUID, asset_ids: list[UUID]) -> None:
        """Remove current members from one tag through the supported API."""

        await self._request(
            "DELETE",
            f"/api/tags/{tag_id}/assets",
            operation="remove assets from tag",
            json={"ids": [str(asset_id) for asset_id in asset_ids]},
        )

    async def add_assets_to_tag(self, tag_id: UUID, asset_ids: list[UUID]) -> None:
        """Add missing members to one tag through the supported API."""

        await self._request(
            "PUT",
            f"/api/tags/{tag_id}/assets",
            operation="add assets to tag",
            json={"ids": [str(asset_id) for asset_id in asset_ids]},
        )

    async def set_assets_archived(self, asset_ids: list[UUID], archived: bool) -> None:
        """Set archive visibility for a batch through Immich."""

        await self._request(
            "PUT",
            "/api/assets",
            operation="archive assets" if archived else "unarchive assets",
            json={
                "ids": [str(asset_id) for asset_id in asset_ids],
                "visibility": "archive" if archived else "timeline",
            },
        )

    async def set_assets_favorite(self, asset_ids: list[UUID], favorite: bool) -> None:
        """Set favorite state for a batch through Immich."""

        await self._request(
            "PUT",
            "/api/assets",
            operation="favorite assets" if favorite else "unfavorite assets",
            json={
                "ids": [str(asset_id) for asset_id in asset_ids],
                "isFavorite": favorite,
            },
        )

    async def trash_assets(self, asset_ids: list[UUID]) -> None:
        """Move a batch to trash without permanent deletion."""

        await self._request(
            "DELETE",
            "/api/assets",
            operation="trash assets",
            json={"ids": [str(asset_id) for asset_id in asset_ids], "force": False},
        )

    async def restore_assets(self, asset_ids: list[UUID]) -> None:
        """Restore a batch from trash through Immich."""

        await self._request(
            "POST",
            "/api/trash/restore/assets",
            operation="restore assets",
            json={"ids": [str(asset_id) for asset_id in asset_ids]},
        )

    async def list_album_catalog(self) -> list[ImmichAlbum]:
        """Fetch the compact album catalog before any media traversal."""

        response = await self._request("GET", "/api/albums", operation="list albums")
        return [ImmichAlbum.model_validate(payload) for payload in response.json()]

    async def create_album(self, name: str, description: str = "") -> ImmichAlbum:
        response = await self._request(
            "POST", "/api/albums", operation="create album",
            json={"albumName": name, "description": description, "assetIds": []},
        )
        return ImmichAlbum.model_validate(response.json())

    async def update_album(self, album_id: UUID, *, name: str | None = None,
                           description: str | None = None) -> ImmichAlbum:
        payload: dict[str, Any] = {}
        if name is not None:
            payload["albumName"] = name
        if description is not None:
            payload["description"] = description
        response = await self._request(
            "PUT", f"/api/albums/{album_id}", operation="update album", json=payload,
        )
        return ImmichAlbum.model_validate(response.json())

    async def delete_album(self, album_id: UUID) -> None:
        await self._request("DELETE", f"/api/albums/{album_id}", operation="delete album")

    async def list_albums_for_asset(self, asset_id: UUID) -> list[ImmichAlbum]:
        """Retrieve the albums containing one asset through the supported API."""

        response = await self._request(
            "GET",
            "/api/albums",
            operation="list albums for asset",
            params={"assetId": str(asset_id)},
        )
        return [ImmichAlbum.model_validate(payload) for payload in response.json()]

    async def iter_album_asset_ids(
        self,
        album_id: UUID,
        *,
        page_size: int = 1000,
        start_page: int = 1,
    ) -> AsyncIterator[list[UUID]]:
        """Yield bounded album-membership pages through metadata search."""

        page_number = start_page
        seen_tokens: set[str] = set()
        while True:
            page = await self.search_assets_page(
                page_number,
                size=page_size,
                album_ids=[album_id],
            )
            yield [asset.id for asset in page.items]
            if page.next_page is None:
                return
            if page.next_page in seen_tokens:
                raise ImmichApiError("album membership pagination")
            seen_tokens.add(page.next_page)
            try:
                page_number = int(page.next_page)
            except ValueError as error:
                raise ImmichApiError("album membership pagination") from error

    async def count_album_asset_ids(self, album_id: UUID) -> int:
        """Return the known album membership population for progress reporting."""

        page = await self.search_assets_page(1, size=1, album_ids=[album_id])
        return page.total

    async def list_albums(self, assets: list[ImmichAsset]) -> list[ImmichAlbum]:
        """Compatibility helper returning catalogs with resolved memberships."""

        albums = await self.list_album_catalog()
        synchronized_ids = {asset.id for asset in assets}
        resolved: list[ImmichAlbum] = []
        for album in albums:
            asset_ids: list[UUID] = []
            async for page_ids in self.iter_album_asset_ids(album.id):
                asset_ids.extend(asset_id for asset_id in page_ids if asset_id in synchronized_ids)
            resolved.append(album.model_copy(update={"asset_ids": asset_ids}))
        return resolved

    async def list_stacks(self) -> list[ImmichStack]:
        """List current stacks through the supported Immich API."""

        response = await self._request("GET", "/api/stacks", operation="list stacks")
        return [ImmichStack.model_validate(payload) for payload in response.json()]

    async def create_stack(self, asset_ids: list[UUID]) -> None:
        """Create one Immich stack from the selected assets."""

        await self._request(
            "POST",
            "/api/stacks",
            json={"assetIds": [str(asset_id) for asset_id in asset_ids]},
            operation="create stack",
        )

    async def remove_asset_from_stack(self, stack_id: UUID, asset_id: UUID) -> None:
        """Remove one asset from a stack through Immich's stack API."""

        await self._request(
            "DELETE",
            f"/api/stacks/{stack_id}/assets/{asset_id}",
            operation="remove asset from stack",
        )

    async def update_stack_primary(self, stack_id: UUID, asset_id: UUID) -> None:
        """Promote an existing member before removing a stack primary."""

        await self._request(
            "PUT",
            f"/api/stacks/{stack_id}",
            json={"primaryAssetId": str(asset_id)},
            operation="update stack primary",
        )

    async def delete_stack(self, stack_id: UUID) -> None:
        """Remove an entire stack while preserving its assets."""

        await self._request(
            "DELETE",
            f"/api/stacks/{stack_id}",
            operation="remove stack",
        )

    async def list_tag_catalog(self) -> list[ImmichTag]:
        """Fetch the compact tag catalog before any media traversal."""

        response = await self._request("GET", "/api/tags", operation="list tags")
        return [ImmichTag.model_validate(payload) for payload in response.json()]

    async def create_tag(self, name: str, color: str | None = None,
                         parent_id: UUID | None = None) -> ImmichTag:
        payload: dict[str, Any] = {"name": name}
        if color is not None:
            payload["color"] = color
        if parent_id is not None:
            payload["parentId"] = str(parent_id)
        response = await self._request("POST", "/api/tags", operation="create tag", json=payload)
        return ImmichTag.model_validate(response.json())

    async def update_tag(self, tag_id: UUID, *, name: str | None = None,
                         color: str | None = None) -> ImmichTag:
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if color is not None:
            payload["color"] = color
        response = await self._request(
            "PUT", f"/api/tags/{tag_id}", operation="update tag", json=payload,
        )
        return ImmichTag.model_validate(response.json())

    async def delete_tag(self, tag_id: UUID) -> None:
        await self._request("DELETE", f"/api/tags/{tag_id}", operation="delete tag")

    async def reparent_tag(
        self,
        tag_id: UUID,
        *,
        name: str,
        color: str | None,
        parent_id: UUID | None,
        catalog: list[ImmichTag],
    ) -> ImmichTag:
        """Recreate a tag subtree under a new parent while preserving memberships."""

        by_parent: dict[UUID, list[ImmichTag]] = {}
        by_id = {tag.id: tag for tag in catalog}
        for tag in catalog:
            if tag.parent_id is not None:
                by_parent.setdefault(tag.parent_id, []).append(tag)
        source = by_id[tag_id]
        subtree: list[ImmichTag] = []

        def visit(tag: ImmichTag) -> None:
            subtree.append(tag)
            for child in by_parent.get(tag.id, []):
                visit(child)

        visit(source)
        replacements: dict[UUID, ImmichTag] = {}
        try:
            for old in subtree:
                replacement = await self.create_tag(
                    name if old.id == tag_id else old.name,
                    color if old.id == tag_id else old.color,
                    parent_id if old.id == tag_id else replacements[old.parent_id].id,
                )
                replacements[old.id] = replacement
                asset_ids: list[UUID] = []
                async for page_ids in self.iter_tag_asset_ids(old.id):
                    asset_ids.extend(page_ids)
                for start in range(0, len(asset_ids), 1000):
                    await self.add_assets_to_tag(replacement.id, asset_ids[start : start + 1000])
                if await self.count_tag_asset_ids(replacement.id) != len(set(asset_ids)):
                    raise ImmichApiError("tag membership verification")
            for old in reversed(subtree):
                await self.delete_tag(old.id)
        except Exception:
            for replacement in reversed(list(replacements.values())):
                with suppress(ImmichApiError):
                    await self.delete_tag(replacement.id)
            raise
        return replacements[tag_id]

    async def iter_tag_asset_ids(
        self,
        tag_id: UUID,
        *,
        page_size: int = 1000,
        start_page: int = 1,
    ) -> AsyncIterator[list[UUID]]:
        """Yield bounded tag-membership pages through metadata search."""

        page_number = start_page
        seen_tokens: set[str] = set()
        while True:
            page = await self.search_assets_page(
                page_number,
                size=page_size,
                tag_ids=[tag_id],
            )
            yield [asset.id for asset in page.items]
            if page.next_page is None:
                return
            if page.next_page in seen_tokens:
                raise ImmichApiError("tag membership pagination")
            seen_tokens.add(page.next_page)
            try:
                page_number = int(page.next_page)
            except ValueError as error:
                raise ImmichApiError("tag membership pagination") from error

    async def count_tag_asset_ids(self, tag_id: UUID) -> int:
        """Return the known tag membership population for progress reporting."""

        page = await self.search_assets_page(1, size=1, tag_ids=[tag_id])
        return page.total

    async def list_tags(self, assets: list[ImmichAsset]) -> list[ImmichTag]:
        """Compatibility helper returning catalogs with resolved memberships."""

        tags = await self.list_tag_catalog()
        synchronized_ids = {asset.id for asset in assets}
        resolved: list[ImmichTag] = []
        for tag in tags:
            asset_ids: list[UUID] = []
            async for page_ids in self.iter_tag_asset_ids(tag.id):
                asset_ids.extend(asset_id for asset_id in page_ids if asset_id in synchronized_ids)
            resolved.append(tag.model_copy(update={"asset_ids": asset_ids}))
        return resolved

    def public_asset_url(self, asset_id: UUID) -> str | None:
        """Build an optional browser-facing link without exposing the API key."""

        if self._settings.immich_public_url is None:
            return None
        return f"{str(self._settings.immich_public_url).rstrip('/')}/photos/{asset_id}"


# Backward-compatible name retained for existing imports while the API client expands.
ImmichHealthClient = ImmichApiClient

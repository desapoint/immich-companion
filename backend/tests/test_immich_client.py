"""Contract tests for the centralized Immich API boundary."""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from companion.config import Settings
from companion.immich import ImmichApiClient, ImmichApiError, ImmichAsset

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "immich_url": "http://immich.test",
        "immich_public_url": "https://photos.example.test/base/",
        "immich_api_key": "private-test-key",
        "immich_retry_attempts": 3,
        "immich_retry_backoff_seconds": 0,
    }
    values.update(overrides)
    return Settings(**values)


def asset_payload(asset_id: UUID, filename: str) -> dict[str, object]:
    return {
        "id": str(asset_id),
        "ownerId": "33333333-3333-4333-8333-333333333333",
        "type": "IMAGE",
        "originalFileName": filename,
        "originalPath": f"upload/library/{filename}",
        "originalMimeType": "image/jpeg",
        "checksum": "base64-checksum",
        "width": 2048,
        "height": 1365,
        "fileCreatedAt": "2026-08-20T12:00:00Z",
        "fileModifiedAt": "2026-08-20T12:00:00Z",
        "localDateTime": "2026-08-20T08:00:00-04:00",
        "createdAt": "2026-08-20T12:01:00Z",
        "updatedAt": "2026-08-20T12:02:00Z",
        "isFavorite": False,
        "isArchived": False,
        "isTrashed": False,
        "isOffline": False,
        "isEdited": False,
        "hasMetadata": True,
        "visibility": "timeline",
        "thumbhash": "hash",
        "duration": None,
        "exifInfo": {"fileSizeInByte": 4096, "make": "Test Camera"},
        "people": [],
        "tags": [],
    }


@pytest.mark.asyncio
async def test_metadata_search_is_typed_authenticated_and_paginated() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-api-key"] == "private-test-key"
        assert request.url.path == "/api/search/metadata"
        body = json.loads(request.content)
        assert body["withExif"] is True
        assert body["withDeleted"] is True
        page = int(body["page"])
        item = asset_payload(ASSET_ONE if page == 1 else ASSET_TWO, f"page-{page}.jpg")
        return httpx.Response(
            200,
            json={
                "assets": {
                    "count": 1,
                    "total": 2,
                    "facets": [],
                    "items": [item],
                    "nextPage": "2" if page == 1 else None,
                },
                "albums": {"total": 0, "count": 0, "items": [], "facets": []},
            },
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    assets = [asset async for asset in client.iter_assets(page_size=25)]

    assert [asset.id for asset in assets] == [ASSET_ONE, ASSET_TWO]
    assert assets[0].original_file_name == "page-1.jpg"
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_transient_retries_are_bounded_and_secrets_are_redacted() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"message": "try later"})

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ImmichApiError) as raised:
        await client.search_assets_page(1)

    assert attempts == 3
    assert raised.value.status_code == 503
    assert "private-test-key" not in str(raised.value)
    assert "immich.test" not in str(raised.value)


@pytest.mark.asyncio
async def test_detail_and_thumbnail_contracts_preserve_safe_media_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/assets/{ASSET_ONE}":
            return httpx.Response(200, json=asset_payload(ASSET_ONE, "detail.jpg"))
        if request.url.path == f"/api/assets/{ASSET_ONE}/thumbnail":
            assert request.url.params["size"] == "preview"
            return httpx.Response(
                200,
                content=b"preview-bytes",
                headers={
                    "content-type": "image/webp",
                    "etag": '"preview-etag"',
                    "cache-control": "private, max-age=60",
                },
            )
        assert request.url.path == f"/api/assets/{ASSET_ONE}/original"
        return httpx.Response(
            200,
            content=b"original-bytes",
            headers={"content-type": "image/jpeg"},
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    detail = await client.get_asset(ASSET_ONE)
    media = await client.get_thumbnail(ASSET_ONE, size="preview")
    original = await client.get_original(ASSET_ONE)

    assert detail.original_file_name == "detail.jpg"
    assert media.content == b"preview-bytes"
    assert media.media_type == "image/webp"
    assert media.etag == '"preview-etag"'
    assert original.content == b"original-bytes"
    assert original.media_type == "image/jpeg"
    assert client.public_asset_url(ASSET_ONE) == f"https://photos.example.test/base/photos/{ASSET_ONE}"


@pytest.mark.asyncio
async def test_album_memberships_use_paged_metadata_search() -> None:
    album_id = UUID("44444444-4444-4444-8444-444444444444")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/api/albums"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(album_id),
                        "albumName": "Overlap A",
                        "description": "Test album",
                        "albumThumbnailAssetId": str(ASSET_ONE),
                        "assetCount": 1,
                        "createdAt": "2026-08-20T12:00:00Z",
                        "updatedAt": "2026-08-20T12:00:00Z",
                    }
                ],
            )
        body = json.loads(request.content)
        assert body["albumIds"] == [str(album_id)]
        assert body["size"] == 1000
        return httpx.Response(
            200,
            json={
                "assets": {
                    "count": 1,
                    "total": 1,
                    "items": [asset_payload(ASSET_ONE, "album-member.png")],
                    "nextPage": None,
                }
            },
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    asset = ImmichAsset.model_validate(asset_payload(ASSET_ONE, "album-member.png"))
    albums = await client.list_albums([asset])

    assert len(albums) == 1
    assert albums[0].album_name == "Overlap A"
    assert albums[0].asset_ids == [ASSET_ONE]


@pytest.mark.asyncio
async def test_stack_contract_includes_all_typed_members() -> None:
    stack_id = UUID("55555555-5555-4555-8555-555555555555")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/stacks"
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(stack_id),
                    "primaryAssetId": str(ASSET_ONE),
                    "assets": [
                        asset_payload(ASSET_ONE, "stack-primary.png"),
                        asset_payload(ASSET_TWO, "stack-child.png"),
                    ],
                }
            ],
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    stacks = await client.list_stacks()

    assert len(stacks) == 1
    assert stacks[0].primary_asset_id == ASSET_ONE
    assert [asset.id for asset in stacks[0].assets] == [ASSET_ONE, ASSET_TWO]


@pytest.mark.asyncio
async def test_tag_memberships_use_paged_metadata_search() -> None:
    tag_id = UUID("66666666-6666-4666-8666-666666666666")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/api/tags"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(tag_id),
                        "name": "Review",
                        "value": "Review",
                        "color": "#d97706",
                    }
                ],
            )
        body = json.loads(request.content)
        assert body["tagIds"] == [str(tag_id)]
        assert body["size"] == 1000
        return httpx.Response(
            200,
            json={
                "assets": {
                    "count": 1,
                    "total": 1,
                    "items": [asset_payload(ASSET_ONE, "tagged.png")],
                    "nextPage": None,
                }
            },
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    asset = ImmichAsset.model_validate(asset_payload(ASSET_ONE, "tagged.png"))
    tags = await client.list_tags([asset])

    assert len(tags) == 1
    assert tags[0].name == "Review"
    assert tags[0].asset_ids == [ASSET_ONE]


@pytest.mark.asyncio
async def test_bulk_mutations_use_supported_immich_endpoints() -> None:
    album_id = UUID("44444444-4444-4444-8444-444444444444")
    tag_id = UUID("66666666-6666-4666-8666-666666666666")
    requests: list[tuple[str, str, dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={})

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    await client.remove_assets_from_album(album_id, [ASSET_ONE])
    await client.add_assets_to_album(album_id, [ASSET_ONE])
    await client.remove_assets_from_tag(tag_id, [ASSET_TWO])
    await client.add_assets_to_tag(tag_id, [ASSET_TWO])
    await client.set_assets_archived([ASSET_ONE], True)
    await client.set_assets_archived([ASSET_ONE], False)
    await client.set_assets_favorite([ASSET_TWO], True)
    await client.set_assets_favorite([ASSET_TWO], False)
    await client.trash_assets([ASSET_ONE])
    await client.restore_assets([ASSET_ONE])

    assert requests == [
        ("DELETE", f"/api/albums/{album_id}/assets", {"ids": [str(ASSET_ONE)]}),
        ("PUT", f"/api/albums/{album_id}/assets", {"ids": [str(ASSET_ONE)]}),
        ("DELETE", f"/api/tags/{tag_id}/assets", {"ids": [str(ASSET_TWO)]}),
        ("PUT", f"/api/tags/{tag_id}/assets", {"ids": [str(ASSET_TWO)]}),
        ("PUT", "/api/assets", {"ids": [str(ASSET_ONE)], "visibility": "archive"}),
        ("PUT", "/api/assets", {"ids": [str(ASSET_ONE)], "visibility": "timeline"}),
        ("PUT", "/api/assets", {"ids": [str(ASSET_TWO)], "isFavorite": True}),
        ("PUT", "/api/assets", {"ids": [str(ASSET_TWO)], "isFavorite": False}),
        ("DELETE", "/api/assets", {"ids": [str(ASSET_ONE)], "force": False}),
        ("POST", "/api/trash/restore/assets", {"ids": [str(ASSET_ONE)]}),
    ]

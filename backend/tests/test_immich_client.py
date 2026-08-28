"""Contract tests for the centralized Immich API boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
        assert body["withExif"] is False
        assert body["withPeople"] is False
        assert body["withStacked"] is True
        assert body["withDeleted"] is False
        assert body["withArchived"] is True
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
async def test_trashed_assets_use_epoch_filter_and_drop_active_leaks() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        payloads.append(body)
        page = int(body["page"])
        active = asset_payload(ASSET_ONE, "active.jpg")
        trashed = asset_payload(ASSET_TWO, "trashed.jpg")
        trashed["isTrashed"] = True
        return httpx.Response(
            200,
            json={
                "assets": {
                    "count": 2 if page == 1 else 1,
                    "total": 2 if page == 1 else 1,
                    "items": [active, trashed] if page == 1 else [trashed],
                    "nextPage": "2" if page == 1 else None,
                }
            },
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    assets = [asset async for asset in client.iter_trashed_assets(page_size=48)]

    assert [asset.id for asset in assets] == [ASSET_TWO, ASSET_TWO]
    assert payloads == [
        {
            "page": 1,
            "size": 48,
            "order": "asc",
            "withExif": False,
            "withPeople": False,
            "withStacked": True,
            "withDeleted": True,
            "withArchived": True,
            "trashedAfter": "1970-01-01T00:00:00+00:00",
        },
        {
            "page": 2,
            "size": 48,
            "order": "asc",
            "withExif": False,
            "withPeople": False,
            "withStacked": True,
            "withDeleted": True,
            "withArchived": True,
            "trashedAfter": "1970-01-01T00:00:00+00:00",
        },
    ]


@pytest.mark.asyncio
async def test_incremental_metadata_window_is_bounded_in_request_payload() -> None:
    lower = datetime(2026, 8, 26, 11, 55, tzinfo=UTC)
    upper = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["updatedAfter"] == lower.isoformat()
        assert body["updatedBefore"] == upper.isoformat()
        return httpx.Response(
            200,
            json={
                "assets": {
                    "count": 0,
                    "total": 0,
                    "items": [],
                    "nextPage": None,
                }
            },
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    assets = [
        asset
        async for asset in client.iter_assets(
            updated_after=lower,
            updated_before=upper,
        )
    ]

    assert assets == []


@pytest.mark.asyncio
async def test_optional_sync_stream_is_typed_and_acknowledged() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/sync/capabilities":
            return httpx.Response(200, json={"stream": True, "acknowledgements": True})
        if request.url.path == "/api/sync/stream":
            return httpx.Response(
                200,
                text='{"id":"evt-1","kind":"asset_deleted","entity_id":"' + str(ASSET_ONE) + '"}\n',
            )
        assert request.url.path == "/api/sync/ack"
        assert json.loads(request.content) == {"id": "evt-1"}
        return httpx.Response(204)

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    capabilities = await client.sync_capabilities()
    events = [event async for event in client.iter_sync_events("cursor-1")]
    await client.acknowledge_sync_event(events[0].id)

    assert capabilities.stream is True
    assert events[0].kind == "asset_deleted"
    assert requests[1].url.params["cursor"] == "cursor-1"


@pytest.mark.asyncio
async def test_server_version_is_typed_and_reports_supported_api_line() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-api-key"] == "private-test-key"
        assert request.url.path == "/api/server/version"
        return httpx.Response(
            200,
            json={"major": 3, "minor": 1, "patch": 0, "prerelease": None},
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    version = await client.get_server_version()
    report = await client.compatibility_report()

    assert version.label == "3.1.0"
    assert version.is_compatible is True
    assert report.status == "compatible"
    assert report.server_version is not None
    assert report.server_version.patch == 0
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_server_version_report_marks_other_api_lines_incompatible() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"major": 4, "minor": 0, "patch": 0, "prerelease": None},
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    report = await client.compatibility_report()

    assert report.status == "incompatible"
    assert report.server_version is not None
    assert report.server_version.label == "4.0.0"
    assert report.supported_api_version == "3.1.x"


@pytest.mark.asyncio
async def test_server_version_report_is_unknown_when_endpoint_is_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not found"})

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    report = await client.compatibility_report()

    assert report.status == "unknown"
    assert report.server_version is None
    assert "does not expose" in report.detail


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
    assert (
        client.public_asset_url(ASSET_ONE) == f"https://photos.example.test/base/photos/{ASSET_ONE}"
    )


@pytest.mark.asyncio
async def test_asset_detail_tracks_tag_field_presence_and_album_membership_endpoint() -> None:
    album_id = UUID("44444444-4444-4444-8444-444444444444")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/assets/{ASSET_ONE}":
            payload = asset_payload(ASSET_ONE, "detail.jpg")
            payload["tags"] = [{"id": str(UUID("66666666-6666-4666-8666-666666666666"))}]
            return httpx.Response(200, json=payload)
        assert request.url.path == "/api/albums"
        assert request.url.params["assetId"] == str(ASSET_ONE)
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(album_id),
                    "albumName": "Review",
                    "assetCount": 1,
                    "createdAt": "2026-08-20T12:00:00Z",
                    "updatedAt": "2026-08-20T12:00:00Z",
                }
            ],
        )

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    detail = await client.get_asset(ASSET_ONE)
    albums = await client.list_albums_for_asset(ASSET_ONE)

    assert detail.includes_tags is True
    assert albums[0].id == album_id


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
async def test_stack_mutations_use_supported_stack_routes() -> None:
    stack_id = UUID("55555555-5555-4555-8555-555555555555")
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        return httpx.Response(204)

    client = ImmichApiClient(settings(), transport=httpx.MockTransport(handler))
    await client.remove_asset_from_stack(stack_id, ASSET_TWO)
    await client.update_stack_primary(stack_id, ASSET_ONE)
    await client.delete_stack(stack_id)

    assert requests == [
        ("DELETE", f"/api/stacks/{stack_id}/assets/{ASSET_TWO}"),
        ("PUT", f"/api/stacks/{stack_id}"),
        ("DELETE", f"/api/stacks/{stack_id}"),
    ]


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

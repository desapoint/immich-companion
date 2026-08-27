"""Regression tests for the bootstrap API and safety defaults."""

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from companion.config import Settings
from companion.main import create_app


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "companion_env": "test",
        "companion_version": "test-version",
        "immich_url": "http://immich.test",
        "immich_api_key": "test-key",
        "allow_destructive_actions": False,
    }
    values.update(overrides)
    return Settings(**values)


def pong_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        if request.url.path == "/api/server/version":
            return httpx.Response(
                200,
                json={"major": 3, "minor": 1, "patch": 0, "prerelease": None},
            )
        assert request.url.path == "/api/server/ping"
        return httpx.Response(200, json={"res": "pong"})

    return httpx.MockTransport(handler)


def immich_asset_payload(asset_id: str, *, trashed: bool) -> dict[str, object]:
    return {
        "id": asset_id,
        "ownerId": "33333333-3333-4333-8333-333333333333",
        "type": "IMAGE",
        "originalFileName": "restore.jpg",
        "originalPath": "upload/library/restore.jpg",
        "originalMimeType": "image/jpeg",
        "width": 2048,
        "height": 1365,
        "fileCreatedAt": "2026-08-20T12:00:00Z",
        "fileModifiedAt": "2026-08-20T12:00:00Z",
        "isFavorite": False,
        "isArchived": False,
        "isTrashed": trashed,
        "isOffline": False,
        "isEdited": False,
        "hasMetadata": True,
        "visibility": "timeline",
        "people": [],
        "tags": [],
    }


def test_health_is_ready_when_immich_ping_succeeds() -> None:
    with TestClient(create_app(settings(), pong_transport())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["ready"] is True
    assert response.json()["dependencies"]["immich"]["status"] == "ok"
    assert response.json()["dependencies"]["companion_database"]["status"] == "not_configured"


def test_readiness_fails_without_immich_configuration() -> None:
    unconfigured = settings(immich_url=None, immich_api_key=None)
    with TestClient(create_app(unconfigured)) as client:
        response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"]["immich"]["status"] == "not_configured"


def test_safety_and_capability_defaults_are_visible() -> None:
    with TestClient(create_app(settings(), pong_transport())) as client:
        capabilities = client.get("/api/capabilities").json()
        health = client.get("/api/health").json()

    assert capabilities["destructive_actions"] is False
    assert capabilities["immich_api"] is True
    assert capabilities["companion_database"] is False
    assert capabilities["immich_server"]["status"] == "compatible"
    assert capabilities["immich_server"]["server_version"]["major"] == 3
    assert health["safe_mode"] is True


def test_file_backed_immich_key_is_used_without_exposing_it(tmp_path: Path) -> None:
    key_file = tmp_path / "immich-api-key"
    key_file.write_text("file-backed-test-key\n")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "file-backed-test-key"
        return httpx.Response(200, json={"res": "pong"})

    configured = settings(immich_api_key=None, immich_api_key_file=key_file)
    with TestClient(create_app(configured, httpx.MockTransport(handler))) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert "file-backed-test-key" not in response.text


def test_disposable_seed_state_is_available_only_in_test_environment(tmp_path: Path) -> None:
    state_file = tmp_path / "bootstrap-state.json"
    state_file.write_text('{"ready": true, "expected_seed_assets": 5}')

    configured = settings(companion_test_state_file=state_file)
    with TestClient(create_app(configured, pong_transport())) as client:
        response = client.get("/api/test-state")

    assert response.status_code == 200
    assert response.json() == {"ready": True, "expected_seed_assets": 5}

    production = settings(companion_env="production", companion_test_state_file=state_file)
    with TestClient(create_app(production, pong_transport())) as client:
        missing = client.get("/api/test-state")

    assert missing.status_code == 404


def test_frontend_assets_are_served_without_shadowing_api_routes(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<h1>Compiled companion frontend</h1>")
    (tmp_path / "assets" / "app.js").write_text("console.log('companion')")

    configured = settings(companion_frontend_dir=tmp_path)
    with TestClient(create_app(configured, pong_transport())) as client:
        page = client.get("/")
        nested_page = client.get("/future/search")
        asset = client.get("/assets/app.js")
        health = client.get("/api/health")
        missing_api = client.get("/api/not-implemented")

    assert page.status_code == 200
    assert "Compiled companion frontend" in page.text
    assert nested_page.text == page.text
    assert asset.text == "console.log('companion')"
    assert health.status_code == 200
    assert missing_api.status_code == 404


def test_root_reports_missing_frontend_assets_during_backend_only_development() -> None:
    with TestClient(create_app(settings(), pong_transport())) as client:
        response = client.get("/")

    assert response.status_code == 503
    assert response.json()["detail"].startswith("Frontend assets are not installed")


def test_immich_http_failure_is_reported_without_leaking_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    with TestClient(create_app(settings(), httpx.MockTransport(handler))) as client:
        response = client.get("/api/health")

    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["immich"]["detail"] == "Immich returned HTTP 401."
    assert "test-key" not in response.text


def test_asset_detail_and_preview_are_proxied_without_exposing_credentials() -> None:
    asset_id = "11111111-1111-4111-8111-111111111111"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        if request.url.path == f"/api/assets/{asset_id}":
            return httpx.Response(
                200,
                json={
                    "id": asset_id,
                    "type": "IMAGE",
                    "originalFileName": "viewer.jpg",
                    "originalPath": "upload/viewer.jpg",
                    "fileCreatedAt": "2026-08-20T12:00:00Z",
                    "fileModifiedAt": "2026-08-20T12:00:00Z",
                    "isFavorite": False,
                    "isArchived": False,
                    "isTrashed": False,
                    "isOffline": False,
                    "isEdited": False,
                    "hasMetadata": True,
                    "visibility": "timeline",
                    "people": [],
                    "tags": [],
                },
            )
        if request.url.path == f"/api/assets/{asset_id}/thumbnail":
            return httpx.Response(
                200,
                content=b"preview-bytes",
                headers={"content-type": "image/webp"},
            )
        assert request.url.path == f"/api/assets/{asset_id}/original"
        return httpx.Response(
            200,
            content=b"original-image-bytes",
            headers={"content-type": "image/png"},
        )

    configured = settings(immich_public_url="https://photos.example.test")
    with TestClient(create_app(configured, httpx.MockTransport(handler))) as client:
        detail = client.get(f"/api/assets/{asset_id}")
        preview = client.get(f"/api/assets/{asset_id}/thumbnail?size=preview")
        original = client.get(f"/api/assets/{asset_id}/original")

    assert detail.status_code == 200
    assert detail.json()["original_file_name"] == "viewer.jpg"
    assert detail.json()["immich_url"].endswith(f"/photos/{asset_id}")
    assert preview.status_code == 200
    assert preview.content == b"preview-bytes"
    assert preview.headers["content-type"] == "image/webp"
    assert original.content == b"original-image-bytes"
    assert original.headers["content-type"] == "image/png"
    assert "test-key" not in detail.text


def test_asset_search_requires_companion_database_configuration() -> None:
    with TestClient(create_app(settings(), pong_transport())) as client:
        response = client.get("/api/assets")

    assert response.status_code == 503
    assert response.json()["detail"] == "The companion database is not configured."


def test_restore_listing_is_paged_directly_from_immich() -> None:
    active_id = "11111111-1111-4111-8111-111111111111"
    first_trashed_id = "22222222-2222-4222-8222-222222222222"
    second_trashed_id = "44444444-4444-4444-8444-444444444444"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/search/metadata"
        request_payload = json.loads(request.read())
        assert request_payload["size"] == 1000
        assert request_payload["trashedAfter"] == "1970-01-01T00:00:00+00:00"
        assert "isTrashed" not in request_payload
        page = request_payload["page"]
        items = (
            [
                immich_asset_payload(active_id, trashed=False),
                immich_asset_payload(first_trashed_id, trashed=True),
            ]
            if page == 1
            else [immich_asset_payload(second_trashed_id, trashed=True)]
        )
        return httpx.Response(
            200,
            json={
                "assets": {
                    "count": len(items),
                    "total": len(items),
                    "items": items,
                    "nextPage": "2" if page == 1 else None,
                }
            },
        )

    with TestClient(create_app(settings(), httpx.MockTransport(handler))) as client:
        response = client.get("/api/restore?page=2&page_size=1")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["pages"] == 2
    assert response.json()["items"][0]["id"] == second_trashed_id
    assert response.json()["items"][0]["is_trashed"] is True
    assert response.json()["items"][0]["restore_path"] == "upload/library/restore.jpg"


def test_restore_detail_rejects_an_asset_that_immich_reports_as_active() -> None:
    asset_id = "11111111-1111-4111-8111-111111111111"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/assets/{asset_id}"
        return httpx.Response(200, json=immich_asset_payload(asset_id, trashed=False))

    with TestClient(create_app(settings(), httpx.MockTransport(handler))) as client:
        response = client.get(f"/api/restore/{asset_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "The asset is not in Restore."

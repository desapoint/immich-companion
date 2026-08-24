"""Regression tests for the bootstrap API and safety defaults."""

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
        assert request.url.path == "/api/server/ping"
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(200, json={"res": "pong"})

    return httpx.MockTransport(handler)


def test_health_is_ready_when_immich_ping_succeeds() -> None:
    with TestClient(create_app(settings(), pong_transport())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["ready"] is True
    assert response.json()["dependencies"]["immich"]["status"] == "ok"


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
    assert health["safe_mode"] is True


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

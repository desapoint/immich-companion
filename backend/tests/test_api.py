"""Regression tests for the bootstrap API and safety defaults."""

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
        page = client.get("/")

    assert capabilities["destructive_actions"] is False
    assert capabilities["immich_api"] is True
    assert page.status_code == 200
    assert "SAFE MODE" in page.text


def test_immich_http_failure_is_reported_without_leaking_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    with TestClient(create_app(settings(), httpx.MockTransport(handler))) as client:
        response = client.get("/api/health")

    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["immich"]["detail"] == "Immich returned HTTP 401."
    assert "test-key" not in response.text

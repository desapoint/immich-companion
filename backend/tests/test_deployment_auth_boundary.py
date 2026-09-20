"""Tests for the opt-in deployment bearer boundary."""

import base64

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient, WebSocketDisconnect

from companion.config import Settings
from companion.deployment_auth_boundary import DeploymentBearerAuthMiddleware
from companion.main import create_app


async def private_endpoint(request: object) -> PlainTextResponse:
    return PlainTextResponse("private")


def build_client(token: str | None) -> TestClient:
    app = Starlette(
        routes=[Route("/private", private_endpoint), Route("/api/live", private_endpoint)]
    )
    protected = DeploymentBearerAuthMiddleware(app, token)
    return TestClient(protected)


def test_unconfigured_boundary_preserves_existing_access() -> None:
    with build_client(None) as client:
        response = client.get("/private")

    assert response.status_code == 200
    assert response.text == "private"


def test_configured_boundary_rejects_missing_or_wrong_token() -> None:
    with build_client("strong-test-token") as client:
        missing = client.get("/private")
        wrong = client.get("/private", headers={"Authorization": "Bearer wrong"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.headers["www-authenticate"] == 'Basic realm="Immich Companion"'


def test_configured_boundary_accepts_bearer_and_keeps_liveness_public() -> None:
    with build_client("strong-test-token") as client:
        authorized = client.get(
            "/private", headers={"Authorization": "Bearer strong-test-token"}
        )
        liveness = client.get("/api/live")

    assert authorized.status_code == 200
    assert liveness.status_code == 200


def test_configured_boundary_accepts_browser_basic_auth() -> None:
    credentials = base64.b64encode(b"companion:strong-test-token").decode("ascii")

    with build_client("strong-test-token") as client:
        response = client.get("/private", headers={"Authorization": f"Basic {credentials}"})

    assert response.status_code == 200


def test_configured_boundary_rejects_wrong_basic_username() -> None:
    credentials = base64.b64encode(b"wrong:strong-test-token").decode("ascii")

    with build_client("strong-test-token") as client:
        response = client.get("/private", headers={"Authorization": f"Basic {credentials}"})

    assert response.status_code == 401


def test_configured_boundary_authenticates_websocket_handshake() -> None:
    async def websocket_endpoint(websocket) -> None:
        await websocket.accept()
        await websocket.send_text("connected")

    app = Starlette(routes=[WebSocketRoute("/api/tasks/stream", websocket_endpoint)])
    protected = DeploymentBearerAuthMiddleware(app, "strong-test-token")
    credentials = base64.b64encode(b"companion:strong-test-token").decode("ascii")

    with TestClient(protected) as client, client.websocket_connect(
        "/api/tasks/stream", headers={"Authorization": f"Basic {credentials}"}
    ) as websocket:
        assert websocket.receive_text() == "connected"


def test_configured_boundary_closes_unauthenticated_websocket() -> None:
    async def websocket_endpoint(websocket) -> None:
        await websocket.accept()

    app = Starlette(routes=[WebSocketRoute("/api/tasks/stream", websocket_endpoint)])
    protected = DeploymentBearerAuthMiddleware(app, "strong-test-token")

    with (
        TestClient(protected) as client,
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect("/api/tasks/stream"),
    ):
        pass

    assert error.value.code == 1008


def test_application_factory_installs_configured_boundary() -> None:
    credentials = base64.b64encode(b"companion:strong-test-token").decode("ascii")
    app = create_app(Settings(companion_auth_token="strong-test-token"))

    with TestClient(app) as client:
        missing = client.get("/api/version")
        authorized = client.get(
            "/api/version", headers={"Authorization": f"Basic {credentials}"}
        )
        liveness = client.get("/api/live")

    assert missing.status_code == 401
    assert authorized.status_code == 200
    assert liveness.status_code == 200

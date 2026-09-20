"""Tests for the opt-in deployment bearer boundary."""

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from companion.deployment_auth_boundary import DeploymentBearerAuthMiddleware


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
    assert missing.headers["www-authenticate"] == "Bearer"


def test_configured_boundary_accepts_bearer_and_keeps_liveness_public() -> None:
    with build_client("strong-test-token") as client:
        authorized = client.get(
            "/private", headers={"Authorization": "Bearer strong-test-token"}
        )
        liveness = client.get("/api/live")

    assert authorized.status_code == 200
    assert liveness.status_code == 200

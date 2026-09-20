"""Optional bearer authentication for deployments behind a public listener.

The boundary is deliberately opt-in so local development and existing
reverse-proxy deployments keep their current behavior until the application
factory installs it with a configured token.
"""

from __future__ import annotations

import json
import secrets

from starlette.types import ASGIApp, Receive, Scope, Send


class DeploymentBearerAuthMiddleware:
    """Require ``Authorization: Bearer <token>`` when ``token`` is configured."""

    def __init__(
        self, app: ASGIApp, token: str | None, *, liveness_path: str = "/api/live"
    ) -> None:
        self.app = app
        self.token = token.strip() if token else None
        self.liveness_path = liveness_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.token or scope.get("path") == self.liveness_path:
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        supplied = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, credential = supplied.partition(" ")
        if scheme.casefold() == "bearer" and secrets.compare_digest(credential, self.token):
            await self.app(scope, receive, send)
            return

        body = json.dumps({"detail": "Authentication required."}).encode("utf-8")
        response_headers = [
            (b"content-type", b"application/json"),
            (b"www-authenticate", b"Bearer"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        await send({"type": "http.response.start", "status": 401, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})

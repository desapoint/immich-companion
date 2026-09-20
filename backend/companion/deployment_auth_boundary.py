"""Optional bearer authentication for deployments behind a public listener.

The boundary is deliberately opt-in so local development and existing
reverse-proxy deployments keep their current behavior until the application
factory installs it with a configured token.
"""

from __future__ import annotations

import json
import secrets
from base64 import b64decode

from starlette.types import ASGIApp, Receive, Scope, Send


class DeploymentBearerAuthMiddleware:
    """Require browser Basic or API Bearer auth when ``token`` is configured."""

    def __init__(
        self, app: ASGIApp, token: str | None, *, liveness_path: str = "/api/live"
    ) -> None:
        self.app = app
        self.token = token.strip() if token else None
        self.liveness_path = liveness_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.token or scope.get("path") == self.liveness_path:
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        supplied = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, credential = supplied.partition(" ")
        if self._authorized(scheme, credential):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send(
                {"type": "websocket.close", "code": 1008, "reason": "Authentication required."}
            )
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body = json.dumps({"detail": "Authentication required."}).encode("utf-8")
        response_headers = [
            (b"content-type", b"application/json"),
            (b"www-authenticate", b'Basic realm="Immich Companion"'),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        await send({"type": "http.response.start", "status": 401, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})

    def _authorized(self, scheme: str, credential: str) -> bool:
        if scheme.casefold() == "bearer":
            return secrets.compare_digest(credential, self.token or "")
        if scheme.casefold() != "basic":
            return False
        try:
            decoded = b64decode(credential, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, separator, password = decoded.partition(":")
        return (
            separator == ":"
            and secrets.compare_digest(username, "companion")
            and secrets.compare_digest(password, self.token or "")
        )

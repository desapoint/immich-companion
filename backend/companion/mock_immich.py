"""Deterministic, test-only Immich ping service for the Compose environment."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class MockImmichHandler(BaseHTTPRequestHandler):
    """Serve only the harmless endpoints needed by bootstrap health checks."""

    server_version = "ImmichCompanionMock/0.1"

    def do_GET(self) -> None:  # noqa: N802 - method name is defined by BaseHTTPRequestHandler
        routes: dict[str, dict[str, Any]] = {
            "/api/server/ping": {"res": "pong"},
            "/api/server/version": {
                "major": 0,
                "minor": 0,
                "patch": 0,
                "mock": True,
            },
            "/health": {"status": "ok"},
        }
        body = routes.get(self.path)
        if body is None:
            self._json_response(404, {"message": "Not found"})
            return
        self._json_response(200, body)

    def _json_response(self, status_code: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, sort_keys=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    port = int(os.getenv("MOCK_IMMICH_PORT", "8081"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MockImmichHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()

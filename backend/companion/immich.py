"""Small API-only Immich integration boundary used by bootstrap health checks."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from companion.config import Settings


class ImmichHealthClient:
    """Check Immich without exposing credentials or relying on its database."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def check(self) -> dict[str, Any]:
        if not self._settings.immich_configured:
            return {
                "status": "not_configured",
                "configured": False,
                "detail": "Set IMMICH_URL and IMMICH_API_KEY to enable connectivity checks.",
            }

        assert self._settings.immich_url is not None
        assert self._settings.immich_api_key is not None
        started = perf_counter()

        try:
            async with httpx.AsyncClient(
                base_url=str(self._settings.immich_url).rstrip("/"),
                headers={"x-api-key": self._settings.immich_api_key.get_secret_value()},
                timeout=self._settings.immich_timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = await client.get("/api/server/ping")
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            return {
                "status": "error",
                "configured": True,
                "detail": f"Immich returned HTTP {error.response.status_code}.",
            }
        except httpx.RequestError as error:
            return {
                "status": "error",
                "configured": True,
                "detail": f"Immich request failed: {type(error).__name__}.",
            }

        elapsed_ms = round((perf_counter() - started) * 1000, 1)
        return {
            "status": "ok",
            "configured": True,
            "latency_ms": elapsed_ms,
        }

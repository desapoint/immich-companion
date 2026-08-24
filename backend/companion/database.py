"""Health boundary for the companion-owned PostgreSQL database."""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any

import psycopg

from companion.config import Settings


class PostgresHealthClient:
    """Check the companion database without exposing its connection string."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self) -> dict[str, Any]:
        database_url = self._settings.companion_database_url
        if database_url is None:
            return {
                "status": "not_configured",
                "configured": False,
                "detail": "Set COMPANION_DATABASE_URL to enable companion database checks.",
            }

        started = perf_counter()
        try:
            async with (
                await psycopg.AsyncConnection.connect(
                    database_url.get_secret_value(),
                    connect_timeout=math.ceil(self._settings.database_timeout_seconds),
                ) as connection,
                connection.cursor() as cursor,
            ):
                await cursor.execute("SELECT 1")
                row = await cursor.fetchone()
                if row != (1,):
                    raise RuntimeError(
                        "Companion database returned an unexpected health result"
                    )
        except (OSError, psycopg.Error, RuntimeError) as error:
            return {
                "status": "error",
                "configured": True,
                "detail": f"Companion database check failed: {type(error).__name__}.",
            }

        elapsed_ms = round((perf_counter() - started) * 1000, 1)
        return {
            "status": "ok",
            "configured": True,
            "latency_ms": elapsed_ms,
        }

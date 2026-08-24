"""Health boundary for the companion-owned PostgreSQL database."""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any

import psycopg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

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


class DatabaseManager:
    """Own the SQLAlchemy engine and short-lived async sessions."""

    def __init__(self, settings: Settings) -> None:
        database_url = settings.sqlalchemy_database_url
        if database_url is None:
            raise RuntimeError("The companion database is not configured")
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": math.ceil(settings.database_timeout_seconds)},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        """Close pooled database connections during application shutdown."""

        await self.engine.dispose()

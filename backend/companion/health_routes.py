"""Health, readiness, version, and capability route registration."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, status

from companion.config import Settings
from companion.database import PostgresHealthClient
from companion.immich import ImmichApiClient


def register_health_routes(
    app: FastAPI,
    settings: Settings,
    immich: ImmichApiClient,
    database_health: PostgresHealthClient,
) -> None:
    """Register process and dependency health endpoints."""

    async def health_payload() -> dict[str, object]:
        immich_status, database_status = await asyncio.gather(
            immich.check(),
            database_health.check(),
        )
        database_ready = database_status["status"] in {"ok", "not_configured"}
        ready = immich_status["status"] == "ok" and database_ready
        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "environment": settings.companion_env,
            "safe_mode": not settings.allow_destructive_actions,
            "dependencies": {
                "immich": immich_status,
                "companion_database": database_status,
            },
        }

    @app.get("/api/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return await health_payload()

    @app.get("/api/ready")
    async def ready() -> dict[str, object]:
        payload = await health_payload()
        if not payload["ready"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=payload,
            )
        return payload

    @app.get("/api/version")
    async def version() -> dict[str, str]:
        return {
            "name": "immich-companion",
            "version": settings.companion_version,
            "environment": settings.companion_env,
        }

    @app.get("/api/capabilities")
    async def capabilities() -> dict[str, object]:
        immich_compatibility = await immich.compatibility_report()
        return {
            "destructive_actions": settings.allow_destructive_actions,
            "immich_api": settings.immich_configured,
            "companion_database": settings.companion_database_url is not None,
            "immich_server": immich_compatibility.model_dump(mode="json"),
            "implemented": [
                "health",
                "version",
                "capabilities",
                "asset_sync",
                "asset_search",
                "asset_details",
                "asset_previews",
                "structured_asset_search",
                "album_filters",
                "tag_filters",
                "selection_resolution",
                "reviewed_asset_actions",
                "hybrid_staged_sync",
                "persistent_sync_status",
                "file_integrity_analysis",
                "cross_source_duplicate_analysis",
            ],
            "planned": [
                "action_jobs",
                "exact_dedupe",
                "tagging",
                "visual_similarity",
            ],
        }

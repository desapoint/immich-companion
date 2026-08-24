"""FastAPI entrypoint for Immich Companion."""

from __future__ import annotations

import asyncio
import json

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from companion.config import Settings, get_settings
from companion.database import PostgresHealthClient
from companion.immich import ImmichHealthClient


def create_app(
    settings: Settings | None = None,
    immich_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Create an application with injectable settings/transport for tests."""

    runtime_settings = settings or get_settings()
    immich = ImmichHealthClient(runtime_settings, transport=immich_transport)
    database = PostgresHealthClient(runtime_settings)
    app = FastAPI(
        title="Immich Companion",
        version=runtime_settings.companion_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    async def health_payload() -> dict[str, object]:
        immich_status, database_status = await asyncio.gather(
            immich.check(),
            database.check(),
        )
        database_ready = database_status["status"] in {"ok", "not_configured"}
        ready = immich_status["status"] == "ok" and database_ready
        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "environment": runtime_settings.companion_env,
            "safe_mode": not runtime_settings.allow_destructive_actions,
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
            "version": runtime_settings.companion_version,
            "environment": runtime_settings.companion_env,
        }

    @app.get("/api/capabilities")
    async def capabilities() -> dict[str, object]:
        return {
            "destructive_actions": runtime_settings.allow_destructive_actions,
            "immich_api": runtime_settings.immich_configured,
            "companion_database": runtime_settings.companion_database_url is not None,
            "implemented": ["health", "version", "capabilities"],
            "planned": [
                "sync",
                "search",
                "actions",
                "integrity",
                "exact_dedupe",
                "tagging",
                "visual_similarity",
            ],
        }

    if runtime_settings.companion_env == "test":

        @app.get("/api/test-state")
        async def test_state() -> dict[str, object]:
            state_file = runtime_settings.companion_test_state_file
            if state_file is None or not state_file.is_file():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The disposable environment has not completed its seed bootstrap.",
                )
            try:
                payload = json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The disposable environment seed state is unreadable.",
                ) from error
            if not isinstance(payload, dict):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The disposable environment seed state is invalid.",
                )
            return payload

    frontend_dir = runtime_settings.companion_frontend_dir
    frontend_index = frontend_dir / "index.html" if frontend_dir else None

    if frontend_index and frontend_index.is_file():
        frontend_assets = frontend_dir / "assets"
        if frontend_assets.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=frontend_assets),
                name="frontend-assets",
            )

        @app.get("/", response_class=FileResponse, include_in_schema=False)
        async def frontend_index_route() -> FileResponse:
            return FileResponse(frontend_index)

        @app.get("/{frontend_path:path}", response_class=FileResponse, include_in_schema=False)
        async def frontend_fallback(frontend_path: str) -> FileResponse:
            if frontend_path == "api" or frontend_path.startswith("api/"):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return FileResponse(frontend_index)
    else:

        @app.get("/", include_in_schema=False)
        async def frontend_unavailable() -> None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Frontend assets are not installed. Run the Vite development server.",
            )

    return app


app = create_app()

"""FastAPI entrypoint for the minimal Immich Companion service."""

from __future__ import annotations

from html import escape

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse

from companion.config import Settings, get_settings
from companion.immich import ImmichHealthClient


def create_app(
    settings: Settings | None = None,
    immich_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Create an application with injectable settings/transport for tests."""

    runtime_settings = settings or get_settings()
    immich = ImmichHealthClient(runtime_settings, transport=immich_transport)
    app = FastAPI(
        title="Immich Companion",
        version=runtime_settings.companion_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    async def health_payload() -> dict[str, object]:
        immich_status = await immich.check()
        ready = immich_status["status"] == "ok"
        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "environment": runtime_settings.companion_env,
            "safe_mode": not runtime_settings.allow_destructive_actions,
            "dependencies": {"immich": immich_status},
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> str:
        environment = escape(runtime_settings.companion_env)
        safety = (
            "SAFE MODE"
            if not runtime_settings.allow_destructive_actions
            else "ACTIONS ENABLED"
        )
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Immich Companion</title>
    <style>
      body {{ font: 16px system-ui, sans-serif; max-width: 48rem; margin: 4rem auto;
             padding: 0 1rem; color: #e5e7eb; background: #111827; }}
      .card {{ padding: 1.5rem; border: 1px solid #374151; border-radius: .75rem;
               background: #1f2937; }}
      .safe {{ color: #86efac; font-weight: 700; }}
      a {{ color: #93c5fd; }}
      code {{ color: #fde68a; }}
    </style>
  </head>
  <body>
    <main class="card">
      <h1>Immich Companion</h1>
      <p>Minimal API bootstrap is running in <code>{environment}</code>.</p>
      <p class="safe">{safety}</p>
      <p><a href="/api/health">Health</a> · <a href="/api/capabilities">Capabilities</a>
         · <a href="/api/docs">API docs</a></p>
    </main>
  </body>
</html>"""

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

    return app


app = create_app()

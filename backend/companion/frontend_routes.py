"""Registration of the optional built-frontend fallback routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def register_frontend_routes(app: FastAPI, frontend_dir: Path | None) -> None:
    """Mount static assets and register the SPA fallback when available."""

    frontend_index = frontend_dir / "index.html" if frontend_dir else None
    if frontend_index and frontend_index.is_file():
        frontend_assets = frontend_dir / "static" / "assets"
        if frontend_assets.is_dir():
            app.mount(
                "/static/assets",
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

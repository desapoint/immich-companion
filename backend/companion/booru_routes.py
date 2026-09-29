"""Booru tagging, model settings, opt-outs, and undo endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from companion.action_schema import AssetSelectionRequest
from companion.booru_service import MODELS, BooruService, BooruSettingsView


class TagPolicyRequest(BaseModel):
    disabled: bool


def register_booru_routes(app: FastAPI, service: BooruService | None, assets, coordinator) -> None:
    def require() -> BooruService:
        if service is None or assets is None or coordinator is None:
            raise HTTPException(503, "Booru tagging needs Immich and the companion database")
        return service

    @app.get("/api/booru/settings")
    async def booru_settings():
        return {**(await require().settings()).model_dump(), "models": MODELS}

    @app.put("/api/booru/settings", response_model=BooruSettingsView)
    async def save_booru_settings(value: BooruSettingsView):
        try:
            return await require().save_settings(value)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/booru/disabled-tags")
    async def disabled_booru_tags():
        return [str(value) for value in await require().disabled_tag_ids()]

    @app.put("/api/booru/disabled-tags/{tag_id}")
    async def set_booru_tag_disabled(tag_id: UUID, request: TagPolicyRequest):
        try:
            await require().set_tag_disabled(tag_id, request.disabled)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error
        return {"id": tag_id, "disabled": request.disabled}

    @app.post("/api/booru/tag")
    async def tag_selection(selection: AssetSelectionRequest):
        require()
        try:
            resolution = await assets.resolve_selection(selection, max_targets=5000)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if not resolution.ids:
            raise HTTPException(422, "Select at least one image")
        task = await coordinator.submit(
            "booru_tagging",
            {
                "asset_ids": [str(value) for value in resolution.ids],
                "manual_retag": True,
            },
        )
        return {"task_id": task.id, "selected_count": len(resolution.ids)}

    @app.post("/api/booru/reset")
    async def reset_booru_selection(selection: AssetSelectionRequest):
        require()
        try:
            resolution = await assets.resolve_selection(selection, max_targets=5000)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if not resolution.ids:
            raise HTTPException(422, "Select at least one image")
        task = await coordinator.submit(
            "booru_tagging",
            {
                "mode": "reset",
                "asset_ids": [str(value) for value in resolution.ids],
            },
        )
        return {"task_id": task.id, "selected_count": len(resolution.ids)}

    @app.get("/api/booru/runs")
    async def booru_runs():
        return await require().recent_runs()

    @app.get("/api/booru/runs/{run_id}/failures")
    async def booru_run_failures(run_id: UUID):
        return await require().failures(run_id)

    @app.post("/api/booru/runs/{run_id}/retry")
    async def retry_booru_run(run_id: UUID):
        require()
        task = await coordinator.get_status(run_id)
        if task is not None and task.status not in {"completed", "failed", "cancelled"}:
            raise HTTPException(409, "Wait for this tagging run to finish before retrying")
        failures = await service.failures(run_id)
        if not failures:
            raise HTTPException(404, "No failed images remain in this run")
        submitted = await coordinator.submit(
            "booru_tagging", {"asset_ids": [item["asset_id"] for item in failures]},
        )
        return {"task_id": submitted.id, "selected_count": len(failures)}

    @app.get("/api/booru/models/status")
    async def booru_model_status():
        require()
        return [service.engine.status(repo) for repo in MODELS]

    @app.post("/api/booru/models/download")
    async def download_booru_model():
        current = await require().settings()
        task = await coordinator.submit(
            "booru_tagging",
            {"mode": "download", "model_repo": current.model_repo},
            lane_key="booru_model_download",
            max_concurrency=1,
        )
        return {"task_id": task.id}

    @app.post("/api/booru/runs/{run_id}/undo")
    async def undo_booru_run(run_id: UUID):
        require()
        task = await coordinator.get_status(run_id)
        if task is not None and task.status not in {"completed", "failed", "cancelled"}:
            raise HTTPException(409, "Wait for this tagging run to finish before undoing it")
        try:
            return await require().undo(run_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

"""Tests for bounded synchronized asset-summary lookup."""

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.asset_routes import register_asset_routes

ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")


class SummaryRepository:
    def __init__(self) -> None:
        self.requested: list[UUID] = []

    async def get_asset_summaries(self, asset_ids: list[UUID]) -> list[object]:
        self.requested = asset_ids
        return []


def app_with(repository: SummaryRepository) -> FastAPI:
    app = FastAPI()
    register_asset_routes(
        app,
        require_asset_repository=lambda: repository,
        require_integrity_service=lambda: None,
        require_immich=lambda: None,
        map_immich_error=lambda error: error,
        add_public_asset_urls=lambda response: response,
        add_public_asset_url=lambda summary: summary,
        composite_duplicate_repository=None,
    )
    return app


def test_asset_summaries_are_loaded_in_one_bounded_repository_call() -> None:
    repository = SummaryRepository()

    with TestClient(app_with(repository)) as client:
        response = client.post("/api/assets/summaries", json={"ids": [str(ASSET_ID)]})

    assert response.status_code == 200
    assert response.json() == []
    assert repository.requested == [ASSET_ID]


def test_asset_summary_batch_rejects_unbounded_requests() -> None:
    repository = SummaryRepository()

    with TestClient(app_with(repository)) as client:
        response = client.post(
            "/api/assets/summaries",
            json={"ids": [str(ASSET_ID)] * 2001},
        )

    assert response.status_code == 422
    assert repository.requested == []

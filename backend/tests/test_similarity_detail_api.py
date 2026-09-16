"""HTTP contract for cached localized similarity diagnostics."""

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.similarity_detail import DetailDiagnostics
from companion.similarity_detail_api import register_similarity_detail_routes
from companion.similarity_detail_service import StoredDetailDiagnostics

SELECTED = UUID("11111111-1111-4111-8111-111111111111")
REFERENCE = UUID("22222222-2222-4222-8222-222222222222")


def _path() -> str:
    return (
        "/api/v2/duplicates/similarity-local-changes"
        f"?selected_asset_id={SELECTED}&reference_asset_id={REFERENCE}"
    )


def test_local_change_route_is_unavailable_without_database() -> None:
    app = FastAPI()
    register_similarity_detail_routes(app, None)

    with TestClient(app) as client:
        response = client.get(_path())

    assert response.status_code == 503
    assert response.json()["detail"] == "The companion database is not configured."


def test_local_change_route_returns_unavailable_when_cached_pair_is_missing() -> None:
    class Repository:
        async def diagnostics(self, selected_asset_id, reference_asset_id):
            assert selected_asset_id == SELECTED
            assert reference_asset_id == REFERENCE
            return None

    app = FastAPI()
    register_similarity_detail_routes(app, Repository())  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.get(_path())

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "selected_asset_id": str(SELECTED),
        "reference_asset_id": str(REFERENCE),
        "changed_percent": None,
        "localized_changed_percent": None,
        "coherent_changed_percent": None,
        "largest_changed_region_percent": None,
        "substantial_region_count": None,
        "rows": 0,
        "columns": 0,
        "cells": [],
        "source": None,
    }


def test_local_change_route_serializes_cached_grid_and_source() -> None:
    result = StoredDetailDiagnostics(
        diagnostics=DetailDiagnostics(
            changed_percent=17.25,
            localized_changed_percent=82.5,
            coherent_changed_percent=13.5,
            largest_changed_region_percent=9.75,
            substantial_region_count=3,
            rows=2,
            columns=2,
            tile_changed_percents=((0.0, 25.0), (75.0, 100.0)),
        ),
        source="transcoded",
    )

    class Repository:
        async def diagnostics(self, selected_asset_id, reference_asset_id):
            assert selected_asset_id == SELECTED
            assert reference_asset_id == REFERENCE
            return result

    app = FastAPI()
    register_similarity_detail_routes(app, Repository())  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.get(_path())

    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "selected_asset_id": str(SELECTED),
        "reference_asset_id": str(REFERENCE),
        "changed_percent": 17.25,
        "localized_changed_percent": 82.5,
        "coherent_changed_percent": 13.5,
        "largest_changed_region_percent": 9.75,
        "substantial_region_count": 3,
        "rows": 2,
        "columns": 2,
        "cells": [[0.0, 25.0], [75.0, 100.0]],
        "source": "transcoded",
    }

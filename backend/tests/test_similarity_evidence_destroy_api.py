"""HTTP contract for destroy-only similarity evidence invalidation."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.similarity_detail_api import register_similarity_detail_routes


def test_destroy_route_invalidates_without_replacement_task() -> None:
    class EpochRepository:
        async def destroy(self):
            state = SimpleNamespace(
                epoch=6,
                code_generation=2,
                recorded_descriptor_fingerprint="b" * 64,
                current_descriptor_fingerprint="b" * 64,
                descriptor_current=True,
                rebuilt_at=None,
            )
            return SimpleNamespace(
                state=state,
                cancelled_task_count=2,
                removed_counts={"search_features": 123, "scans": 4},
            )

    class Repository:
        _evidence_epoch = EpochRepository()

    app = FastAPI()
    register_similarity_detail_routes(app, Repository())  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post("/api/v2/duplicates/similarity-evidence/destroy")

    assert response.status_code == 200
    assert response.json() == {
        "generation": {
            "epoch": 6,
            "code_generation": 2,
            "recorded_descriptor_fingerprint": "b" * 64,
            "current_descriptor_fingerprint": "b" * 64,
            "descriptor_current": True,
            "rebuilt_at": None,
        },
        "cancelled_task_count": 2,
        "removed_counts": {"search_features": 123, "scans": 4},
    }

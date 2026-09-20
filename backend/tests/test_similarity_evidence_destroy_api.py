"""HTTP contract for destroy-only similarity evidence invalidation."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.similarity_detail_api import register_similarity_detail_routes
from companion.similarity_generation import SIMILARITY_EVIDENCE_CODE_GENERATION


def test_destroy_route_invalidates_without_replacement_task() -> None:
    class EpochRepository:
        async def destroy(self):
            state = SimpleNamespace(
                epoch=6,
                code_generation=SIMILARITY_EVIDENCE_CODE_GENERATION,
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

        async def generation_status(self):
            return SimpleNamespace(epoch=4)

    app = FastAPI()
    register_similarity_detail_routes(app, Repository())  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post("/api/v2/duplicates/similarity-evidence/destroy")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": None,
        "generation": {
            "epoch": 6,
            "code_generation": SIMILARITY_EVIDENCE_CODE_GENERATION,
            "recorded_descriptor_fingerprint": "b" * 64,
            "current_descriptor_fingerprint": "b" * 64,
            "descriptor_current": True,
            "rebuilt_at": None,
        },
        "cancelled_task_count": 2,
        "removed_counts": {"search_features": 123, "scans": 4},
    }


def test_destroy_route_submits_deduplicated_progress_task() -> None:
    class EpochRepository:
        async def destroy(self):
            raise AssertionError("the async task path must not destroy inline")

    class Repository:
        _evidence_epoch = EpochRepository()

        async def generation_status(self):
            return SimpleNamespace(epoch=4)

    class Coordinator:
        async def submit(self, task_type, payload, **kwargs):
            assert task_type == "similarity_evidence_destroy"
            assert payload == {"expected_epoch": 4}
            assert kwargs["deduplication_key"] == "similarity-evidence-destroy"
            return SimpleNamespace(id="11111111-1111-4111-8111-111111111111")

    app = FastAPI()
    register_similarity_detail_routes(app, Repository(), Coordinator())  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post("/api/v2/duplicates/similarity-evidence/destroy")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "11111111-1111-4111-8111-111111111111",
        "cancelled_task_count": 0,
        "removed_counts": {},
        "generation": None,
    }

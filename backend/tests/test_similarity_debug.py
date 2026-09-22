"""Read-only arbitrary similarity debugging contracts."""

from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.similarity_debug_api import register_similarity_debug_routes
from companion.similarity_debug_schema import SimilarityDebugRequest
from companion.similarity_debug_service import SimilarityDebugService
from companion.similarity_detail import DetailDiagnostics
from companion.similarity_detail_service import StoredDetailDiagnostics
from companion.similarity_repository import PairSimilarityEvidence

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")


def _feature(asset_id: UUID, perceptual_hash: str, *, width: int = 100, height: int = 100):
    return SimpleNamespace(
        asset_id=asset_id,
        model_version="appearance-normalized-v1",
        feature_version=6,
        config_fingerprint="f" * 64,
        source_identity=f"source-{asset_id}",
        fingerprint_origin="original",
        width=width,
        height=height,
        perceptual_hash=perceptual_hash,
    )


def _evidence(similarity: float) -> PairSimilarityEvidence:
    return PairSimilarityEvidence(
        similarity_percent=similarity,
        structural_percent=97.0,
        perceptual_percent=96.0,
        color_percent=95.0,
        exact_thumbnail_match=False,
        exact_pixel_match=False,
        model_version="appearance-normalized-v1",
        feature_version=6,
        comparison_version=8,
        normalized_luminance_mae=0.02,
        normalized_luminance_rmse=0.03,
        normalized_luminance_ssim=0.98,
        aspect_ratio_difference=0.0,
        dimensions_equal=True,
        detail_changed_percent=2.5,
        detail_source="original",
    )


class Features:
    def __init__(self, current):
        self.current = current

    async def get_current_many(self, asset_ids):
        return {asset_id: self.current[asset_id] for asset_id in asset_ids if asset_id in self.current}

    async def get_many(self, asset_ids):
        return {asset_id: self.current[asset_id] for asset_id in asset_ids if asset_id in self.current}

    async def unavailable_reason(self, asset_id):
        return None


class Similarity:
    def __init__(self, values):
        self.values = values
        self.requested = []

    async def reference_edges(self, groups, features):
        self.requested = [tuple(group) for group in groups]
        return {
            tuple(group): self.values[tuple(group)]
            for group in groups
            if tuple(group) in self.values
        }


class Details:
    async def diagnostics(self, selected_asset_id, reference_asset_id):
        return StoredDetailDiagnostics(
            diagnostics=DetailDiagnostics(
                changed_percent=4.0,
                localized_changed_percent=30.0,
                coherent_changed_percent=3.0,
                largest_changed_region_percent=2.0,
                substantial_region_count=1,
                aligned_changed_percent=2.5,
                raw_similarity_percent=94.0,
                aligned_similarity_percent=97.5,
                alignment_applied=True,
                alignment_shift_percent=1.0,
                alignment_overlap_percent=98.0,
                rows=1,
                columns=1,
                tile_changed_percents=((4.0,),),
            ),
            source="original",
        )


async def test_debug_scores_pair_even_when_candidate_gate_would_reject_it() -> None:
    features = Features({
        A: _feature(A, "0000000000000000"),
        B: _feature(B, "ffffffffffffffff"),
    })
    similarity = Similarity({(A, B): _evidence(99.0)})
    service = SimilarityDebugService(features, similarity, Details())  # type: ignore[arg-type]

    result = await service.compare(
        SimilarityDebugRequest(
            asset_ids=[A, B],
            similarity_threshold=95,
            maximum_perceptual_distance=12,
        )
    )

    assert similarity.requested == [(A, B)]
    pair = result.pairs[0]
    assert pair.evidence_available is True
    assert pair.similarity_percent == 99.0
    assert pair.perceptual_distance == 64
    assert pair.perceptual_gate_pass is False
    assert pair.similarity_threshold_pass is True
    assert pair.would_pass_pair_pipeline is False
    assert pair.exclusion_reason == "perceptual_distance"
    assert pair.local_diagnostics is not None
    assert pair.local_diagnostics.aligned_similarity_percent == 97.5
    assert result.groups == []


async def test_debug_simulates_grouping_from_pairs_that_pass_pair_local_gates() -> None:
    features = Features({
        A: _feature(A, "0000000000000000"),
        B: _feature(B, "0000000000000001"),
        C: _feature(C, "0000000000000003"),
    })
    similarity = Similarity({
        (A, B): _evidence(98.0),
        (A, C): _evidence(90.0),
        (B, C): _evidence(97.0),
    })
    service = SimilarityDebugService(features, similarity)  # type: ignore[arg-type]

    result = await service.compare(
        SimilarityDebugRequest(
            asset_ids=[A, B, C],
            similarity_threshold=95,
            validation_mode="linked",
            anchor_asset_id=A,
            max_link_depth=2,
        )
    )

    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.anchor_asset_id == A
    assert set(group.asset_ids) == {A, B, C}
    c_admission = next(item for item in group.admission_evidence if item.asset_id == C)
    assert c_admission.admitted_by_asset_id == B
    assert c_admission.admission_similarity_percent == 97.0
    assert c_admission.link_depth == 1
    assert result.neighbor_allocation_simulated is False


async def test_debug_returns_missing_evidence_without_attempting_pair_score() -> None:
    features = Features({A: _feature(A, "0000000000000000")})
    similarity = Similarity({})
    service = SimilarityDebugService(features, similarity)  # type: ignore[arg-type]

    result = await service.compare(SimilarityDebugRequest(asset_ids=[A, B]))

    assert similarity.requested == []
    missing = next(asset for asset in result.assets if asset.asset_id == B)
    assert missing.evidence_state == "missing_or_stale"
    assert result.pairs[0].exclusion_reason == "asset_evidence_unavailable"


def test_debug_route_is_unavailable_without_database() -> None:
    app = FastAPI()
    register_similarity_debug_routes(app, None, None, None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/similarity-debug/compare",
            json={"asset_ids": [str(A), str(B)]},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "The companion database is not configured."

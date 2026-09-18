"""Regression coverage for the unified Appearance/preservation evidence paths."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.discovery import DiscoveredGroup
from companion.duplicate_service import CrossSourceDuplicateService
from companion.group_decision import DiscoverySource
from companion.similarity_repository import (
    DetailSourceEvidence,
    PairSimilarityEvidence,
)
from companion.similarity_scan_repository import SimilarityScanRepository

LEFT = UUID(int=1)
RIGHT = UUID(int=2)
SCAN_ID = UUID(int=10)


def pair(score: float, *, detail_source: str | None = "transcoded") -> PairSimilarityEvidence:
    return PairSimilarityEvidence(
        similarity_percent=score,
        structural_percent=98.0,
        perceptual_percent=97.0,
        color_percent=96.0,
        exact_thumbnail_match=False,
        exact_pixel_match=False,
        model_version="appearance-preview-v1",
        feature_version=3,
        comparison_version=6,
        detail_changed_percent=2.0 if detail_source is not None else None,
        detail_source=detail_source,
    )


class _ScanEvidence:
    def __init__(self, evidence: PairSimilarityEvidence) -> None:
        self.evidence = evidence
        self.calls: list[tuple[UUID, list[UUID], dict[UUID, str]]] = []

    async def pair_evidence(
        self,
        scan_id: UUID,
        asset_ids: list[UUID],
        *,
        source_identities: dict[UUID, str] | None = None,
    ) -> dict[tuple[UUID, UUID], PairSimilarityEvidence]:
        self.calls.append((scan_id, asset_ids, source_identities or {}))
        return {(LEFT, RIGHT): self.evidence}


@pytest.mark.asyncio
async def test_duplicate_review_prefers_persisted_scan_score_and_keeps_live_dimensions() -> None:
    persisted = pair(96.25)
    scan_evidence = _ScanEvidence(persisted)
    service = CrossSourceDuplicateService(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        scan_evidence=scan_evidence,  # type: ignore[arg-type]
    )
    group = DiscoveredGroup(
        group_id="companion:pair",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id="scan:pair",
        assets=(SimpleNamespace(id=LEFT), SimpleNamespace(id=RIGHT)),  # type: ignore[arg-type]
        provider_metadata={"scan_id": str(SCAN_ID)},
    )
    live_source = DetailSourceEvidence(
        "transcoded",
        validated_width=1920,
        validated_height=1080,
        reference_validated_width=3840,
        reference_validated_height=2160,
    )
    live = pair(99.75, detail_source=live_source)
    features = {
        LEFT: SimpleNamespace(source_identity="left-current"),
        RIGHT: SimpleNamespace(source_identity="right-current"),
    }

    result = await service._persisted_scan_edges(  # noqa: SLF001
        [group],
        features,  # type: ignore[arg-type]
        {(LEFT, RIGHT): live},
    )

    evidence = result[(LEFT, RIGHT)]
    assert evidence.similarity_percent == 96.25
    assert evidence.detail_source == "transcoded"
    assert evidence.detail_source.validated_width == 1920
    assert evidence.detail_source.reference_validated_width == 3840
    assert scan_evidence.calls == [
        (
            SCAN_ID,
            [LEFT, RIGHT],
            {LEFT: "left-current", RIGHT: "right-current"},
        )
    ]


class _Rows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class _Session:
    def __init__(self, scan: object, rows: list[object]) -> None:
        self.scan = scan
        self.rows = rows

    async def get(self, _model, _identifier):
        return self.scan

    async def scalars(self, _statement):
        return _Rows(self.rows)


class _Database:
    def __init__(self, scan: object, rows: list[object]) -> None:
        self.scan = scan
        self.rows = rows

    @asynccontextmanager
    async def sessions(self):
        yield _Session(self.scan, self.rows)


@pytest.mark.asyncio
async def test_scan_pair_reader_rejects_stale_source_identity() -> None:
    scan = SimpleNamespace(
        status="completed",
        model_version="appearance-preview-v1",
        feature_version=3,
        comparison_version=6,
    )
    row = SimpleNamespace(
        asset_id_low=LEFT,
        asset_id_high=RIGHT,
        asset_low_source_sha256="left-at-scan",
        asset_high_source_sha256="right-at-scan",
        similarity_percent=97.5,
        structural_percent=98.0,
        perceptual_percent=97.0,
        color_percent=96.0,
        normalized_luminance_mae=0.01,
        normalized_luminance_rmse=0.02,
        normalized_luminance_ssim=0.99,
        aspect_ratio_difference=0.0,
        dimensions_equal=True,
        exact_thumbnail_match=False,
        exact_pixel_match=False,
        detail_changed_percent=1.5,
        detail_source="original",
    )
    repository = SimilarityScanRepository(_Database(scan, [row]))  # type: ignore[arg-type]

    current = await repository.pair_evidence(
        SCAN_ID,
        [LEFT, RIGHT],
        source_identities={LEFT: "left-at-scan", RIGHT: "right-at-scan"},
    )
    stale = await repository.pair_evidence(
        SCAN_ID,
        [LEFT, RIGHT],
        source_identities={LEFT: "left-new", RIGHT: "right-at-scan"},
    )

    assert current[(LEFT, RIGHT)].similarity_percent == 97.5
    assert stale == {}

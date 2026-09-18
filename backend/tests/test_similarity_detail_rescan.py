"""Regressions for exposing and regenerating similarity detail evidence."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest

import companion.similarity_repository as similarity_repository_module
from companion.similarity_detail_service import SimilarityDetailMaintainer
from companion.similarity_generation import (
    SIMILARITY_EVIDENCE_CODE_GENERATION,
    similarity_generation_fingerprint,
)
from companion.similarity_repository import SimilarityRepository

LEFT = UUID(int=1)
RIGHT = UUID(int=2)


class _Rows:
    def all(self):
        return []


class _ExecuteResult:
    rowcount = 0

    def first(self):
        return (
            1,
            SIMILARITY_EVIDENCE_CODE_GENERATION,
            similarity_generation_fingerprint(),
        )


class _Session:
    async def scalars(self, _statement):
        return _Rows()

    async def scalar(self, _statement):
        return 0

    async def execute(self, _statement):
        return _ExecuteResult()

    @asynccontextmanager
    async def begin(self):
        yield self


class _Database:
    @asynccontextmanager
    async def sessions(self):
        yield _Session()


def _search_feature(asset_id: UUID, source_identity: str):
    return SimpleNamespace(
        asset_id=asset_id,
        model_version="appearance-preview-v1",
        feature_version=1,
        config_fingerprint="search-config",
        source_identity=source_identity,
        width=100,
        height=100,
        luminance_vector=bytes([128] * 256),
        perceptual_hash="0" * 16,
        color_histogram=bytes([5] * 48),
        thumbnail_sha256=source_identity,
    )


def _coarse_comparison():
    return SimpleNamespace(
        similarity_percent=99.0,
        structural_percent=99.0,
        perceptual_percent=99.0,
        color_percent=99.0,
        normalized_luminance_mae=0.01,
        normalized_luminance_rmse=0.02,
        normalized_luminance_ssim=0.99,
        aspect_ratio_difference=0.0,
        dimensions_equal=True,
    )


def _detail_records():
    return {
        LEFT: SimpleNamespace(
            width=384,
            height=384,
            sample=b"left-detail",
            origin="original",
        ),
        RIGHT: SimpleNamespace(
            width=384,
            height=384,
            sample=b"right-detail",
            origin="original",
        ),
    }


def _comparison_features():
    return {
        LEFT: _search_feature(LEFT, "1" * 64),
        RIGHT: _search_feature(RIGHT, "2" * 64),
    }


@pytest.mark.asyncio
async def test_current_detail_refines_search_duplicate_pair(monkeypatch) -> None:
    class Details:
        async def get_current_many(self, _asset_ids):
            return _detail_records()

    monkeypatch.setattr(
        similarity_repository_module,
        "compare_visual_features",
        lambda *_args: _coarse_comparison(),
    )
    monkeypatch.setattr(
        similarity_repository_module,
        "compare_detail_features",
        lambda *_args: SimpleNamespace(similarity_percent=96.0, changed_percent=4.0),
    )

    repository = SimilarityRepository(  # type: ignore[arg-type]
        _Database(),
        details=Details(),  # type: ignore[arg-type]
    )

    edges = await repository.reference_edges(  # type: ignore[arg-type]
        [[LEFT, RIGHT]],
        _comparison_features(),
        evidence_epoch=1,
    )
    evidence = edges[(LEFT, RIGHT)]

    assert evidence.similarity_percent == 96.0
    assert evidence.detail_changed_percent == 4.0
    assert evidence.detail_source == "original"
    assert evidence.detail_source.validated_width == 384  # type: ignore[union-attr]
    assert evidence.detail_source.reference_validated_width == 384  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_regenerated_detail_bypasses_search_only_hot_cache(monkeypatch) -> None:
    class Details:
        records = {}

        async def get_current_many(self, _asset_ids):
            return self.records

    details = Details()
    monkeypatch.setattr(
        similarity_repository_module,
        "compare_visual_features",
        lambda *_args: _coarse_comparison(),
    )
    monkeypatch.setattr(
        similarity_repository_module,
        "compare_detail_features",
        lambda *_args: SimpleNamespace(similarity_percent=95.0, changed_percent=5.0),
    )
    repository = SimilarityRepository(  # type: ignore[arg-type]
        _Database(),
        details=details,  # type: ignore[arg-type]
    )
    features = _comparison_features()

    first = await repository.reference_edges(  # type: ignore[arg-type]
        [[LEFT, RIGHT]], features, evidence_epoch=1
    )
    assert first[(LEFT, RIGHT)].similarity_percent == 99.0
    assert first[(LEFT, RIGHT)].detail_source is None

    details.records = _detail_records()
    second = await repository.reference_edges(  # type: ignore[arg-type]
        [[LEFT, RIGHT]], features, evidence_epoch=1
    )

    assert second[(LEFT, RIGHT)].similarity_percent == 95.0
    assert second[(LEFT, RIGHT)].detail_changed_percent == 5.0
    assert second[(LEFT, RIGHT)].detail_source == "original"


@pytest.mark.asyncio
async def test_full_rescan_retries_persisted_detail_unavailable() -> None:
    class Details:
        async def get_current_many(self, _asset_ids):
            return {}

        async def get_current_unavailable_many(self, _asset_ids):
            return {LEFT: "previous bounded detail failure"}

    class Context:
        def __init__(self, task_type: str) -> None:
            self.task = SimpleNamespace(task_type=task_type)

        async def ensure_active(self):
            return None

    maintainer = SimilarityDetailMaintainer(  # type: ignore[arg-type]
        SimpleNamespace(),
        Details(),
    )
    extracted: list[UUID] = []

    async def extract_one(_context, asset_id, _search, _evidence_epoch=None):
        extracted.append(asset_id)
        return True

    maintainer._extract_one = extract_one  # type: ignore[method-assign]
    search_features = {LEFT: SimpleNamespace()}

    await maintainer.ensure(  # type: ignore[arg-type]
        Context("similarity_scan"),
        [LEFT],
        search_features,
        evidence_epoch=1,
    )

    assert extracted == [LEFT]
    assert maintainer.counters["detail_unavailable_retried"] == 1
    assert maintainer.counters["deterministic_retries_suppressed"] == 0

    maintainer.reset_counters()
    extracted.clear()
    await maintainer.ensure(  # type: ignore[arg-type]
        Context("similarity_maintenance"),
        [LEFT],
        search_features,
        evidence_epoch=1,
    )

    assert extracted == []
    assert maintainer.counters["detail_unavailable_retried"] == 0
    assert maintainer.counters["deterministic_retries_suppressed"] == 1

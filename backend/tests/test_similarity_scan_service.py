"""Coordinated bounded similarity scan regressions."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.duplicate_schema import SimilarityScanRequest
from companion.similarity_repository import PairSimilarityEvidence
from companion.similarity_scan_service import (
    SimilarityScanAlreadyRunningError,
    SimilarityScanService,
    SimilarityScanTaskHandler,
)
from companion.task_coordinator import TaskCancelledError

SCAN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def feature(number: int, perceptual_hash: int):
    return SimpleNamespace(
        asset_id=UUID(int=number),
        model_version="appearance-v1",
        feature_version=2,
        width=100,
        height=100,
        perceptual_hash=f"{perceptual_hash:016x}",
        source_sha256=f"{number:064x}",
    )


def evidence(score: float) -> PairSimilarityEvidence:
    return PairSimilarityEvidence(
        similarity_percent=score,
        structural_percent=score,
        perceptual_percent=score,
        color_percent=score,
        exact_thumbnail_match=False,
        exact_pixel_match=False,
        model_version="appearance-v1",
        feature_version=2,
        comparison_version=2,
    )


class FakeFeatures:
    async def list_current_similarity_features(self):
        return [feature(1, 0), feature(2, 0), feature(3, 1)]


class FakeSimilarity:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = []

    async def reference_edges(self, groups, _features):
        self.calls.append(groups)
        if self.fail:
            raise RuntimeError("comparison unavailable")
        return {
            (group[0], group[1]): evidence(99.0 if group == [UUID(int=1), UUID(int=2)] else 94.0)
            for group in groups
        }


class FakeScans:
    def __init__(self):
        self.parameters = None
        self.completed = None
        self.failed = None
        self.cancelled = None

    async def create(self, parameters):
        self.parameters = parameters
        return SCAN_ID

    async def complete(self, scan_id, **values):
        self.completed = (scan_id, values)

    async def fail(self, scan_id, error):
        self.failed = (scan_id, error)

    async def cancel(self, scan_id):
        self.cancelled = scan_id


class FakeContext:
    def __init__(self):
        self.checkpoints = []

    async def ensure_active(self):
        return None

    async def checkpoint(self, **values):
        self.checkpoints.append(values)


@pytest.mark.asyncio
async def test_scan_scores_bounded_candidates_and_publishes_only_threshold_matches() -> None:
    similarity = FakeSimilarity()
    scans = FakeScans()
    context = FakeContext()
    handler = SimilarityScanTaskHandler(FakeFeatures(), similarity, scans)
    request = SimilarityScanRequest(similarity_threshold=95, maximum_matches=1)

    result = await handler.execute(context, request.model_dump(mode="json"))

    assert scans.failed is None
    assert scans.completed is not None
    assert scans.completed[0] == SCAN_ID
    assert scans.completed[1]["asset_count"] == 3
    assert scans.completed[1]["candidate_count"] == 3
    assert len(scans.completed[1]["pairs"]) == 1
    assert scans.completed[1]["pairs"][0].asset_id_low == UUID(int=1)
    assert scans.completed[1]["pairs"][0].asset_id_high == UUID(int=2)
    assert result.counters["pairs_scored"] == 3
    assert result.counters["matches_retained"] == 1
    percents = [checkpoint["progress"]["percent"] for checkpoint in context.checkpoints]
    assert percents == sorted(percents)
    scoring = [
        checkpoint["progress"]
        for checkpoint in context.checkpoints
        if checkpoint["progress"]["phase"] == "similarity_scoring"
    ]
    assert {item["total"] for item in scoring} == {3}


@pytest.mark.asyncio
async def test_failed_scan_is_not_completed() -> None:
    scans = FakeScans()
    handler = SimilarityScanTaskHandler(FakeFeatures(), FakeSimilarity(fail=True), scans)

    with pytest.raises(RuntimeError, match="comparison unavailable"):
        await handler.execute(FakeContext(), SimilarityScanRequest().model_dump(mode="json"))

    assert scans.completed is None
    assert scans.failed == (SCAN_ID, "comparison unavailable")


@pytest.mark.asyncio
async def test_cancelled_scan_is_not_failed_or_completed() -> None:
    scans = FakeScans()
    handler = SimilarityScanTaskHandler(FakeFeatures(), FakeSimilarity(), scans)

    class CancelledContext(FakeContext):
        async def ensure_active(self):
            raise TaskCancelledError("cancelled")

    with pytest.raises(TaskCancelledError):
        await handler.execute(CancelledContext(), SimilarityScanRequest().model_dump(mode="json"))

    assert scans.cancelled == SCAN_ID
    assert scans.failed is None
    assert scans.completed is None


@pytest.mark.asyncio
async def test_service_coalesces_same_scan_and_rejects_incompatible_active_scan() -> None:
    active = SimpleNamespace(id=SCAN_ID, deduplication_key="active")

    class Tasks:
        same = None
        incompatible = None

        async def find_active(self, *_args):
            return self.same

        async def find_active_by_type(self, *_args):
            return self.incompatible

        async def submit(self, *_args, **_kwargs):
            return active

        async def start(self):
            return None

    tasks = Tasks()
    service = SimilarityScanService(tasks, SimpleNamespace())  # type: ignore[arg-type]
    first = await service.start(SimilarityScanRequest())
    assert first.task_id == SCAN_ID

    tasks.same = active
    assert (await service.start(SimilarityScanRequest())).task_id == SCAN_ID

    tasks.same = None
    tasks.incompatible = active
    with pytest.raises(SimilarityScanAlreadyRunningError):
        await service.start(SimilarityScanRequest(similarity_threshold=90))

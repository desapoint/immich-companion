"""Coordinated bounded similarity scan regressions."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.duplicate_schema import SimilarityIndexCoverage, SimilarityScanRequest
from companion.similarity_repository import PairSimilarityEvidence
from companion.similarity_scan_service import (
    SimilarityScanAlreadyRunningError,
    SimilarityScanService,
    SimilarityScanTaskHandler,
)
from companion.task_coordinator import PermanentTaskError, TaskCancelledError, TaskPausedError

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
    def __init__(self, values=None):
        self.values = values or [feature(1, 0), feature(2, 0), feature(3, 1)]

    async def list_current_similarity_features(self):
        return self.values


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
        self.prepared = []
        self.already_completed = None

    async def prepare(self, parameters, *, scan_id=None):
        self.parameters = parameters
        resolved = scan_id or SCAN_ID
        self.prepared.append(resolved)
        return resolved

    async def complete(self, scan_id, **values):
        self.completed = (scan_id, values)

    async def completed_summary(self, _scan_id):
        return self.already_completed

    async def fail(self, scan_id, error):
        self.failed = (scan_id, error)

    async def cancel(self, scan_id):
        self.cancelled = scan_id


class FakeContext:
    def __init__(self, *, checkpoint=None, status="running"):
        self.checkpoints = []
        self.task = SimpleNamespace(id=SCAN_ID, checkpoint=checkpoint or {}, status=status)

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
    request = SimilarityScanRequest(
        similarity_threshold=95,
        validation_mode="linked",
        anchor_asset_id=UUID(int=2),
        maximum_matches=1,
    )

    result = await handler.execute(context, request.model_dump(mode="json"))

    assert scans.failed is None
    assert scans.completed is not None
    assert scans.parameters.validation_mode == "linked"
    assert scans.parameters.anchor_asset_id == UUID(int=2)
    assert scans.completed[0] == SCAN_ID
    assert scans.completed[1]["asset_count"] == 3
    assert scans.completed[1]["candidate_count"] == 3
    assert len(scans.completed[1]["pairs"]) == 1
    assert scans.completed[1]["pairs"][0].asset_id_low == UUID(int=1)
    assert scans.completed[1]["pairs"][0].asset_id_high == UUID(int=2)
    assert result.counters["pairs_scored"] == 3
    assert result.counters["matches_retained"] == 1
    assert result.counters["candidate_pair_limit"] == 12
    assert result.counters["candidate_raw_neighbor_matches"] == 3
    assert result.counters["rss_bytes"] >= 0
    assert result.counters["elapsed_milliseconds"] >= 0
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

    assert scans.cancelled is None
    assert scans.failed is None
    assert scans.completed is None


@pytest.mark.asyncio
async def test_scan_observes_cancellation_after_candidate_indexing() -> None:
    scans = FakeScans()
    similarity = FakeSimilarity()
    handler = SimilarityScanTaskHandler(FakeFeatures(), similarity, scans)

    class CancelledAfterIndexContext(FakeContext):
        checks = 0

        async def ensure_active(self):
            self.checks += 1
            if self.checks == 3:
                raise TaskCancelledError("cancelled after candidate indexing")

    with pytest.raises(TaskCancelledError, match="after candidate indexing"):
        await handler.execute(
            CancelledAfterIndexContext(),
            SimilarityScanRequest().model_dump(mode="json"),
        )

    assert scans.cancelled == SCAN_ID
    assert similarity.calls == []


@pytest.mark.asyncio
async def test_scan_pauses_inside_candidate_index_and_resumes_from_durable_cursor() -> None:
    values = [feature(number, 0) for number in range(1, 1_502)]
    features = FakeFeatures(values)
    scans = FakeScans()
    similarity = FakeSimilarity()
    handler = SimilarityScanTaskHandler(features, similarity, scans)
    request = SimilarityScanRequest(
        maximum_perceptual_distance=0,
        maximum_neighbors_per_asset=1,
        maximum_matches=1_000,
    )

    class PausedAfterFirstBatch(FakeContext):
        checks = 0

        async def ensure_active(self):
            self.checks += 1
            if self.checks == 3:
                raise TaskPausedError("paused during candidate indexing")

    paused = PausedAfterFirstBatch()
    with pytest.raises(TaskPausedError, match="during candidate indexing"):
        await handler.execute(paused, request.model_dump(mode="json"))

    saved = paused.checkpoints[-1]["checkpoint"]
    assert saved["phase"] == "candidate_index"
    assert saved["candidate_assets_processed"] == 1_000
    assert scans.failed is None
    assert scans.cancelled is None

    recovered = FakeContext(checkpoint=saved, status="recovering")
    result = await handler.execute(recovered, request.model_dump(mode="json"))

    candidate_progress = [
        item["checkpoint"]["candidate_assets_processed"]
        for item in recovered.checkpoints
        if item["checkpoint"]["phase"] == "candidate_index"
    ]
    assert min(candidate_progress) >= 1_000
    assert scans.prepared == [SCAN_ID, SCAN_ID]
    assert scans.completed is not None
    assert result.counters["pairs_scored"] == scans.completed[1]["candidate_count"]


@pytest.mark.asyncio
async def test_recovery_reuses_scan_committed_before_task_completion() -> None:
    scans = FakeScans()
    scans.already_completed = SimpleNamespace(
        asset_count=1_500,
        candidate_count=4_000,
        match_count=20,
    )
    similarity = FakeSimilarity()
    handler = SimilarityScanTaskHandler(FakeFeatures(), similarity, scans)

    result = await handler.execute(
        FakeContext(status="recovering"),
        SimilarityScanRequest(maximum_matches=20).model_dump(mode="json"),
    )

    assert result.summary["recovered_completed_scan"] is True
    assert result.counters["pairs_scored"] == 4_000
    assert result.counters["matches_retained"] == 20
    assert similarity.calls == []


@pytest.mark.asyncio
async def test_scan_resumes_scoring_without_regressing_its_durable_cursor() -> None:
    values = [feature(number, 0) for number in range(1, 1_502)]
    scans = FakeScans()
    handler = SimilarityScanTaskHandler(FakeFeatures(values), FakeSimilarity(), scans)
    request = SimilarityScanRequest(
        maximum_perceptual_distance=0,
        maximum_neighbors_per_asset=1,
        maximum_matches=1_000,
    )

    class PausedDuringScoring(FakeContext):
        checks = 0

        async def ensure_active(self):
            self.checks += 1
            if self.checks == 5:
                raise TaskPausedError("paused during scoring")

    paused = PausedDuringScoring()
    with pytest.raises(TaskPausedError, match="during scoring"):
        await handler.execute(paused, request.model_dump(mode="json"))

    saved = paused.checkpoints[-1]["checkpoint"]
    assert saved["phase"] == "scoring"
    assert saved["pairs_scored"] == 500

    recovered = FakeContext(checkpoint=saved, status="recovering")
    result = await handler.execute(recovered, request.model_dump(mode="json"))
    scoring_progress = [
        item["checkpoint"]["pairs_scored"]
        for item in recovered.checkpoints
        if item["checkpoint"]["phase"] == "scoring"
    ]
    assert min(scoring_progress) >= 500
    assert all(
        item["checkpoint"]["phase"] != "candidate_index"
        for item in recovered.checkpoints
    )
    assert scans.completed is not None
    assert result.counters["pairs_scored"] == scans.completed[1]["candidate_count"]


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


@pytest.mark.asyncio
async def test_scan_completes_library_index_before_candidate_search() -> None:
    events: list[str] = []

    class Indexer:
        async def maintain(self, _context, *, progress_ceiling):
            assert progress_ceiling == 30
            events.append("indexed")
            return (
                SimilarityIndexCoverage(
                    eligible_count=3,
                    current_count=3,
                    missing_count=0,
                    stale_count=0,
                    complete=True,
                    model_version="appearance-v1",
                    feature_version=2,
                    config_fingerprint="test",
                ),
                3,
                0,
                set(),
            )

    class OrderedFeatures(FakeFeatures):
        async def list_current_similarity_features(self):
            events.append("searched")
            return await super().list_current_similarity_features()

    result = await SimilarityScanTaskHandler(
        OrderedFeatures(),
        FakeSimilarity(),
        FakeScans(),
        Indexer(),  # type: ignore[arg-type]
    ).execute(FakeContext(), SimilarityScanRequest().model_dump(mode="json"))

    assert events == ["indexed", "searched"]
    assert result.counters["eligible_images"] == 3
    assert result.counters["current_fingerprints"] == 3


@pytest.mark.asyncio
async def test_scan_proceeds_with_only_the_fingerprints_that_failed_after_retry() -> None:
    class IncompleteIndex:
        async def maintain(self, _context, *, progress_ceiling):
            return (
                SimilarityIndexCoverage(
                    eligible_count=3,
                    current_count=2,
                    missing_count=1,
                    stale_count=0,
                    complete=False,
                    model_version="appearance-v1",
                    feature_version=2,
                    config_fingerprint="test",
                ),
                2,
                1,
                {UUID(int=3)},
            )

    class IndexedFeatures(FakeFeatures):
        def __init__(self):
            super().__init__([feature(1, 0), feature(2, 0)])

        async def list_similarity_feature_work(self, *, after_asset_id, limit):
            return [UUID(int=3)] if after_asset_id is None else []

    scans = FakeScans()
    result = await SimilarityScanTaskHandler(
        IndexedFeatures(),
        FakeSimilarity(),
        scans,
        IncompleteIndex(),  # type: ignore[arg-type]
    ).execute(FakeContext(), SimilarityScanRequest().model_dump(mode="json"))

    assert scans.completed is not None
    assert scans.completed[1]["asset_count"] == 2
    assert result.counters["fingerprints_excluded_after_retry"] == 1
    assert result.summary["excluded_asset_ids"] == [str(UUID(int=3))]


@pytest.mark.asyncio
async def test_scan_stops_if_new_missing_work_appears_after_retry() -> None:
    class ChangedIndex:
        async def maintain(self, _context, *, progress_ceiling):
            return (
                SimilarityIndexCoverage(
                    eligible_count=3,
                    current_count=2,
                    missing_count=1,
                    stale_count=0,
                    complete=False,
                    model_version="appearance-v1",
                    feature_version=2,
                    config_fingerprint="test",
                ),
                2,
                1,
                {UUID(int=4)},
            )

    class ChangedFeatures(FakeFeatures):
        async def list_similarity_feature_work(self, *, after_asset_id, limit):
            return [UUID(int=3)] if after_asset_id is None else []

        async def list_current_similarity_features(self):
            pytest.fail("Candidate search started after coverage drift")

    with pytest.raises(PermanentTaskError, match="coverage changed"):
        await SimilarityScanTaskHandler(
            ChangedFeatures(),
            FakeSimilarity(),
            FakeScans(),
            ChangedIndex(),  # type: ignore[arg-type]
        ).execute(FakeContext(), SimilarityScanRequest().model_dump(mode="json"))

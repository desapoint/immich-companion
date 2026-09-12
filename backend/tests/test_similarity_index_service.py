"""Durable whole-library Appearance fingerprint maintenance regressions."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.similarity_features import (
    SIMILARITY_CONFIG_FINGERPRINT,
    SIMILARITY_FEATURE_VERSION,
    SIMILARITY_MODEL_VERSION,
)
from companion.similarity_index_service import (
    SimilarityIndexMaintainer,
    SimilarityIndexService,
    SimilarityIndexTaskHandler,
)
from companion.task_coordinator import PermanentTaskError

A = UUID(int=1)
B = UUID(int=2)
C = UUID(int=3)
MODIFIED = datetime(2026, 9, 11, tzinfo=UTC)


def source(asset_id: UUID):
    return SimpleNamespace(
        id=asset_id,
        original_file_name="fixture.jpg",
        asset_type="IMAGE",
        is_trashed=False,
        is_offline=False,
        file_modified_at=MODIFIED,
        file_size_bytes=asset_id.int * 100,
    )


class FakeFeatures:
    def __init__(self, work: list[UUID], *, eligible_count: int | None = None) -> None:
        self.work = list(work)
        self.current: set[UUID] = set()
        self.eligible_count = eligible_count or len(work)
        self.requested_pages: list[tuple[UUID | None, int]] = []

    async def similarity_feature_coverage(self):
        missing = len([asset_id for asset_id in self.work if asset_id not in self.current])
        baseline_current = self.eligible_count - len(self.work)
        return self.eligible_count, baseline_current + len(self.current), missing, 0

    async def list_similarity_feature_work(self, *, after_asset_id, limit):
        self.requested_pages.append((after_asset_id, limit))
        return [
            asset_id
            for asset_id in self.work
            if asset_id not in self.current
            and (after_asset_id is None or asset_id.int > after_asset_id.int)
        ][:limit]

    async def get_similarity_feature(self, asset_id: UUID):
        if asset_id not in self.current:
            return None
        item = source(asset_id)
        return SimpleNamespace(
            asset_id=asset_id,
            model_version=SIMILARITY_MODEL_VERSION,
            feature_version=SIMILARITY_FEATURE_VERSION,
            config_fingerprint=SIMILARITY_CONFIG_FINGERPRINT,
            source_file_modified_at=item.file_modified_at,
            source_file_size_bytes=item.file_size_bytes,
        )


class FakeImmich:
    async def get_asset(self, asset_id: UUID):
        return source(asset_id)


class FakeAssets:
    def __init__(self) -> None:
        self.refreshed: list[UUID] = []

    async def refresh_asset(self, item, *, track_similarity_changes=True) -> None:
        assert track_similarity_changes is False
        self.refreshed.append(item.id)


class FakeIntegrity:
    def __init__(self, features: FakeFeatures) -> None:
        self.features = features
        self.analyzed: list[UUID] = []

    async def analyze(
        self, _context, asset_id, *, publish_progress, source, track_similarity_changes
    ):
        assert publish_progress is False
        assert track_similarity_changes is False
        assert source.id == asset_id
        self.analyzed.append(asset_id)
        self.features.current.add(asset_id)


class FakeContext:
    def __init__(self, checkpoint=None) -> None:
        self.task = SimpleNamespace(checkpoint=checkpoint or {})
        self.checkpoints: list[dict[str, object]] = []

    async def ensure_active(self) -> None:
        return None

    async def checkpoint(self, **values) -> None:
        self.checkpoints.append(values)


@pytest.mark.asyncio
async def test_library_index_fingerprints_assets_independent_of_immich_duplicate_groups() -> None:
    features = FakeFeatures([A, B, C])
    assets = FakeAssets()
    integrity = FakeIntegrity(features)
    handler = SimilarityIndexTaskHandler(
        SimilarityIndexMaintainer(
            FakeImmich(),  # type: ignore[arg-type]
            assets,  # type: ignore[arg-type]
            features,  # type: ignore[arg-type]
            integrity,  # type: ignore[arg-type]
            batch_size=2,
        )
    )

    result = await handler.execute(FakeContext(), {})

    assert integrity.analyzed == [A, B, C]
    assert assets.refreshed == [A, B, C]
    assert result.counters["eligible_images"] == 3
    assert result.counters["current_fingerprints"] == 3
    assert result.counters["missing_fingerprints"] == 0
    assert result.summary["coverage"]["complete"] is True


@pytest.mark.asyncio
async def test_library_index_reuses_committed_features_after_restart() -> None:
    features = FakeFeatures([A, B, C])
    features.current.add(A)
    integrity = FakeIntegrity(features)
    maintainer = SimilarityIndexMaintainer(
        FakeImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        integrity,  # type: ignore[arg-type]
        batch_size=2,
    )

    coverage, completed, unavailable, attempted, reasons = await maintainer.maintain(FakeContext())

    assert integrity.analyzed == [B, C]
    assert completed == 2
    assert unavailable == 0
    assert attempted == set()
    assert reasons == {}
    assert coverage.complete is True


@pytest.mark.asyncio
async def test_sixty_thousand_asset_catalog_only_pages_the_120_required_features() -> None:
    required = [UUID(int=index) for index in range(1, 121)]
    features = FakeFeatures(required, eligible_count=60_000)
    integrity = FakeIntegrity(features)
    maintainer = SimilarityIndexMaintainer(
        FakeImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        integrity,  # type: ignore[arg-type]
        batch_size=25,
    )

    coverage, completed, unavailable, attempted, reasons = await maintainer.maintain(FakeContext())

    assert completed == 120
    assert unavailable == 0
    assert attempted == set()
    assert reasons == {}
    assert coverage.eligible_count == 60_000
    assert coverage.current_count == 60_000
    assert [limit for _, limit in features.requested_pages] == [25] * 6
    assert [cursor.int if cursor else None for cursor, _ in features.requested_pages] == [
        None,
        25,
        50,
        75,
        100,
        120,
    ]


@pytest.mark.asyncio
async def test_current_index_preserves_a_resumable_scan_checkpoint() -> None:
    features = FakeFeatures([A])
    features.current.add(A)
    context = FakeContext({"phase": "scoring", "pairs_scored": 42})
    maintainer = SimilarityIndexMaintainer(
        FakeImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        FakeIntegrity(features),  # type: ignore[arg-type]
    )

    coverage, completed, unavailable, attempted, reasons = await maintainer.maintain(
        context, progress_ceiling=30
    )

    assert coverage.complete is True
    assert (completed, unavailable) == (0, 0)
    assert attempted == set()
    assert reasons == {}
    assert context.checkpoints == []


@pytest.mark.asyncio
async def test_eleven_persistent_failures_are_retried_once_and_reported(caplog) -> None:
    failed_ids = [UUID(int=number) for number in range(1, 12)]
    features = FakeFeatures(failed_ids, eligible_count=60_000)

    class FailingIntegrity(FakeIntegrity):
        async def analyze(self, context, asset_id, **kwargs):
            self.analyzed.append(asset_id)
            raise PermanentTaskError("unsupported image")

    integrity = FailingIntegrity(features)
    maintainer = SimilarityIndexMaintainer(
        FakeImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        integrity,  # type: ignore[arg-type]
        batch_size=25,
    )

    coverage, completed, unavailable, attempted, reasons = await maintainer.maintain(FakeContext())

    assert coverage.eligible_count == 60_000
    assert coverage.current_count == 59_989
    assert coverage.complete is False
    assert completed == 0
    assert unavailable == 11
    assert attempted == set(failed_ids)
    assert reasons == {
        asset_id: "PermanentTaskError: unsupported image" for asset_id in failed_ids
    }
    assert integrity.analyzed == failed_ids * 2
    failure_records = [
        record for record in caplog.records if "Library fingerprint unavailable" in record.message
    ]
    assert len(failure_records) == 22
    assert "attempt=retry reason=PermanentTaskError: unsupported image" in caplog.text


@pytest.mark.asyncio
async def test_analysis_without_a_feature_logs_its_issue_and_retry_reason(caplog) -> None:
    features = FakeFeatures([A])

    class UnfingerprintableIntegrity(FakeIntegrity):
        async def analyze(self, context, asset_id, **kwargs):
            self.analyzed.append(asset_id)
            return SimpleNamespace(issues=["image_decode_unsupported"])

    handler = SimilarityIndexTaskHandler(
        SimilarityIndexMaintainer(
            FakeImmich(),  # type: ignore[arg-type]
            FakeAssets(),  # type: ignore[arg-type]
            features,  # type: ignore[arg-type]
            UnfingerprintableIntegrity(features),  # type: ignore[arg-type]
        )
    )

    result = await handler.execute(FakeContext(), {})

    reason = result.summary["unavailable_asset_reasons"][str(A)]
    assert "freshness=missing" in reason
    assert "image_decode_unsupported" in reason
    assert f"asset_id={A} attempt=retry reason={reason}" in caplog.text


@pytest.mark.asyncio
async def test_index_service_coalesces_the_current_feature_generation() -> None:
    task = SimpleNamespace(id=A)

    class Tasks:
        active = None
        submitted = 0

        async def find_active(self, *_args):
            return self.active

        async def submit(self, *_args, **_kwargs):
            self.submitted += 1
            return task

        async def start(self):
            return None

    tasks = Tasks()
    maintainer = SimpleNamespace(coverage=lambda: None)
    service = SimilarityIndexService(tasks, maintainer)  # type: ignore[arg-type]

    assert (await service.start()).task_id == A
    tasks.active = task
    assert (await service.start()).task_id == A
    assert tasks.submitted == 1

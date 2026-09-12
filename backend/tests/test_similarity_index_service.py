"""Durable whole-library Appearance fingerprint maintenance regressions."""

from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image

from companion.immich import ImmichApiError
from companion.similarity_index_service import (
    SimilarityIndexMaintainer,
    SimilarityIndexService,
    SimilarityIndexTaskHandler,
)

A = UUID(int=1)
B = UUID(int=2)
C = UUID(int=3)
MODIFIED = datetime(2026, 9, 11, tzinfo=UTC)
PREVIEW_BUFFER = BytesIO()
Image.new("RGB", (64, 48), (40, 80, 120)).save(PREVIEW_BUFFER, format="PNG")
PREVIEW = PREVIEW_BUFFER.getvalue()


def source(asset_id: UUID):
    return SimpleNamespace(
        id=asset_id,
        original_file_name="fixture.jpg",
        asset_type="IMAGE",
        is_trashed=False,
        is_offline=False,
        file_modified_at=MODIFIED,
        file_size_bytes=asset_id.int * 100,
        checksum=None,
        width=4000,
        height=3000,
        original_mime_type="image/jpeg",
    )


class FakeFeatures:
    def __init__(self, work: list[UUID], *, eligible_count: int | None = None) -> None:
        self.work = list(work)
        self.current: set[UUID] = set()
        self.eligible_count = eligible_count or len(work)
        self.requested_pages: list[tuple[UUID | None, int]] = []

    async def coverage(self):
        missing = len([asset_id for asset_id in self.work if asset_id not in self.current])
        baseline_current = self.eligible_count - len(self.work)
        return self.eligible_count, baseline_current + len(self.current), missing, 0

    async def list_work(self, *, after_asset_id, limit):
        self.requested_pages.append((after_asset_id, limit))
        return [
            asset_id
            for asset_id in self.work
            if asset_id not in self.current
            and (after_asset_id is None or asset_id.int > after_asset_id.int)
        ][:limit]

    async def save(self, asset, preview_sha256, feature):
        assert len(preview_sha256) == 64
        assert feature.pixel_sha256 is None
        self.current.add(asset.id)
        return True


class FakeImmich:
    def __init__(self) -> None:
        self.previewed: list[UUID] = []

    async def get_asset(self, asset_id: UUID):
        return source(asset_id)

    async def get_bounded_preview(self, asset_id: UUID, *, max_bytes: int):
        assert len(PREVIEW) < max_bytes
        self.previewed.append(asset_id)
        return PREVIEW


class FakeAssets:
    def __init__(self) -> None:
        self.refreshed: list[UUID] = []

    async def refresh_asset(self, item, *, track_similarity_changes=True) -> None:
        assert track_similarity_changes is False
        self.refreshed.append(item.id)


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
    immich = FakeImmich()
    handler = SimilarityIndexTaskHandler(
        SimilarityIndexMaintainer(
            immich,  # type: ignore[arg-type]
            assets,  # type: ignore[arg-type]
            features,  # type: ignore[arg-type]
            batch_size=2,
        )
    )

    result = await handler.execute(FakeContext(), {})

    assert immich.previewed == [A, B, C]
    assert assets.refreshed == [A, B, C]
    assert result.counters["eligible_images"] == 3
    assert result.counters["current_fingerprints"] == 3
    assert result.counters["missing_fingerprints"] == 0
    assert result.summary["coverage"]["complete"] is True


@pytest.mark.asyncio
async def test_library_index_reuses_committed_features_after_restart() -> None:
    features = FakeFeatures([A, B, C])
    features.current.add(A)
    immich = FakeImmich()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        batch_size=2,
    )

    coverage, completed, unavailable, attempted, reasons = await maintainer.maintain(FakeContext())

    assert immich.previewed == [B, C]
    assert completed == 2
    assert unavailable == 0
    assert attempted == set()
    assert reasons == {}
    assert coverage.complete is True


@pytest.mark.asyncio
async def test_sixty_thousand_asset_catalog_only_pages_the_120_required_features() -> None:
    required = [UUID(int=index) for index in range(1, 121)]
    features = FakeFeatures(required, eligible_count=60_000)
    maintainer = SimilarityIndexMaintainer(
        FakeImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
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

    class FailingImmich(FakeImmich):
        async def get_bounded_preview(self, asset_id, *, max_bytes):
            self.previewed.append(asset_id)
            raise ImmichApiError("generated preview unavailable")

    immich = FailingImmich()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
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
        asset_id: "ImmichApiError: Immich operation 'generated preview unavailable' failed."
        for asset_id in failed_ids
    }
    assert immich.previewed == failed_ids * 2
    failure_records = [
        record for record in caplog.records if "Library fingerprint unavailable" in record.message
    ]
    assert len(failure_records) == 22
    assert "attempt=retry reason=ImmichApiError" in caplog.text


@pytest.mark.asyncio
async def test_undecodable_preview_logs_its_retry_reason(caplog) -> None:
    features = FakeFeatures([A])

    class InvalidPreviewImmich(FakeImmich):
        async def get_bounded_preview(self, asset_id, *, max_bytes):
            self.previewed.append(asset_id)
            return b"invalid preview"

    handler = SimilarityIndexTaskHandler(
        SimilarityIndexMaintainer(
            InvalidPreviewImmich(),  # type: ignore[arg-type]
            FakeAssets(),  # type: ignore[arg-type]
            features,  # type: ignore[arg-type]
        )
    )

    result = await handler.execute(FakeContext(), {})

    reason = result.summary["unavailable_asset_reasons"][str(A)]
    assert "generated preview could not be decoded" in reason
    assert f"asset_id={A} attempt=retry reason={reason}" in caplog.text


@pytest.mark.asyncio
async def test_valid_preview_indexes_original_with_mismatched_declared_mime() -> None:
    features = FakeFeatures([A])

    class MismatchedMimeImmich(FakeImmich):
        async def get_asset(self, asset_id):
            item = source(asset_id)
            item.original_mime_type = "image/heic"
            return item

        async def stream_original(self, *args, **kwargs):
            pytest.fail("Search indexing downloaded an original with mismatched MIME")

    immich = MismatchedMimeImmich()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
    )

    coverage, completed, unavailable, _, reasons = await maintainer.maintain(FakeContext())

    assert coverage.complete is True
    assert (completed, unavailable) == (1, 0)
    assert reasons == {}
    assert immich.previewed == [A]


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

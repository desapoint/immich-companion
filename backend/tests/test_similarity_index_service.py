"""Durable whole-library Appearance fingerprint maintenance regressions."""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from threading import Lock
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image

from companion.immich import ImmichApiError
from companion.similarity_index_service import (
    SimilarityIndexMaintainer,
    SimilarityIndexService,
    SimilarityIndexTaskHandler,
    _extract_normalized_evidence,
)
from companion.task_coordinator import TaskPausedError

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

    async def has_current(self, asset_id):
        return asset_id in self.current

    async def list_work(self, *, after_asset_id, limit):
        self.requested_pages.append((after_asset_id, limit))
        return [
            asset_id
            for asset_id in self.work
            if asset_id not in self.current
            and (after_asset_id is None or asset_id.int > after_asset_id.int)
        ][:limit]

    async def save(self, asset, media_sha256, feature, *, origin="preview"):
        assert len(media_sha256) == 64
        assert feature.pixel_sha256 is None
        assert origin in {"preview", "original"}
        self.current.add(asset.id)
        return True


class FakeImmich:
    def __init__(self) -> None:
        self.previewed: list[UUID] = []
        self.metadata_requested: list[UUID] = []

    async def get_asset(self, asset_id: UUID):
        self.metadata_requested.append(asset_id)
        return source(asset_id)

    async def get_bounded_preview(self, asset_id: UUID, *, max_bytes: int):
        assert len(PREVIEW) < max_bytes
        self.previewed.append(asset_id)
        return PREVIEW

    @asynccontextmanager
    async def stream_original(self, asset_id, **_kwargs):
        raise ImmichApiError("original unavailable")
        yield  # pragma: no cover


class FakeAssets:
    def __init__(self) -> None:
        self.refreshed: list[UUID] = []
        self.looked_up: list[UUID] = []

    async def get_immich_assets(self, asset_ids):
        self.looked_up.extend(asset_ids)
        return {asset_id: source(asset_id) for asset_id in asset_ids}

    async def refresh_asset(self, item, *, track_similarity_changes=True) -> None:
        assert track_similarity_changes is False
        self.refreshed.append(item.id)


class FakeRuntimeSettings:
    def __init__(self, fingerprint_page_size: int) -> None:
        self.fingerprint_page_size = fingerprint_page_size

    async def get(self):
        return SimpleNamespace(fingerprint_page_size=self.fingerprint_page_size)


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

    assert sorted(immich.previewed) == [A, B, C]
    assert sorted(immich.metadata_requested) == [A, B, C]
    assert assets.looked_up == [A, B, C]
    assert assets.refreshed == []
    assert result.counters["eligible_images"] == 3
    assert result.counters["current_fingerprints"] == 3
    assert result.counters["missing_fingerprints"] == 0
    assert result.summary["coverage"]["complete"] is True


@pytest.mark.asyncio
async def test_ensure_asset_reuses_complete_visual_cache_without_media_fetch() -> None:
    features = FakeFeatures([A])
    features.current.add(A)
    immich = FakeImmich()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
    )

    assert await maintainer.ensure_asset(FakeContext(), A) is True

    assert immich.previewed == []
    assert immich.metadata_requested == []
    assert maintainer.metrics()["fingerprints_reused"] == 1


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
async def test_persisted_fingerprint_page_size_overrides_constructor_default() -> None:
    required = [UUID(int=index) for index in range(1, 121)]
    features = FakeFeatures(required)
    maintainer = SimilarityIndexMaintainer(
        FakeImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        batch_size=25,
        runtime_settings=FakeRuntimeSettings(60),  # type: ignore[arg-type]
    )

    coverage, completed, unavailable, _, reasons = await maintainer.maintain(FakeContext())

    assert coverage.complete is True
    assert completed == 120
    assert unavailable == 0
    assert reasons == {}
    assert [limit for _, limit in features.requested_pages] == [60, 60, 60]
    assert [cursor.int if cursor else None for cursor, _ in features.requested_pages] == [
        None,
        60,
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
    assert all("visual_normalization_unavailable" in reason for reason in reasons.values())
    assert immich.previewed == failed_ids * 2
    failure_records = [
        record for record in caplog.records if "Library fingerprint unavailable" in record.message
    ]
    assert len(failure_records) == 22
    assert "attempt=retry reason=visual_normalization_unavailable" in caplog.text


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
    assert "visual_normalization_unavailable" in reason
    assert f"asset_id={A} attempt=retry reason={reason}" in caplog.text


@pytest.mark.asyncio
async def test_safe_image_uses_original_visual_source_without_pixel_hash() -> None:
    features = FakeFeatures([A])

    class OriginalImmich(FakeImmich):
        async def get_bounded_preview(self, asset_id, *, max_bytes):
            return b"invalid preview"

        @asynccontextmanager
        async def stream_original(self, asset_id, **_kwargs):
            async def chunks():
                yield PREVIEW[:10]
                yield PREVIEW[10:]

            yield SimpleNamespace(content_length=len(PREVIEW), chunks=chunks())

    immich = OriginalImmich()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
    )
    coverage, completed, unavailable, _, _ = await maintainer.maintain(FakeContext())

    assert coverage.complete is True
    assert (completed, unavailable) == (1, 0)
    assert maintainer.metrics()["original_fingerprints_generated"] == 1
    assert maintainer.metrics()["original_bytes_downloaded"] == len(PREVIEW)
    assert "decode_milliseconds" in maintainer.metrics()
    assert "feature_extraction_milliseconds" in maintainer.metrics()
    assert maintainer.metrics()["normalized_pixel_hash_milliseconds"] == 0


@pytest.mark.asyncio
async def test_original_fallback_rejects_declared_body_over_limit() -> None:
    features = FakeFeatures([A])

    class OversizedOriginal(FakeImmich):
        async def get_bounded_preview(self, asset_id, *, max_bytes):
            return b"bad preview"

        @asynccontextmanager
        async def stream_original(self, asset_id, **_kwargs):
            async def chunks():
                pytest.fail("Oversized original body was read")
                yield b""  # pragma: no cover

            yield SimpleNamespace(content_length=len(PREVIEW) + 1, chunks=chunks())

    maintainer = SimilarityIndexMaintainer(
        OversizedOriginal(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        visual_source_max_bytes=len(PREVIEW),
    )
    coverage, _, unavailable, _, reasons = await maintainer.maintain(FakeContext())

    assert coverage.complete is False
    assert unavailable == 1
    assert "size limit" in reasons[A]
    assert maintainer.metrics()["original_bytes_downloaded"] == 0


@pytest.mark.asyncio
async def test_source_change_during_preview_rejects_feature() -> None:
    features = FakeFeatures([A])

    class ChangingImmich(FakeImmich):
        async def get_asset(self, asset_id):
            item = source(asset_id)
            item.file_size_bytes += 1
            return item

    maintainer = SimilarityIndexMaintainer(
        ChangingImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
    )
    coverage, completed, unavailable, _, reasons = await maintainer.maintain(FakeContext())

    assert coverage.complete is False
    assert (completed, unavailable) == (0, 1)
    assert features.current == set()
    assert reasons[A] == "Immich source changed while visual evidence was generated"


@pytest.mark.asyncio
async def test_pause_during_concurrent_fetch_keeps_page_uncommitted() -> None:
    features = FakeFeatures([A, B, C])
    both_started = asyncio.Event()
    release = asyncio.Event()

    class SlowImmich(FakeImmich):
        started = 0

        async def get_bounded_preview(self, asset_id, *, max_bytes):
            self.started += 1
            if self.started == 2:
                both_started.set()
            await release.wait()
            return PREVIEW

    class PausingContext(FakeContext):
        paused = False

        async def ensure_active(self):
            if self.paused:
                raise TaskPausedError()

    context = PausingContext()
    maintainer = SimilarityIndexMaintainer(
        SlowImmich(),  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        batch_size=3,
        fetch_slots=2,
    )
    task = asyncio.create_task(maintainer.maintain(context))
    await asyncio.wait_for(both_started.wait(), timeout=2)
    context.paused = True
    release.set()

    with pytest.raises(TaskPausedError):
        await task
    assert features.current == set()
    assert all(checkpoint["checkpoint"].get("cursor") is None for checkpoint in context.checkpoints)


@pytest.mark.asyncio
async def test_safe_original_decode_does_not_trust_declared_mime() -> None:
    features = FakeFeatures([A])

    class MismatchedMimeImmich(FakeImmich):
        original_calls = 0

        async def get_asset(self, asset_id):
            item = source(asset_id)
            item.original_mime_type = "image/heic"
            return item

        @asynccontextmanager
        async def stream_original(self, _asset_id, **_kwargs):
            self.original_calls += 1

            async def chunks():
                yield PREVIEW

            yield SimpleNamespace(content_length=len(PREVIEW), chunks=chunks())

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
    assert immich.original_calls == 1
    assert immich.previewed == []


@pytest.mark.asyncio
async def test_preview_fetch_and_decode_have_independent_bounded_slots(monkeypatch) -> None:
    features = FakeFeatures([UUID(int=index) for index in range(1, 9)])

    class SlowImmich(FakeImmich):
        active_fetches = 0
        peak_fetches = 0

        async def get_bounded_preview(self, asset_id, *, max_bytes):
            self.active_fetches += 1
            self.peak_fetches = max(self.peak_fetches, self.active_fetches)
            await asyncio.sleep(0.01)
            self.active_fetches -= 1
            return await super().get_bounded_preview(asset_id, max_bytes=max_bytes)

    lock = Lock()
    active_decodes = 0
    peak_decodes = 0

    def slow_decode(normalized):
        nonlocal active_decodes, peak_decodes
        with lock:
            active_decodes += 1
            peak_decodes = max(peak_decodes, active_decodes)
        time.sleep(0.01)
        evidence = _extract_normalized_evidence(normalized)
        with lock:
            active_decodes -= 1
        return evidence

    monkeypatch.setattr(
        "companion.similarity_index_service._extract_normalized_evidence",
        slow_decode,
    )
    immich = SlowImmich()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        FakeAssets(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
        batch_size=8,
        fetch_slots=2,
        decode_slots=1,
    )

    coverage, completed, unavailable, _, _ = await maintainer.maintain(FakeContext())

    assert coverage.complete is True
    assert (completed, unavailable) == (8, 0)
    assert immich.peak_fetches == 2
    assert peak_decodes == 1


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

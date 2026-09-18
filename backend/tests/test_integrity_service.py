"""Task and cache behavior for bounded integrity analysis."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.image_decode import ImageDecodeResult
from companion.immich import ImmichAsset
from companion.integrity import ANALYZER_VERSION
from companion.integrity_repository import (
    preservation_feature_freshness,
    public_report,
    report_freshness,
)
from companion.integrity_schema import AssetIntegrityReport
from companion.integrity_service import (
    IntegrityService,
    IntegrityTaskHandler,
    RetryableTaskError,
)
from companion.models import AssetImagePreservationFeatureRecord, AssetIntegrityReportRecord
from companion.preservation_features import (
    PRESERVATION_CONFIG_FINGERPRINT,
    PRESERVATION_FEATURE_VERSION,
)
from companion.similarity_features import (
    SIMILARITY_CONFIG_FINGERPRINT,
    SIMILARITY_FEATURE_VERSION,
    SIMILARITY_MODEL_VERSION,
    VisualFeatureResult,
)
from companion.task_schema import TaskStatusView

ASSET_ID = UUID("11111111-1111-4111-8111-111111111111")
TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def asset(
    *,
    checksum: str = "base64-checksum",
    modified: str = "2026-08-28T12:00:00Z",
    library_id: UUID | None = None,
    size: int = 4,
):
    return ImmichAsset.model_validate(
        {
            "id": str(ASSET_ID),
            "type": "IMAGE",
            "originalFileName": "fixture.jpg",
            "originalMimeType": "image/jpeg",
            "checksum": checksum,
            "libraryId": str(library_id) if library_id is not None else None,
            "fileCreatedAt": "2026-08-28T12:00:00Z",
            "fileModifiedAt": modified,
            "exifInfo": {"fileSizeInByte": size},
        }
    )


class FakeAssets:
    def __init__(self):
        self.refreshed = []

    async def has_asset(self, _asset_id):
        return True

    async def refresh_asset(self, current, *, track_similarity_changes=True):
        self.refreshed.append(current)


class FakeReports:
    def __init__(self, record=None):
        self.record = record
        self.saved = []

    async def get(self, _asset_id):
        return self.record

    async def save(
        self,
        current,
        result,
        visual_feature=None,
        *,
        visual_feature_origin="original",
    ):
        self.saved.append((current, result, visual_feature, visual_feature_origin))
        return AssetIntegrityReport(
            asset_id=current.id,
            analyzer_version=result.analyzer_version,
            byte_size=result.byte_size,
            sha1_hex=result.sha1_hex,
            sha256_hex=result.sha256_hex,
            detected_format=result.detected_format,
            format_matches_declared=result.format_matches_declared,
            classification=result.classification,
            structurally_valid=result.structurally_valid,
            container_valid=result.container_valid,
            decode_supported=result.decode_supported,
            decode_valid=result.decode_valid,
            decoded_width=result.decoded_width,
            decoded_height=result.decoded_height,
            dimensions_match_immich=result.dimensions_match_immich,
            jpeg_eoi_offset=result.jpeg_eoi_offset,
            trailing_byte_count=result.trailing_byte_count,
            immich_checksum_match=result.immich_checksum_match,
            issues=list(result.issues),
            analyzed_at=datetime.now(UTC),
        )


class FakeImmich:
    def __init__(self, before, after=None):
        self.assets = [before, after or before]

    async def get_asset(self, _asset_id):
        return self.assets.pop(0) if len(self.assets) > 1 else self.assets[0]

    @asynccontextmanager
    async def stream_original(self, _asset_id, *, chunk_size):
        async def chunks():
            yield b"\xff\xd8"
            yield b"\xff\xd9"

        yield SimpleNamespace(chunks=chunks(), content_length=4)


class FakeContext:
    def __init__(self):
        self.checkpoints = []

    async def checkpoint(self, **payload):
        self.checkpoints.append(payload)

    async def ensure_active(self):
        return None


class FakeTasks:
    def __init__(self, active=None):
        self.active = active
        self.submitted = []

    async def find_active(self, *_args):
        return self.active

    async def submit(self, task_type, payload, **options):
        self.submitted.append((task_type, payload, options))
        return task_status()


def task_status():
    now = datetime.now(UTC)
    return TaskStatusView(
        id=TASK_ID,
        task_type="asset_integrity",
        status="queued",
        priority=60,
        deduplication_key=f"asset:{ASSET_ID}",
        lane_key="asset_integrity",
        payload={"asset_id": str(ASSET_ID)},
        checkpoint={},
        counters={},
        progress={},
        result=None,
        error=None,
        attempt=0,
        next_attempt_at=now,
        lease_owner=None,
        lease_expires_at=None,
        created_at=now,
        started_at=None,
        heartbeat_at=None,
        completed_at=None,
    )


def report_record(current: ImmichAsset) -> AssetIntegrityReportRecord:
    return AssetIntegrityReportRecord(
        asset_id=current.id,
        analyzer_version=ANALYZER_VERSION,
        source_checksum=current.checksum,
        source_file_modified_at=current.file_modified_at,
        source_file_size_bytes=4,
        source_mime_type="image/jpeg",
        byte_size=4,
        sha1_hex="0" * 40,
        sha256_hex="1" * 64,
        detected_format="jpeg",
        format_matches_declared=True,
        classification="healthy",
        structurally_valid=True,
        container_valid=True,
        decode_supported=False,
        decode_valid=None,
        decoded_width=None,
        decoded_height=None,
        dimensions_match_immich=None,
        jpeg_eoi_offset=4,
        trailing_byte_count=0,
        immich_checksum_match=None,
        issues=[],
        analyzed_at=datetime.now(UTC),
    )


def preservation_record(current: ImmichAsset) -> AssetImagePreservationFeatureRecord:
    return AssetImagePreservationFeatureRecord(
        asset_id=current.id,
        extractor_model_version=SIMILARITY_MODEL_VERSION,
        extractor_feature_version=SIMILARITY_FEATURE_VERSION,
        extractor_config_fingerprint=SIMILARITY_CONFIG_FINGERPRINT,
        preservation_version=PRESERVATION_FEATURE_VERSION,
        preservation_config_fingerprint=PRESERVATION_CONFIG_FINGERPRINT,
        source_file_modified_at=current.file_modified_at,
        source_file_size_bytes=4,
        source_sha256="1" * 64,
        origin="original",
        width=1,
        height=1,
        luminance_vector=bytes([128] * 256),
        perceptual_hash="0" * 16,
        color_histogram=bytes([0] * 48),
        thumbnail_sha256="2" * 64,
        pixel_normalization_version=1,
        pixel_sha256="3" * 64,
        bit_depth=8,
        channel_count=3,
        has_alpha=False,
        color_space="RGB",
        orientation=None,
        icc_profile_present=False,
        has_exif=False,
        has_capture_time=False,
        has_camera_info=False,
        has_gps=False,
        has_orientation_metadata=False,
        metadata_richness=0,
        analyzed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_handler_streams_then_saves_only_after_source_verification(monkeypatch) -> None:
    current = asset()
    reports = FakeReports()
    context = FakeContext()
    handler = IntegrityTaskHandler(FakeImmich(current), FakeAssets(), reports)
    visual_feature = VisualFeatureResult(
        model_version=SIMILARITY_MODEL_VERSION,
        feature_version=SIMILARITY_FEATURE_VERSION,
        width=1,
        height=1,
        luminance_vector=bytes([128] * 256),
        perceptual_hash="0" * 16,
        color_histogram=bytes([0] * 48),
        thumbnail_sha256="2" * 64,
        pixel_normalization_version=1,
        pixel_sha256="3" * 64,
        bit_depth=8,
        channel_count=3,
        has_alpha=False,
        color_space="RGB",
        orientation=None,
        icc_profile_present=False,
        has_exif=False,
        has_capture_time=False,
        has_camera_info=False,
        has_gps=False,
        has_orientation_metadata=False,
        metadata_richness=0,
    )
    monkeypatch.setattr(
        "companion.integrity_service.decode_and_extract_features",
        lambda *_args: (
            ImageDecodeResult(supported=True, valid=True, width=1, height=1),
            visual_feature,
        ),
    )

    result = await handler.execute(context, {"asset_id": str(ASSET_ID)})

    assert result.summary["classification"] == "healthy"
    assert reports.saved[0][1].byte_size == 4
    assert reports.saved[0][2] == visual_feature
    assert reports.saved[0][3] == "original"
    assert context.checkpoints[-1]["progress"]["phase"] == "finalizing"


@pytest.mark.asyncio
async def test_handler_does_not_save_when_source_changes_during_stream() -> None:
    reports = FakeReports()
    handler = IntegrityTaskHandler(
        FakeImmich(asset(checksum="before"), asset(checksum="after")),
        FakeAssets(),
        reports,
    )

    with pytest.raises(RetryableTaskError, match="source changed"):
        await handler.execute(FakeContext(), {"asset_id": str(ASSET_ID)})

    assert reports.saved == []


@pytest.mark.asyncio
async def test_supplied_candidate_source_uses_one_final_live_check() -> None:
    reports = FakeReports()

    class CountingImmich(FakeImmich):
        lookups = 0

        async def get_asset(self, asset_id):
            self.lookups += 1
            return await super().get_asset(asset_id)

    immich = CountingImmich(asset(checksum="after"))
    handler = IntegrityTaskHandler(immich, FakeAssets(), reports)

    with pytest.raises(RetryableTaskError, match="source changed"):
        await handler.analyze(
            FakeContext(), ASSET_ID, source=asset(checksum="before"), publish_progress=False
        )

    assert immich.lookups == 1
    assert reports.saved == []


@pytest.mark.asyncio
async def test_external_integrity_does_not_compare_immich_path_checksum() -> None:
    external = asset(library_id=UUID("22222222-2222-4222-8222-222222222222"))
    reports = FakeReports()

    await IntegrityTaskHandler(FakeImmich(external), FakeAssets(), reports).execute(
        FakeContext(), {"asset_id": str(ASSET_ID)}
    )

    assert reports.saved[0][1].immich_checksum_match is None


@pytest.mark.asyncio
async def test_external_source_change_uses_size_and_mtime_not_path_checksum() -> None:
    library_id = UUID("22222222-2222-4222-8222-222222222222")
    reports = FakeReports()
    handler = IntegrityTaskHandler(
        FakeImmich(
            asset(library_id=library_id, size=4),
            asset(library_id=library_id, size=5),
        ),
        FakeAssets(),
        reports,
    )

    with pytest.raises(RetryableTaskError, match="source changed"):
        await handler.execute(FakeContext(), {"asset_id": str(ASSET_ID)})

    assert reports.saved == []


@pytest.mark.asyncio
async def test_stream_size_must_match_external_metadata_before_caching() -> None:
    library_id = UUID("22222222-2222-4222-8222-222222222222")
    reports = FakeReports()
    external = asset(library_id=library_id, size=5)

    with pytest.raises(RetryableTaskError, match="size did not match"):
        await IntegrityTaskHandler(FakeImmich(external), FakeAssets(), reports).execute(
            FakeContext(), {"asset_id": str(ASSET_ID)}
        )

    assert reports.saved == []


@pytest.mark.asyncio
async def test_service_reuses_current_report_and_force_queues_reanalysis() -> None:
    current = asset()
    record = report_record(current)
    tasks = FakeTasks()
    service = IntegrityService(FakeImmich(current), FakeAssets(), FakeReports(record), tasks)

    cached = await service.analyze(ASSET_ID, force=False)
    forced = await service.analyze(ASSET_ID, force=True)

    assert cached.state == "ready"
    assert cached.report == public_report(record)
    assert forced.state == "pending"
    assert forced.task_id == TASK_ID
    assert len(tasks.submitted) == 1


def test_upload_report_becomes_stale_when_size_or_mtime_changes() -> None:
    current = asset()
    record = report_record(current)

    assert report_freshness(record, current) == "current"
    assert report_freshness(record, asset(size=5)) == "stale"
    assert (
        report_freshness(
            record,
            asset(modified="2026-08-28T12:01:00Z"),
        )
        == "stale"
    )


def test_preservation_feature_reuses_only_compatible_source_and_versions() -> None:
    current = asset()
    record = preservation_record(current)

    assert preservation_feature_freshness(record, current) == "current"
    assert preservation_feature_freshness(record, asset(size=5)) == "stale"
    assert (
        preservation_feature_freshness(
            record,
            asset(modified="2026-08-28T12:01:00Z"),
        )
        == "stale"
    )

    # Extractor provenance is retained for diagnostics but no longer couples
    # preservation freshness to the Appearance generation.
    record.extractor_feature_version += 1
    assert preservation_feature_freshness(record, current) == "current"

    record.preservation_version += 1
    assert preservation_feature_freshness(record, current) == "stale"
    record.preservation_version = PRESERVATION_FEATURE_VERSION
    record.preservation_config_fingerprint = "legacy"
    assert preservation_feature_freshness(record, current) == "stale"


def test_legacy_other_format_report_remains_readable_while_stale() -> None:
    current = asset()
    record = report_record(current)
    record.analyzer_version = 1
    record.detected_format = "other"

    assert report_freshness(record, current) == "stale"
    assert public_report(record).detected_format == "unknown"


def test_external_report_ignores_path_checksum_changes() -> None:
    library_id = UUID("22222222-2222-4222-8222-222222222222")
    current = asset(library_id=library_id)
    record = report_record(current)

    assert report_freshness(record, current) == "current"
    assert (
        report_freshness(
            record,
            asset(library_id=library_id, checksum="new-path-checksum"),
        )
        == "current"
    )

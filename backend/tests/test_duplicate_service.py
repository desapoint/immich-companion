"""Immich-group candidate, cache, and checksum-semantics regressions."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.action_service import (
    ActionPlanConflictError,
    DestructiveActionsDisabledError,
)
from companion.discovery import DiscoveredGroup
from companion.duplicate_schema import (
    DuplicateAnalysisOptions,
    DuplicateResolutionExecuteRequest,
    DuplicateResolutionPlanRequest,
    DuplicateReviewUpdate,
    DuplicateSimilarityReferenceRequest,
)
from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
)
from companion.group_decision import DiscoverySource
from companion.immich import ImmichApiError, ImmichAsset, ImmichDuplicateGroup
from companion.integrity import ANALYZER_VERSION
from companion.models import AssetIntegrityReportRecord, AssetSimilarityFeatureRecord
from companion.similarity_features import (
    SIMILARITY_FEATURE_VERSION,
    SIMILARITY_MODEL_VERSION,
)
from companion.similarity_repository import (
    SIMILARITY_COMPARISON_VERSION,
    PairSimilarityEvidence,
    canonical_pair,
    requested_reference_pairs,
)
from companion.task_coordinator import PermanentTaskError

UPLOAD_1 = UUID("11111111-1111-4111-8111-111111111111")
UPLOAD_2 = UUID("22222222-2222-4222-8222-222222222222")
EXTERNAL_1 = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EXTERNAL_2 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
LIBRARY_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
GROUP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
PUBLIC_GROUP_ID = f"immich:{GROUP_ID}"
MODIFIED = datetime(2026, 8, 29, 12, tzinfo=UTC)


def sha1(payload: bytes) -> str:
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


def immich_sha1(payload: bytes) -> str:
    return base64.b64encode(hashlib.sha1(payload, usedforsecurity=False).digest()).decode()


def asset(
    identifier: UUID,
    *,
    external: bool,
    checksum: str | None,
    filename: str,
    size: int = 4,
    modified: datetime = MODIFIED,
    uploaded: datetime | None = None,
    offline: bool = False,
) -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(identifier),
            "ownerId": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            "libraryId": str(LIBRARY_ID) if external else None,
            "type": "IMAGE",
            "originalFileName": filename,
            "originalPath": f"library/{filename}",
            "originalMimeType": "image/jpeg",
            "checksum": checksum,
            "fileCreatedAt": MODIFIED.isoformat(),
            "fileModifiedAt": modified.isoformat(),
            "createdAt": uploaded.isoformat() if uploaded is not None else None,
            "isOffline": offline,
            "exifInfo": {"fileSizeInByte": size},
        }
    )


def group(*assets: ImmichAsset) -> ImmichDuplicateGroup:
    return ImmichDuplicateGroup(duplicate_id=GROUP_ID, assets=list(assets))


def report(
    identifier: UUID,
    content: bytes,
    *,
    size: int = 4,
    modified: datetime = MODIFIED,
) -> AssetIntegrityReportRecord:
    return AssetIntegrityReportRecord(
        asset_id=identifier,
        analyzer_version=ANALYZER_VERSION,
        source_checksum="external-sha1-path-not-content",
        source_file_modified_at=modified,
        source_file_size_bytes=size,
        source_mime_type="image/jpeg",
        byte_size=len(content),
        sha1_hex=sha1(content),
        sha256_hex=hashlib.sha256(content).hexdigest(),
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
        jpeg_eoi_offset=len(content),
        trailing_byte_count=0,
        immich_checksum_match=None,
        issues=[],
        analyzed_at=MODIFIED,
    )


def feature(identifier: UUID, *, digest: str | None = None) -> AssetSimilarityFeatureRecord:
    return AssetSimilarityFeatureRecord(
        asset_id=identifier,
        model_version=SIMILARITY_MODEL_VERSION,
        feature_version=SIMILARITY_FEATURE_VERSION,
        source_file_modified_at=MODIFIED,
        source_file_size_bytes=4,
        source_sha256=digest or str(identifier).replace("-", "") * 2,
        width=100,
        height=80,
        luminance_vector=bytes([128] * 256),
        perceptual_hash="0" * 16,
        color_histogram=bytes([5] * 48),
        thumbnail_sha256=(digest or "a" * 64),
        pixel_normalization_version=1,
        pixel_sha256=(digest or "b" * 64),
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
        analyzed_at=MODIFIED,
    )


def assemble(
    candidate_group: ImmichDuplicateGroup,
    reports: list[AssetIntegrityReportRecord],
    *,
    policy: str = "prefer_upload",
):
    discovered = DiscoveredGroup(
        group_id=f"immich:{candidate_group.duplicate_id}",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id=str(candidate_group.duplicate_id),
        assets=tuple(candidate_group.assets),
    )
    return CrossSourceDuplicateService.assemble(
        [discovered],
        {item.asset_id: item for item in reports},
        DuplicateAnalysisOptions(keeper_policy=policy),
    )


def test_same_file_across_sources_is_exact_with_different_names() -> None:
    content = b"same"
    result = assemble(
        group(
            asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="upload.jpg"),
            asset(EXTERNAL_1, external=True, checksum="sha1-path", filename="renamed.jpg"),
        ),
        [report(EXTERNAL_1, content)],
    )

    assert result.groups[0].status == "exact"
    assert result.groups[0].members[0].evidence.analysis_freshness == "missing"
    assert result.groups[0].members[1].evidence.analysis_freshness == "current"
    assert result.groups[0].members[1].evidence.integrity_status == "healthy"
    assert result.groups[0].members[1].evidence.detected_format == "jpeg"
    assert result.groups[0].keeper_asset_id == UPLOAD_1
    assert result.groups[0].discovery_source == "immich_duplicate"
    assert result.groups[0].classification == "exact_file"
    assert result.groups[0].recommended_action == "resolve"
    assert result.groups[0].auto_resolvable is True
    assert result.groups[0].auto_selected is True
    assert {item.content_checksum for item in result.groups[0].members} == {sha1(content)}


@pytest.mark.parametrize("same_filename", [True, False])
def test_same_size_with_different_content_is_not_exact(same_filename: bool) -> None:
    upload_content = b"left"
    external_content = b"rite"
    result = assemble(
        group(
            asset(
                UPLOAD_1,
                external=False,
                checksum=immich_sha1(upload_content),
                filename="same.jpg",
            ),
            asset(
                EXTERNAL_1,
                external=True,
                checksum=immich_sha1(upload_content),
                filename="same.jpg" if same_filename else "different.jpg",
            ),
        ),
        [report(EXTERNAL_1, external_content)],
    )

    assert result.groups[0].status == "mismatch"
    assert not result.groups[0].eligible


def test_multiple_uploads_and_externals_form_one_exact_group() -> None:
    content = b"same"
    result = assemble(
        group(
            asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
            asset(UPLOAD_2, external=False, checksum=immich_sha1(content), filename="two.jpg"),
            asset(EXTERNAL_1, external=True, checksum="path-one", filename="three.jpg"),
            asset(EXTERNAL_2, external=True, checksum="path-two", filename="four.jpg"),
        ),
        [report(EXTERNAL_1, content), report(EXTERNAL_2, content)],
    )

    assert result.exact_group_count == 1
    assert len(result.groups[0].members) == 4
    assert result.groups[0].group_id == PUBLIC_GROUP_ID
    assert result.groups[0].provider_group_id == str(GROUP_ID)
    assert "duplicate_id" not in result.groups[0].model_dump()
    assert result.groups[0].recommended_primary_asset_id is None
    assert result.groups[0].auto_selected is False
    assert "multiple_equal_candidates" in result.groups[0].recommendation_reason_codes


def test_newest_otherwise_equal_upload_is_recommended() -> None:
    content = b"same"
    result = assemble(
        group(
            asset(
                UPLOAD_1,
                external=False,
                checksum=immich_sha1(content),
                filename="old.jpg",
                uploaded=MODIFIED,
            ),
            asset(
                UPLOAD_2,
                external=False,
                checksum=immich_sha1(content),
                filename="new.jpg",
                uploaded=MODIFIED + timedelta(seconds=1),
            ),
        ),
        [],
    )

    assert result.groups[0].recommended_primary_asset_id == UPLOAD_2
    assert "most_recent_upload" in result.groups[0].recommendation_reason_codes


def test_external_immich_checksum_is_never_used_as_content_sha1() -> None:
    content = b"same"
    checksum = immich_sha1(content)
    result = assemble(
        group(
            asset(UPLOAD_1, external=False, checksum=checksum, filename="same.jpg"),
            asset(EXTERNAL_1, external=True, checksum=checksum, filename="same.jpg"),
        ),
        [],
    )

    assert result.groups[0].status == "unverified"
    assert result.groups[0].members[1].content_checksum is None


def test_similarity_pair_identity_is_order_independent() -> None:
    assert canonical_pair(UPLOAD_1, EXTERNAL_1) == canonical_pair(EXTERNAL_1, UPLOAD_1)


def test_similarity_pair_plan_is_sparse_and_skips_missing_features() -> None:
    pairs = requested_reference_pairs(
        [[UPLOAD_1, EXTERNAL_1, EXTERNAL_2]],
        {UPLOAD_1, EXTERNAL_1},
    )

    assert pairs == {
        (UPLOAD_1, EXTERNAL_1): canonical_pair(UPLOAD_1, EXTERNAL_1),
    }


def test_unavailable_external_is_unverified_not_a_mismatch() -> None:
    content = b"same"
    result = assemble(
        group(
            asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
            asset(
                EXTERNAL_1,
                external=True,
                checksum="path",
                filename="two.jpg",
                offline=True,
            ),
        ),
        [],
    )

    assert result.groups[0].status == "unverified"
    assert "offline" in (result.groups[0].reason or "")


def test_stale_member_evidence_is_exposed_but_not_used_as_current_hash() -> None:
    content = b"same"
    stale = report(EXTERNAL_1, content, modified=MODIFIED - timedelta(seconds=1))

    result = assemble(
        group(
            asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
            asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
        ),
        [stale],
    )

    member = result.groups[0].members[1]
    assert result.groups[0].status == "unverified"
    assert member.content_checksum is None
    assert member.evidence.analysis_freshness == "stale"
    assert member.evidence.integrity_status == "healthy"


def test_keeper_policy_can_prefer_external() -> None:
    content = b"same"
    result = assemble(
        group(
            asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
            asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
        ),
        [report(EXTERNAL_1, content)],
        policy="prefer_external",
    )

    assert result.groups[0].keeper_asset_id == EXTERNAL_1


class FakeImmich:
    def __init__(self, candidate_group: ImmichDuplicateGroup):
        self.candidate_group = candidate_group
        self.created_stacks: list[list[UUID]] = []
        self.resolutions = []
        self.events: list[str] = []
        self.group_active = True
        self.fail_stack_attempts = 0

    async def list_duplicate_groups(self):
        return [self.candidate_group] if self.group_active else []

    async def resolve_duplicate_groups(self, resolutions):
        self.events.append("resolve")
        self.resolutions.extend(resolutions)
        for resolution in resolutions:
            for item in self.candidate_group.assets:
                if item.id in resolution.trash_asset_ids:
                    item.is_trashed = True
        self.group_active = False
        return [{"success": True} for _ in resolutions]

    async def get_asset(self, asset_id):
        return next(item for item in self.candidate_group.assets if item.id == asset_id)

    async def create_stack(self, asset_ids):
        self.events.append("stack")
        if self.fail_stack_attempts:
            self.fail_stack_attempts -= 1
            raise ImmichApiError("create stack")
        self.created_stacks.append(asset_ids)
        for item in self.candidate_group.assets:
            if item.id in asset_ids:
                item.stack = {"id": "ffffffff-ffff-4fff-8fff-ffffffffffff"}

    def public_asset_url(self, asset_id):
        return f"https://immich.test/photos/{asset_id}"


class FakeAssets:
    def __init__(self):
        self.refreshed: list[UUID] = []
        self.removed: list[UUID] = []

    async def refresh_asset(self, item):
        self.refreshed.append(item.id)

    async def remove_assets(self, asset_ids):
        self.removed.extend(asset_ids)


class FakeReports:
    def __init__(self, records, features=None):
        self.records = {item.asset_id: item for item in records}
        self.features = {item.asset_id: item for item in (features or [])}

    async def get_many(self, _ids):
        return self.records

    async def get_similarity_features(self, _ids):
        return self.features


class FakeSimilarity:
    def __init__(self, evidence):
        self.evidence = evidence
        self.calls = []

    async def reference_edges(self, groups, features):
        self.calls.append((groups, features))
        return self.evidence


class FakeReviews:
    def __init__(self, record=None):
        self.record = record
        self.saved = None

    async def get_many(self, _source, provider_group_ids):
        if self.record is None or self.record.provider_group_id not in provider_group_ids:
            return {}
        return {self.record.provider_group_id: self.record}

    async def save(self, **values):
        self.saved = values
        self.record = SimpleNamespace(**values)
        return self.record


class FakeActions:
    def __init__(self, record=None):
        self.created = None
        self.record = record
        self.finished = None

    async def create_duplicate_plan(self, **values):
        self.created = values
        destructive = any(group["trash_asset_ids"] for group in values["groups"])
        return SimpleNamespace(
            id=GROUP_ID,
            status="planned",
            relation_work={"groups": values["groups"]},
            expires_at=values["expires_at"],
            destructive=destructive,
        )

    async def get_plan(self, _plan_id):
        return self.record

    async def claim_plan(self, _plan_id):
        self.record.status = "running"
        return self.record

    async def reopen_duplicate_follow_up(self, _plan_id):
        states = (getattr(self.record, "result", None) or {}).get("group_execution", {})
        if self.record.status != "failed" or not any(
            item.get("state") == "follow_up_pending" for item in states.values()
        ):
            return None
        self.record.status = "planned"
        return self.record

    async def record_duplicate_group_execution(
        self,
        _plan_id,
        group_id,
        state,
        *,
        error=None,
    ):
        result = dict(getattr(self.record, "result", None) or {})
        states = dict(result.get("group_execution") or {})
        states[group_id] = {"state": state, "error": error}
        result["group_execution"] = states
        self.record.result = result

    async def finish_plan(self, _plan_id, status, result):
        self.record.status = status
        phases = (getattr(self.record, "result", None) or {}).get("group_execution", {})
        self.record.result = {**result, "group_execution": phases}
        self.finished = (status, result)


class FakeRuntimeSettings:
    async def get(self):
        return SimpleNamespace(full_batch_size=100, full_min_batch_delay_seconds=0)


class FakeTasks:
    def __init__(self):
        self.submissions = []
        self.task = None

    async def find_active(self, *_args):
        return self.task

    async def submit(self, task_type, payload, **options):
        self.submissions.append((task_type, payload, options))
        self.task = SimpleNamespace(id=UPLOAD_2)
        return self.task

    async def start(self):
        return None


class FakeIntegrity:
    def __init__(self, *, unavailable: bool = False):
        self.calls: list[UUID] = []
        self.unavailable = unavailable

    async def analyze(self, _context, asset_id, *, publish_progress=True):
        self.calls.append(asset_id)
        assert publish_progress is False
        if self.unavailable:
            raise PermanentTaskError("The Immich original was not found.")


class TaskContext:
    def __init__(self):
        self.checkpoints = []

    async def ensure_active(self):
        return None

    async def checkpoint(self, **payload):
        self.checkpoints.append(payload)


@pytest.mark.asyncio
async def test_review_automatically_queues_missing_external_evidence_once() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    tasks = FakeTasks()
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([]),
        FakeActions(),
        tasks,
        SimpleNamespace(),
    )

    first = await service.review()
    second = await service.review()

    assert first.analysis_pending_count == 1
    assert first.analysis_candidate_count == 1
    assert first.analysis_cached_count == 0
    assert first.analysis_task_id == UPLOAD_2
    assert second.analysis_task_id == UPLOAD_2
    assert len(tasks.submissions) == 1


@pytest.mark.asyncio
async def test_review_exposes_sparse_first_member_similarity_evidence() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    upload_feature = feature(UPLOAD_1, digest="1" * 64)
    external_feature = feature(EXTERNAL_1, digest="2" * 64)
    pair = PairSimilarityEvidence(
        similarity_percent=96.5,
        structural_percent=98.0,
        perceptual_percent=95.0,
        color_percent=91.0,
        normalized_luminance_mae=0.01,
        normalized_luminance_rmse=0.02,
        normalized_luminance_ssim=0.99,
        aspect_ratio_difference=0.0,
        dimensions_equal=True,
        exact_thumbnail_match=False,
        exact_pixel_match=True,
        model_version=SIMILARITY_MODEL_VERSION,
        feature_version=SIMILARITY_FEATURE_VERSION,
        comparison_version=SIMILARITY_COMPARISON_VERSION,
    )
    similarity = FakeSimilarity({(UPLOAD_1, EXTERNAL_1): pair})
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports(
            [report(EXTERNAL_1, content)],
            [upload_feature, external_feature],
        ),
        FakeActions(),
        FakeTasks(),
        SimpleNamespace(),
        similarity=similarity,
    )

    result = await service.review()

    assert result.analysis_pending_count == 0
    assert result.analysis_candidate_count == 2
    assert result.analysis_cached_count == 2
    assert result.groups[0].members[0].similarity is not None
    assert result.groups[0].members[0].similarity.state == "reference"
    assert result.groups[0].members[0].similarity.exact_pixel_match is True
    assert (
        result.groups[0].members[0].similarity.feature_version
        == SIMILARITY_FEATURE_VERSION
    )
    assert result.groups[0].members[1].similarity is not None
    assert result.groups[0].members[1].similarity.similarity_percent == 96.5
    assert result.groups[0].members[1].similarity.normalized_luminance_rmse == 0.02
    assert result.groups[0].members[1].similarity.normalized_luminance_ssim == 0.99
    assert result.groups[0].members[1].similarity.dimensions_equal is True
    assert result.groups[0].members[1].similarity.exact_pixel_match is True
    assert result.groups[0].members[1].preservation is not None
    assert result.groups[0].members[1].preservation.pixel_sha256 == "2" * 64
    assert result.groups[0].members[1].preservation.metadata_richness == 0
    assert similarity.calls[0][0] == [[UPLOAD_1, EXTERNAL_1]]


@pytest.mark.asyncio
async def test_companion_similarity_group_exposes_provenance_without_automatic_action() -> None:
    content = b"same"
    members = (
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    discovered = DiscoveredGroup(
        group_id=f"companion:v1:{UPLOAD_1}:{EXTERNAL_1}",
        discovery_source=DiscoverySource.COMPANION_SIMILARITY,
        provider_group_id=f"scan:{UPLOAD_1}:{EXTERNAL_1}",
        assets=members,
        provider_metadata={
            "scan_id": str(GROUP_ID),
            "scan_threshold_percent": "95.0",
            "similarity_percent": "99.2",
        },
    )

    class Discovery:
        async def discover(self):
            return [discovered]

    pair = PairSimilarityEvidence(
        similarity_percent=99.2,
        structural_percent=99.0,
        perceptual_percent=99.5,
        color_percent=98.0,
        exact_thumbnail_match=False,
        exact_pixel_match=False,
        model_version=SIMILARITY_MODEL_VERSION,
        feature_version=SIMILARITY_FEATURE_VERSION,
        comparison_version=1,
    )
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(group(*members)),
        FakeAssets(),
        FakeReports(
            [report(EXTERNAL_1, content)],
            [feature(UPLOAD_1, digest="1" * 64), feature(EXTERNAL_1, digest="2" * 64)],
        ),
        FakeActions(),
        FakeTasks(),
        SimpleNamespace(),
        similarity=FakeSimilarity({(UPLOAD_1, EXTERNAL_1): pair}),
        discovery=Discovery(),
    )

    result = await service.result()
    found = result.groups[0]

    assert found.discovery_source == "companion_similarity"
    assert found.discovery_metadata["scan_id"] == str(GROUP_ID)
    assert found.classification == "likely_same"
    assert found.status == "exact"
    assert found.eligible is False
    assert found.auto_resolvable is False
    assert found.recommended_action == "none"
    assert found.effective_action == "none"
    assert "99.2% visual match" in (found.reason or "")


@pytest.mark.asyncio
async def test_similarity_reference_is_scoped_to_group_members() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    pair = PairSimilarityEvidence(
        similarity_percent=93.0,
        structural_percent=94.0,
        perceptual_percent=92.0,
        color_percent=90.0,
        exact_thumbnail_match=False,
        exact_pixel_match=False,
        model_version=SIMILARITY_MODEL_VERSION,
        feature_version=SIMILARITY_FEATURE_VERSION,
        comparison_version=1,
    )
    similarity = FakeSimilarity({(EXTERNAL_1, UPLOAD_1): pair})
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports(
            [report(EXTERNAL_1, content)],
            [feature(UPLOAD_1), feature(EXTERNAL_1)],
        ),
        FakeActions(),
        FakeTasks(),
        SimpleNamespace(),
        similarity=similarity,
    )

    result = await service.similarity_reference(
        PUBLIC_GROUP_ID,
        DuplicateSimilarityReferenceRequest(reference_asset_id=EXTERNAL_1),
    )

    assert similarity.calls[0][0] == [[EXTERNAL_1, UPLOAD_1]]
    assert result.members[0].similarity is not None
    assert result.members[0].similarity.similarity_percent == 93.0
    assert result.members[1].similarity is not None
    assert result.members[1].similarity.state == "reference"

    with pytest.raises(ActionPlanConflictError, match="not a member"):
        await service.similarity_reference(
            PUBLIC_GROUP_ID,
            DuplicateSimilarityReferenceRequest(reference_asset_id=UPLOAD_2),
        )


@pytest.mark.asyncio
async def test_similarity_backfill_includes_upload_images_without_stream_verification() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    integrity = FakeIntegrity()
    handler = CrossSourceDuplicateTaskHandler(
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content)]),
        integrity,
        include_similarity=True,
    )

    await handler.execute(
        TaskContext(),
        DuplicateAnalysisOptions().model_dump(mode="json"),
    )

    assert integrity.calls == [UPLOAD_1, EXTERNAL_1]


@pytest.mark.asyncio
async def test_review_does_not_queue_current_or_offline_external_evidence() -> None:
    content = b"same"
    current_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    tasks = FakeTasks()
    current_service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(current_group),
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content)]),
        FakeActions(),
        tasks,
        SimpleNamespace(),
    )

    current = await current_service.review()

    assert current.analysis_pending_count == 0
    assert current.analysis_task_id is None
    assert tasks.submissions == []

    offline_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(
            EXTERNAL_1,
            external=True,
            checksum="path",
            filename="two.jpg",
            offline=True,
        ),
    )
    offline_service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(offline_group),
        FakeAssets(),
        FakeReports([]),
        FakeActions(),
        tasks,
        SimpleNamespace(),
    )

    offline = await offline_service.review()

    assert offline.analysis_pending_count == 0
    assert offline.analysis_task_id is None
    assert tasks.submissions == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cached_size", "cached_modified", "expected_calls"),
    [
        (4, MODIFIED, []),
        (5, MODIFIED, [EXTERNAL_1]),
        (4, MODIFIED - timedelta(seconds=1), [EXTERNAL_1]),
    ],
)
async def test_cache_reuse_and_size_mtime_invalidation(
    cached_size: int,
    cached_modified: datetime,
    expected_calls: list[UUID],
) -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    integrity = FakeIntegrity()
    handler = CrossSourceDuplicateTaskHandler(
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content, size=cached_size, modified=cached_modified)]),
        integrity,
    )

    await handler.execute(TaskContext(), DuplicateAnalysisOptions().model_dump(mode="json"))

    assert integrity.calls == expected_calls


@pytest.mark.asyncio
async def test_analysis_hashes_only_external_members_of_immich_groups() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    integrity = FakeIntegrity()
    handler = CrossSourceDuplicateTaskHandler(
        FakeImmich(candidate_group), FakeAssets(), FakeReports([]), integrity
    )

    result = await handler.execute(
        TaskContext(), DuplicateAnalysisOptions().model_dump(mode="json")
    )

    assert integrity.calls == [EXTERNAL_1]
    assert result.counters["candidate_files"] == 1


@pytest.mark.asyncio
async def test_unavailable_candidate_does_not_fail_the_whole_analysis() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    context = TaskContext()
    handler = CrossSourceDuplicateTaskHandler(
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([]),
        FakeIntegrity(unavailable=True),
    )

    result = await handler.execute(context, DuplicateAnalysisOptions().model_dump(mode="json"))

    assert result.counters["files_unavailable"] == 1
    assert context.checkpoints[-1]["progress"]["percent"] == 100.0


@pytest.mark.asyncio
async def test_duplicate_analysis_progress_is_monotonic_across_member_analysis() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
        asset(EXTERNAL_2, external=True, checksum="other-path", filename="three.jpg"),
    )
    context = TaskContext()
    handler = CrossSourceDuplicateTaskHandler(
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([]),
        FakeIntegrity(),
    )

    await handler.execute(
        context,
        DuplicateAnalysisOptions().model_dump(mode="json"),
    )

    progress = [checkpoint["progress"] for checkpoint in context.checkpoints]
    assert [item["percent"] for item in progress] == [0.0, 50.0, 100.0, 100.0]
    assert [(item["completed"], item["total"]) for item in progress] == [
        (0, 2),
        (1, 2),
        (2, 2),
        (2, 2),
    ]


@pytest.mark.asyncio
async def test_review_plan_applies_policy_and_explicit_keeper_override() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    actions = FakeActions()
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content)]),
        actions,
        SimpleNamespace(),
        SimpleNamespace(),
    )

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            group_ids=[PUBLIC_GROUP_ID],
            keeper_overrides={PUBLIC_GROUP_ID: EXTERNAL_1},
        )
    )

    assert plan.group_count == 1
    assert plan.groups[0].keeper_asset_id == EXTERNAL_1
    assert plan.groups[0].keep_asset_ids == [EXTERNAL_1]
    assert plan.groups[0].trash_asset_ids == [UPLOAD_1]
    assert plan.groups[0].group_id == PUBLIC_GROUP_ID
    assert plan.groups[0].provider_group_id == str(GROUP_ID)
    assert actions.created["groups"][0]["group_id"] == PUBLIC_GROUP_ID
    assert "duplicate_id" not in actions.created["groups"][0]
    assert actions.created["options"]["keeper_policy"] == "most_recent"


@pytest.mark.asyncio
async def test_manual_keeper_makes_an_ambiguous_exact_group_plannable() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(UPLOAD_2, external=False, checksum=immich_sha1(content), filename="two.jpg"),
    )
    actions = FakeActions()
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([]),
        actions,
        SimpleNamespace(),
        SimpleNamespace(),
    )

    result = await service.result()
    assert result.groups[0].eligible is True
    assert result.groups[0].auto_resolvable is False

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            group_ids=[PUBLIC_GROUP_ID],
            keeper_overrides={PUBLIC_GROUP_ID: UPLOAD_2},
        )
    )

    assert plan.groups[0].keeper_asset_id == UPLOAD_2
    assert plan.groups[0].trash_asset_ids == [UPLOAD_1]


@pytest.mark.asyncio
async def test_mismatch_group_can_be_manually_planned_as_a_non_destructive_stack() -> None:
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(b"left"), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    actions = FakeActions()
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, b"right")]),
        actions,
        SimpleNamespace(),
        SimpleNamespace(),
    )

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            group_ids=[PUBLIC_GROUP_ID],
            keeper_overrides={PUBLIC_GROUP_ID: UPLOAD_1},
            action_overrides={PUBLIC_GROUP_ID: "stack_all"},
        )
    )

    assert plan.destructive is False
    assert plan.resolve_group_count == 0
    assert plan.stack_group_count == 1
    assert plan.groups[0].action == "stack_all"
    assert plan.groups[0].member_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert plan.groups[0].keep_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert plan.groups[0].trash_asset_ids == []
    assert plan.groups[0].follow_up is not None
    assert plan.groups[0].follow_up.type == "stack"


@pytest.mark.asyncio
async def test_non_destructive_stack_plan_executes_in_safe_mode() -> None:
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(b"left"), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    immich = FakeImmich(candidate_group)
    assets = FakeAssets()
    record = SimpleNamespace(
        id=GROUP_ID,
        action="resolve_duplicates",
        status="planned",
        destructive=False,
        relation_work={
            "options": DuplicateAnalysisOptions().model_dump(mode="json"),
            "groups": [
                {
                    "duplicate_id": str(GROUP_ID),
                    "action": "stack_all",
                    "keeper_asset_id": str(UPLOAD_1),
                    "member_asset_ids": [str(UPLOAD_1), str(EXTERNAL_1)],
                    "trash_asset_ids": [],
                }
            ],
        },
    )
    actions = FakeActions(record)
    service = CrossSourceDuplicateService(
        SimpleNamespace(allow_destructive_actions=False),
        immich,
        assets,
        FakeReports([report(EXTERNAL_1, b"right")]),
        actions,
        SimpleNamespace(),
        FakeRuntimeSettings(),
    )

    outcome = await service.execute_plan(TaskContext(), GROUP_ID)

    assert outcome.status == "completed"
    assert outcome.counters["groups_stacked"] == 1
    assert immich.events == ["resolve", "stack"]
    assert immich.resolutions[0].keep_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert immich.resolutions[0].trash_asset_ids == []
    assert immich.created_stacks == [[UPLOAD_1, EXTERNAL_1]]
    assert assets.refreshed == [UPLOAD_1, EXTERNAL_1]
    assert actions.finished[0] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "expected_disposition", "destructive", "zero_survivors"),
    [
        ("keep_all", "keep", False, 0),
        ("delete_all", "delete", True, 1),
    ],
)
async def test_whole_group_actions_have_explicit_member_dispositions(
    action: str,
    expected_disposition: str,
    destructive: bool,
    zero_survivors: int,
) -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content)]),
        FakeActions(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            group_ids=[PUBLIC_GROUP_ID],
            action_overrides={PUBLIC_GROUP_ID: action},
        )
    )

    assert plan.destructive is destructive
    assert plan.groups[0].keeper_asset_id is None
    assert plan.groups[0].keep_asset_ids == (
        [UPLOAD_1, EXTERNAL_1] if action == "keep_all" else []
    )
    assert {member.disposition for member in plan.groups[0].members} == {expected_disposition}
    assert plan.zero_survivor_group_count == zero_survivors


@pytest.mark.asyncio
async def test_manual_review_is_reused_only_for_the_same_member_fingerprint() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    reviews = FakeReviews()
    service = CrossSourceDuplicateService(
        SimpleNamespace(action_plan_ttl_seconds=900),
        FakeImmich(candidate_group),
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content)]),
        FakeActions(),
        SimpleNamespace(),
        SimpleNamespace(),
        reviews,
    )

    saved = await service.save_review(
        DuplicateReviewUpdate(
            group_id=PUBLIC_GROUP_ID,
            manual_action="keep_all",
            manual_primary_asset_id=EXTERNAL_1,
        )
    )

    assert saved.manual_action == "keep_all"
    assert saved.effective_action == "keep_all"
    assert saved.review_status == "manually_configured"
    assert reviews.saved["provider_group_id"] == PUBLIC_GROUP_ID
    reviews.record.member_fingerprint = "different-membership"
    drifted = await service.result()
    assert drifted.groups[0].manual_action is None
    assert drifted.groups[0].review_status == "drifted"


@pytest.mark.asyncio
async def test_delete_all_uses_explicit_all_trash_duplicate_resolution() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    immich = FakeImmich(candidate_group)
    assets = FakeAssets()
    record = SimpleNamespace(
        id=GROUP_ID,
        action="resolve_duplicates",
        status="planned",
        destructive=True,
        relation_work={
            "options": DuplicateAnalysisOptions().model_dump(mode="json"),
            "groups": [
                {
                    "duplicate_id": str(GROUP_ID),
                    "action": "delete_all",
                    "keeper_asset_id": None,
                    "member_asset_ids": [str(UPLOAD_1), str(EXTERNAL_1)],
                    "trash_asset_ids": [str(UPLOAD_1), str(EXTERNAL_1)],
                }
            ],
        },
    )
    actions = FakeActions(record)
    reviews = FakeReviews()
    service = CrossSourceDuplicateService(
        SimpleNamespace(allow_destructive_actions=True),
        immich,
        assets,
        FakeReports([report(EXTERNAL_1, content)]),
        actions,
        SimpleNamespace(),
        FakeRuntimeSettings(),
        reviews,
    )

    outcome = await service.execute_plan(TaskContext(), GROUP_ID)

    assert outcome.status == "completed"
    assert outcome.counters["groups_deleted_all"] == 1
    assert immich.resolutions[0].keep_asset_ids == []
    assert immich.resolutions[0].trash_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert assets.removed == [UPLOAD_1, EXTERNAL_1]
    assert reviews.saved["review_status"] == "reviewed_delete_all"


@pytest.mark.asyncio
async def test_keep_all_resolves_provider_group_without_trashing_members() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    immich = FakeImmich(candidate_group)
    record = SimpleNamespace(
        id=GROUP_ID,
        action="resolve_duplicates",
        status="planned",
        destructive=False,
        result=None,
        relation_work={
            "options": DuplicateAnalysisOptions().model_dump(mode="json"),
            "groups": [
                {
                    "duplicate_id": str(GROUP_ID),
                    "action": "keep_all",
                    "keeper_asset_id": None,
                    "member_asset_ids": [str(UPLOAD_1), str(EXTERNAL_1)],
                    "trash_asset_ids": [],
                }
            ],
        },
    )
    actions = FakeActions(record)
    service = CrossSourceDuplicateService(
        SimpleNamespace(allow_destructive_actions=False),
        immich,
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content)]),
        actions,
        SimpleNamespace(),
        FakeRuntimeSettings(),
    )

    outcome = await service.execute_plan(TaskContext(), GROUP_ID)

    assert outcome.status == "completed"
    assert immich.resolutions[0].keep_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert immich.resolutions[0].trash_asset_ids == []
    assert await immich.list_duplicate_groups() == []


@pytest.mark.asyncio
async def test_failed_stack_follow_up_resumes_without_replaying_resolution() -> None:
    content = b"same"
    candidate_group = group(
        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    )
    immich = FakeImmich(candidate_group)
    immich.fail_stack_attempts = 1
    record = SimpleNamespace(
        id=GROUP_ID,
        action="resolve_duplicates",
        status="planned",
        destructive=False,
        result=None,
        relation_work={
            "options": DuplicateAnalysisOptions().model_dump(mode="json"),
            "groups": [
                {
                    "duplicate_id": str(GROUP_ID),
                    "action": "stack_all",
                    "keeper_asset_id": str(UPLOAD_1),
                    "member_asset_ids": [str(UPLOAD_1), str(EXTERNAL_1)],
                    "trash_asset_ids": [],
                }
            ],
        },
    )
    actions = FakeActions(record)
    service = CrossSourceDuplicateService(
        SimpleNamespace(allow_destructive_actions=False),
        immich,
        FakeAssets(),
        FakeReports([report(EXTERNAL_1, content)]),
        actions,
        SimpleNamespace(),
        FakeRuntimeSettings(),
    )

    first = await service.execute_plan(TaskContext(), GROUP_ID)
    assert first.status == "failed"
    assert record.result["group_execution"][PUBLIC_GROUP_ID]["state"] == "follow_up_pending"

    record.status = "running"
    second = await service.execute_plan(TaskContext(), GROUP_ID)

    assert second.status == "completed"
    assert immich.events == ["resolve", "stack", "stack"]
    assert len(immich.resolutions) == 1
    assert record.result["group_execution"][PUBLIC_GROUP_ID]["state"] == "completed"


@pytest.mark.asyncio
async def test_delete_all_plan_is_blocked_by_safe_mode_before_task_submission() -> None:
    record = SimpleNamespace(
        id=GROUP_ID,
        action="resolve_duplicates",
        status="planned",
        destructive=True,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    service = CrossSourceDuplicateService(
        SimpleNamespace(allow_destructive_actions=False),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        FakeActions(record),
        FakeTasks(),
        SimpleNamespace(),
    )

    with pytest.raises(DestructiveActionsDisabledError):
        await service.start_resolution(DuplicateResolutionExecuteRequest(plan_id=GROUP_ID))


@pytest.mark.asyncio
async def test_incomplete_stack_follow_up_can_resume_after_plan_expiry() -> None:
    record = SimpleNamespace(
        id=GROUP_ID,
        action="resolve_duplicates",
        status="failed",
        destructive=False,
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
        result={
            "group_execution": {
                PUBLIC_GROUP_ID: {"state": "follow_up_pending", "error": "stack_follow_up_failed"}
            }
        },
    )
    tasks = FakeTasks()
    service = CrossSourceDuplicateService(
        SimpleNamespace(allow_destructive_actions=False),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        FakeActions(record),
        tasks,
        SimpleNamespace(),
    )

    started = await service.start_resolution(
        DuplicateResolutionExecuteRequest(plan_id=GROUP_ID)
    )

    assert started.task_id == UPLOAD_2
    assert tasks.submissions[0][1] == {"plan_id": str(GROUP_ID)}

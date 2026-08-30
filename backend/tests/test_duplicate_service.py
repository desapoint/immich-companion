"""Immich-group candidate, cache, and checksum-semantics regressions."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from companion.duplicate_schema import (
    DuplicateAnalysisOptions,
    DuplicateResolutionPlanRequest,
)
from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
)
from companion.immich import ImmichAsset, ImmichDuplicateGroup
from companion.models import AssetIntegrityReportRecord
from companion.task_coordinator import PermanentTaskError

UPLOAD_1 = UUID("11111111-1111-4111-8111-111111111111")
UPLOAD_2 = UUID("22222222-2222-4222-8222-222222222222")
EXTERNAL_1 = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EXTERNAL_2 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
LIBRARY_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
GROUP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
MODIFIED = datetime(2026, 8, 29, 12, tzinfo=UTC)


def sha1(payload: bytes) -> str:
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


def immich_sha1(payload: bytes) -> str:
    return base64.b64encode(
        hashlib.sha1(payload, usedforsecurity=False).digest()
    ).decode()


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
        analyzer_version=1,
        source_checksum="external-sha1-path-not-content",
        source_file_modified_at=modified,
        source_file_size_bytes=size,
        source_mime_type="image/jpeg",
        byte_size=len(content),
        sha1_hex=sha1(content),
        sha256_hex=hashlib.sha256(content).hexdigest(),
        detected_format="jpeg",
        classification="healthy",
        structurally_valid=True,
        jpeg_eoi_offset=len(content),
        trailing_byte_count=0,
        immich_checksum_match=None,
        issues=[],
        analyzed_at=MODIFIED,
    )


def assemble(
    candidate_group: ImmichDuplicateGroup,
    reports: list[AssetIntegrityReportRecord],
    *,
    policy: str = "prefer_upload",
):
    return CrossSourceDuplicateService.assemble(
        [candidate_group],
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

    async def list_duplicate_groups(self):
        return [self.candidate_group]

    async def get_asset(self, asset_id):
        return next(item for item in self.candidate_group.assets if item.id == asset_id)

    def public_asset_url(self, asset_id):
        return f"https://immich.test/photos/{asset_id}"


class FakeAssets:
    def __init__(self):
        self.refreshed: list[UUID] = []

    async def refresh_asset(self, item):
        self.refreshed.append(item.id)


class FakeReports:
    def __init__(self, records):
        self.records = {item.asset_id: item for item in records}

    async def get_many(self, _ids):
        return self.records


class FakeActions:
    def __init__(self):
        self.created = None

    async def create_duplicate_plan(self, **values):
        self.created = values
        return SimpleNamespace(
            id=GROUP_ID,
            status="planned",
            relation_work={"groups": values["groups"]},
            expires_at=values["expires_at"],
        )


class FakeIntegrity:
    def __init__(self, *, unavailable: bool = False):
        self.calls: list[UUID] = []
        self.unavailable = unavailable

    async def analyze(self, _context, asset_id):
        self.calls.append(asset_id)
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

    result = await handler.execute(
        context, DuplicateAnalysisOptions().model_dump(mode="json")
    )

    assert result.counters["files_unavailable"] == 1
    assert context.checkpoints[-1]["progress"]["percent"] == 100.0


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
            duplicate_ids=[GROUP_ID],
            keeper_overrides={GROUP_ID: EXTERNAL_1},
        )
    )

    assert plan.group_count == 1
    assert plan.groups[0].keeper_asset_id == EXTERNAL_1
    assert plan.groups[0].trash_asset_ids == [UPLOAD_1]
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
            duplicate_ids=[GROUP_ID],
            keeper_overrides={GROUP_ID: UPLOAD_2},
        )
    )

    assert plan.groups[0].keeper_asset_id == UPLOAD_2
    assert plan.groups[0].trash_asset_ids == [UPLOAD_1]

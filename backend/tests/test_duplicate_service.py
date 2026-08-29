"""Cross-source candidate, cache, and checksum-semantics regressions."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from companion.duplicate_repository import (
    CrossSourceCandidateAsset,
    DuplicateRepository,
    ExternalFingerprintTarget,
)
from companion.duplicate_schema import (
    CrossSourceDuplicateResult,
    CrossSourceUnverifiedCandidate,
)
from companion.duplicate_service import (
    CrossSourceDuplicateService,
    CrossSourceDuplicateTaskHandler,
)
from companion.models import AssetIntegrityReportRecord, AssetRecord
from companion.task_coordinator import PermanentTaskError

UPLOAD_1 = UUID("11111111-1111-4111-8111-111111111111")
UPLOAD_2 = UUID("22222222-2222-4222-8222-222222222222")
EXTERNAL_1 = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EXTERNAL_2 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
LIBRARY_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MODIFIED = datetime(2026, 8, 29, 12, tzinfo=UTC)


def sha1(payload: bytes) -> str:
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()


def immich_sha1(payload: bytes) -> str:
    return base64.b64encode(
        hashlib.sha1(payload, usedforsecurity=False).digest()
    ).decode()


def candidate(
    identifier: UUID,
    *,
    external: bool,
    checksum: str | None,
    filename: str,
    size: int = 4,
    modified: datetime = MODIFIED,
    offline: bool = False,
) -> CrossSourceCandidateAsset:
    return CrossSourceCandidateAsset(
        id=identifier,
        library_id=LIBRARY_ID if external else None,
        asset_type="IMAGE",
        original_file_name=filename,
        original_mime_type="image/jpeg",
        immich_checksum=checksum,
        file_size_bytes=size,
        file_modified_at=modified,
        width=1,
        height=1,
        duration=None,
        is_offline=offline,
    )


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
        source_checksum="immich-sha1-path-is-not-content",
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
    uploads: list[CrossSourceCandidateAsset],
    externals: list[CrossSourceCandidateAsset],
    reports: list[AssetIntegrityReportRecord],
):
    return CrossSourceDuplicateService.assemble(
        [*uploads, *externals], {item.asset_id: item for item in reports}
    )


def test_same_file_across_sources_is_confirmed_even_with_different_names() -> None:
    content = b"same"
    result = assemble(
        [candidate(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="upload.jpg")],
        [candidate(EXTERNAL_1, external=True, checksum="path-checksum", filename="renamed.jpg")],
        [report(EXTERNAL_1, content)],
    )

    assert result.confirmed_groups[0].content_checksum == sha1(content)
    assert result.confirmed_groups[0].upload_asset_ids == [UPLOAD_1]
    assert result.confirmed_groups[0].external_asset_ids == [EXTERNAL_1]


@pytest.mark.parametrize("same_filename", [True, False])
def test_same_size_with_different_content_is_not_a_match(same_filename: bool) -> None:
    upload_content = b"left"
    external_content = b"rite"
    result = assemble(
        [
            candidate(
                UPLOAD_1,
                external=False,
                checksum=immich_sha1(upload_content),
                filename="same.jpg",
            )
        ],
        [
            candidate(
                EXTERNAL_1,
                external=True,
                checksum=immich_sha1(upload_content),
                filename="same.jpg" if same_filename else "different.jpg",
            )
        ],
        [report(EXTERNAL_1, external_content)],
    )

    assert result.confirmed_groups == []
    assert result.verified_non_match_count == 1


def test_multiple_uploads_and_externals_share_one_confirmed_group() -> None:
    content = b"same"
    result = assemble(
        [
            candidate(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
            candidate(UPLOAD_2, external=False, checksum=immich_sha1(content), filename="two.jpg"),
        ],
        [
            candidate(EXTERNAL_1, external=True, checksum="path-one", filename="three.jpg"),
            candidate(EXTERNAL_2, external=True, checksum="path-two", filename="four.jpg"),
        ],
        [report(EXTERNAL_1, content), report(EXTERNAL_2, content)],
    )

    assert result.confirmed_groups[0].upload_asset_ids == [UPLOAD_1, UPLOAD_2]
    assert result.confirmed_groups[0].external_asset_ids == [EXTERNAL_1, EXTERNAL_2]


def test_external_immich_checksum_is_never_used_as_content_sha1() -> None:
    content = b"same"
    upload_checksum = immich_sha1(content)
    result = assemble(
        [candidate(UPLOAD_1, external=False, checksum=upload_checksum, filename="same.jpg")],
        [candidate(EXTERNAL_1, external=True, checksum=upload_checksum, filename="same.jpg")],
        [],
    )

    assert result.confirmed_groups == []
    assert result.unverified_candidates[0].reason == "content_hash_missing"


def test_offline_external_without_cached_hash_is_unverified() -> None:
    content = b"same"
    result = assemble(
        [candidate(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg")],
        [
            candidate(
                EXTERNAL_1,
                external=True,
                checksum="path",
                filename="two.jpg",
                offline=True,
            )
        ],
        [],
    )

    assert result.confirmed_groups == []
    assert result.unverified_candidates[0].reason == "external_file_unavailable"


class FakeCandidates:
    def __init__(self, items):
        self.items = items

    async def cross_source_candidates(self):
        return self.items

    async def external_fingerprint_targets(self):
        return [
            ExternalFingerprintTarget(
                id=item.id,
                is_offline=item.is_offline,
                file_size_bytes=item.file_size_bytes,
                file_modified_at=item.file_modified_at,
            )
            for item in self.items
            if item.library_id is not None
        ]


class FakeReports:
    def __init__(self, records):
        self.records = records

    async def get_many(self, _ids):
        return {item.asset_id: item for item in self.records}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cached_size", "cached_modified", "expected"),
    [
        (4, MODIFIED, []),
        (5, MODIFIED, [EXTERNAL_1]),
        (4, MODIFIED - timedelta(seconds=1), [EXTERNAL_1]),
    ],
)
async def test_external_cache_reuse_and_size_mtime_invalidation(
    cached_size: int,
    cached_modified: datetime,
    expected: list[UUID],
) -> None:
    content = b"same"
    items = [
        candidate(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        candidate(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),
    ]
    service = CrossSourceDuplicateService(
        FakeCandidates(items),
        FakeReports([report(EXTERNAL_1, content, size=cached_size, modified=cached_modified)]),
        SimpleNamespace(),
    )

    pending = await service.candidates_needing_hash()

    assert [item.id for item in pending] == expected


@pytest.mark.asyncio
async def test_on_demand_scan_hashes_all_unfingerprinted_externals() -> None:
    content = b"same"
    items = [
        candidate(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),
        candidate(EXTERNAL_1, external=True, checksum="path-one", filename="two.jpg"),
        candidate(EXTERNAL_2, external=True, checksum="path-two", filename="unrelated.jpg", size=9),
    ]
    service = CrossSourceDuplicateService(
        FakeCandidates(items), FakeReports([]), SimpleNamespace()
    )

    pending = await service.candidates_needing_hash()

    assert [item.id for item in pending] == [EXTERNAL_1, EXTERNAL_2]


def test_candidate_query_is_grouped_in_sql_and_uses_the_size_type_index() -> None:
    sql = str(
        DuplicateRepository.candidate_statement().compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    index_names = {index.name for index in AssetRecord.__table__.indexes}

    assert "GROUP BY assets.file_size_bytes, assets.asset_type" in sql
    assert "bool_or(assets.library_id IS NULL)" in sql
    assert "cross_source_candidate_keys" in sql
    assert "ix_assets_cross_source_candidate" in index_names


class UnavailableImmich:
    async def count_assets(self):
        return 0

    async def iter_asset_pages(self, **_kwargs):
        if False:
            yield None


class UnavailableCandidates:
    def __init__(self):
        self.updated = []

    async def update_file_size(self, asset_id, size):
        self.updated.append((asset_id, size))


class UnavailableIntegrity:
    async def analyze(self, _context, _asset_id):
        raise PermanentTaskError("The Immich original was not found.")


class UnavailableService:
    async def candidates_needing_hash(self):
        return [
            ExternalFingerprintTarget(
                id=EXTERNAL_1,
                is_offline=False,
                file_size_bytes=4,
                file_modified_at=MODIFIED,
            )
        ]

    async def result(self):
        return CrossSourceDuplicateResult(
            generated_at=MODIFIED,
            candidate_asset_count=2,
            candidate_external_count=1,
            verified_external_count=0,
            verified_non_match_count=0,
            confirmed_groups=[],
            unverified_candidates=[
                CrossSourceUnverifiedCandidate(
                    external_asset_id=EXTERNAL_1,
                    upload_asset_ids=[UPLOAD_1],
                    reason="content_hash_missing",
                )
            ],
        )


class TaskContext:
    def __init__(self):
        self.checkpoints = []

    async def ensure_active(self):
        return None

    async def checkpoint(self, **payload):
        self.checkpoints.append(payload)


@pytest.mark.asyncio
async def test_unavailable_external_is_unverified_without_failing_the_scan() -> None:
    context = TaskContext()
    handler = CrossSourceDuplicateTaskHandler(
        UnavailableImmich(),
        UnavailableCandidates(),
        UnavailableService(),
        UnavailableIntegrity(),
    )

    result = await handler.execute(context, {})

    assert result.counters["external_unavailable"] == 1
    assert result.summary["unverified_candidate_count"] == 1
    assert context.checkpoints[-1]["progress"]["percent"] == 100.0

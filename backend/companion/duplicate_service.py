"""Lazy, bounded upload/external exact-content comparison."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from companion.duplicate_repository import (
    CrossSourceCandidateAsset,
    DuplicateRepository,
    ExternalFingerprintTarget,
)
from companion.duplicate_schema import (
    CrossSourceDuplicateGroup,
    CrossSourceDuplicateResult,
    CrossSourceDuplicateTaskStart,
    CrossSourceUnverifiedCandidate,
    CrossSourceUnverifiedReason,
)
from companion.immich import ImmichApiClient, ImmichApiError
from companion.integrity import decode_immich_sha1
from companion.integrity_repository import IntegrityRepository
from companion.integrity_service import INTEGRITY_TASK_TYPE, IntegrityTaskHandler
from companion.models import AssetIntegrityReportRecord
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
CROSS_SOURCE_METADATA_PAGE_SIZE = 1000


def _external_report_current(
    candidate: CrossSourceCandidateAsset | ExternalFingerprintTarget,
    report: AssetIntegrityReportRecord | None,
) -> bool:
    return bool(
        report is not None
        and report.source_file_modified_at == candidate.file_modified_at
        and candidate.file_size_bytes is not None
        and report.source_file_size_bytes == candidate.file_size_bytes
    )


class CrossSourceDuplicateService:
    """Assemble persisted results and launch missing external fingerprints."""

    def __init__(
        self,
        candidates: DuplicateRepository,
        reports: IntegrityRepository,
        tasks: TaskCoordinator,
    ) -> None:
        self._candidates = candidates
        self._reports = reports
        self._tasks = tasks

    async def start(self) -> CrossSourceDuplicateTaskStart:
        active = await self._tasks.find_active(CROSS_SOURCE_DUPLICATE_TASK_TYPE, "global")
        if active is None:
            active = await self._tasks.submit(
                CROSS_SOURCE_DUPLICATE_TASK_TYPE,
                {},
                priority=50,
                lane_key=INTEGRITY_TASK_TYPE,
                deduplication_key="global",
            )
        return CrossSourceDuplicateTaskStart(task_id=active.id)

    async def result(self) -> CrossSourceDuplicateResult:
        candidates = await self._candidates.cross_source_candidates()
        reports = await self._reports.get_many(
            [candidate.id for candidate in candidates if candidate.library_id is not None]
        )
        return self.assemble(candidates, reports)

    async def candidates_needing_hash(self) -> list[ExternalFingerprintTarget]:
        candidates = await self._candidates.external_fingerprint_targets()
        reports = await self._reports.get_many([candidate.id for candidate in candidates])
        return [
            candidate
            for candidate in candidates
            if not candidate.is_offline
            and not _external_report_current(candidate, reports.get(candidate.id))
        ]

    @staticmethod
    def assemble(
        candidates: list[CrossSourceCandidateAsset],
        reports: dict[Any, AssetIntegrityReportRecord],
    ) -> CrossSourceDuplicateResult:
        groups: dict[tuple[int, str], list[CrossSourceCandidateAsset]] = defaultdict(list)
        for candidate in candidates:
            groups[(candidate.file_size_bytes, candidate.asset_type)].append(candidate)

        confirmed: dict[str, tuple[set[Any], set[Any]]] = {}
        unverified: list[CrossSourceUnverifiedCandidate] = []
        candidate_external_count = 0
        verified_external_count = 0
        verified_non_match_count = 0

        for group_candidates in groups.values():
            uploads = [item for item in group_candidates if item.library_id is None]
            externals = [item for item in group_candidates if item.library_id is not None]
            upload_hashes: dict[str, list[Any]] = defaultdict(list)
            for upload in uploads:
                checksum = decode_immich_sha1(upload.immich_checksum)
                if checksum is not None:
                    upload_hashes[checksum.hex()].append(upload.id)

            for external in externals:
                candidate_external_count += 1
                report = reports.get(external.id)
                current = _external_report_current(external, report)
                if not current:
                    reason: CrossSourceUnverifiedReason
                    if external.is_offline:
                        reason = "external_file_unavailable"
                    elif report is None:
                        reason = "content_hash_missing"
                    else:
                        reason = "content_hash_stale"
                    unverified.append(
                        CrossSourceUnverifiedCandidate(
                            external_asset_id=external.id,
                            upload_asset_ids=[item.id for item in uploads],
                            reason=reason,
                        )
                    )
                    continue

                verified_external_count += 1
                assert report is not None
                matching_uploads = upload_hashes.get(report.sha1_hex, [])
                if not upload_hashes:
                    unverified.append(
                        CrossSourceUnverifiedCandidate(
                            external_asset_id=external.id,
                            upload_asset_ids=[item.id for item in uploads],
                            reason="upload_checksum_unavailable",
                        )
                    )
                elif matching_uploads:
                    upload_ids, external_ids = confirmed.setdefault(
                        report.sha1_hex, (set(), set())
                    )
                    upload_ids.update(matching_uploads)
                    external_ids.add(external.id)
                else:
                    verified_non_match_count += 1

        confirmed_groups = [
            CrossSourceDuplicateGroup(
                content_checksum=checksum,
                upload_asset_ids=sorted(upload_ids),
                external_asset_ids=sorted(external_ids),
            )
            for checksum, (upload_ids, external_ids) in sorted(confirmed.items())
        ]
        unverified.sort(key=lambda item: item.external_asset_id)
        return CrossSourceDuplicateResult(
            generated_at=datetime.now(UTC),
            candidate_asset_count=len(candidates),
            candidate_external_count=candidate_external_count,
            verified_external_count=verified_external_count,
            verified_non_match_count=verified_non_match_count,
            confirmed_groups=confirmed_groups,
            unverified_candidates=unverified,
        )


class CrossSourceDuplicateTaskHandler:
    """Hydrate cheap metadata, then hash only unresolved external candidates."""

    task_type = CROSS_SOURCE_DUPLICATE_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 2

    def __init__(
        self,
        immich: ImmichApiClient,
        candidates: DuplicateRepository,
        service: CrossSourceDuplicateService,
        integrity: IntegrityTaskHandler,
    ) -> None:
        self._immich = immich
        self._candidates = candidates
        self._service = service
        self._integrity = integrity

    async def execute(self, context: TaskContext, _payload: dict[str, Any]) -> TaskResult:
        total_assets = await self._immich.count_assets()
        metadata_processed = 0
        sizes_recorded = 0
        async for _, page in self._immich.iter_asset_pages(
            page_size=CROSS_SOURCE_METADATA_PAGE_SIZE,
            with_exif=True,
        ):
            await context.ensure_active()
            sizes_recorded += await self._candidates.update_file_sizes(page.items)
            metadata_processed += len(page.items)
            percent = (
                min(round(metadata_processed / total_assets * 100, 1), 99.0)
                if total_assets
                else None
            )
            await context.checkpoint(
                checkpoint={"phase": "metadata", "assets_processed": metadata_processed},
                counters={"metadata_assets": metadata_processed, "sizes_recorded": sizes_recorded},
                progress={
                    "phase": "candidate_metadata",
                    "completed": metadata_processed,
                    "total": total_assets,
                    "percent": percent,
                    "detail": "Collecting exact file sizes from Immich…",
                },
            )

        unresolved = await self._service.candidates_needing_hash()
        attempted = 0
        unavailable = 0
        for attempted, candidate in enumerate(unresolved, start=1):
            await context.ensure_active()
            try:
                report = await self._integrity.analyze(context, candidate.id)
                await self._candidates.update_file_size(candidate.id, report.byte_size)
            except (PermanentTaskError, RetryableTaskError, ImmichApiError):
                unavailable += 1
            await context.checkpoint(
                checkpoint={"phase": "fingerprinting", "asset_id": str(candidate.id)},
                counters={
                    "metadata_assets": metadata_processed,
                    "sizes_recorded": sizes_recorded,
                    "external_attempted": attempted,
                    "external_unavailable": unavailable,
                },
                progress={
                    "phase": "external_fingerprints",
                    "completed": attempted,
                    "total": len(unresolved),
                    "percent": round(attempted / len(unresolved) * 100, 1),
                    "detail": "Calculating external content fingerprints…",
                },
            )

        result = await self._service.result()
        await context.checkpoint(
            checkpoint={"phase": "complete"},
            counters={
                "metadata_assets": metadata_processed,
                "sizes_recorded": sizes_recorded,
                "external_attempted": attempted,
                "external_unavailable": unavailable,
            },
            progress={
                "phase": "complete",
                "completed": 1,
                "total": 1,
                "percent": 100.0,
                "detail": "Cross-source comparison is ready.",
            },
        )
        return TaskResult(
            summary={
                "confirmed_group_count": len(result.confirmed_groups),
                "unverified_candidate_count": len(result.unverified_candidates),
            },
            counters={
                "candidate_assets": result.candidate_asset_count,
                "candidate_external": result.candidate_external_count,
                "verified_external": result.verified_external_count,
                "external_unavailable": unavailable,
            },
        )

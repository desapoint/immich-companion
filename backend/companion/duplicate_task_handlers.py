"""Duplicate evidence task handlers."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Any, Literal
from uuid import UUID

from companion.action_repository import ActionRepository
from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
    DestructiveActionsDisabledError,
)
from companion.asset_repository import AssetRepository
from companion.config import Settings
from companion.contained_duplicate_resolution import _is_contained_resolution_step
from companion.discovery import (
    DiscoveredGroup,
    GroupDiscoveryProvider,
    ImmichDuplicateProvider,
)
from companion.duplicate_identity import member_set_key, stable_group_key
from companion.duplicate_keeper_rules import choose_keeper
from companion.duplicate_policy import DuplicatePolicyRepository
from companion.duplicate_review_repository import DuplicateReviewRepository
from companion.duplicate_schema import (
    COMPLETED_DUPLICATE_REVIEW_STATUSES,
    CrossSourceDuplicateResult,
    CrossSourceDuplicateTaskStart,
    DuplicateAdmissionEvidence,
    DuplicateAnalysisOptions,
    DuplicateGroupDraft,
    DuplicateGroupDraftUpdate,
    DuplicateKeeperSelectionRequest,
    DuplicateKeeperSelectionResult,
    DuplicateMember,
    DuplicateMemberEvidence,
    DuplicatePreservationEvidence,
    DuplicateResolutionExecuteRequest,
    DuplicateResolutionPlan,
    DuplicateResolutionPlanGroup,
    DuplicateResolutionPlanRequest,
    DuplicateReviewUpdate,
    DuplicateSearchPage,
    DuplicateSimilarityEvidence,
    DuplicateSimilarityReferenceRequest,
    DuplicateWorkspaceGroupReference,
    DuplicateWorkspaceMembership,
    DuplicateWorkspaceMembershipRequest,
    DuplicateWorkspacePresetRequest,
    DuplicateWorkspaceResetRequest,
    DuplicateWorkspaceSelectionDelta,
    DuplicateWorkspaceSelectionUpdate,
    DuplicateWorkspaceState,
    ExactDuplicateGroup,
)
from companion.group_decision import (
    CandidateGroup,
    CandidateMember,
    DiscoverySource,
    GroupClassification,
    ResolutionPolicy,
    decide_group,
)
from companion.immich import (
    ImmichApiClient,
    ImmichApiError,
    ImmichAsset,
    ImmichDuplicateResolution,
)
from companion.integrity import decode_immich_sha1
from companion.integrity_repository import (
    IntegrityRepository,
    preservation_feature_freshness,
    report_freshness,
)
from companion.integrity_service import (
    INTEGRITY_CHUNK_SIZE,
    INTEGRITY_TASK_TYPE,
    IntegrityTaskHandler,
)
from companion.models import (
    ActionPlanRecord,
    AssetImagePreservationFeatureRecord,
    AssetIntegrityReportRecord,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_features import PIXEL_NORMALIZATION_VERSION
from companion.similarity_generation import StaleSimilarityEvidenceEpochError
from companion.similarity_index_service import SimilarityIndexMaintainer
from companion.similarity_repository import (
    PairSimilarityEvidence,
    SimilarityRepository,
    canonical_pair,
)
from companion.similarity_scan_repository import SimilarityScanRepository
from companion.similarity_search_repository import SimilaritySearchRepository
from companion.stack_service import StackSelectionError, StackService
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"

logger = logging.getLogger(__name__)


def _options_key(options: DuplicateAnalysisOptions) -> str:
    raw = json.dumps(options.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _plan_digest(groups: list[dict[str, Any]]) -> str:
    raw = json.dumps(groups, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _stable_fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _source_fingerprint(assets: list[Any]) -> str:
    return _stable_fingerprint(
        [
            {
                "asset_id": str(asset.id),
                "file_modified_at": asset.file_modified_at.isoformat(),
                "file_size_bytes": asset.file_size_bytes,
            }
            for asset in sorted(assets, key=lambda item: str(item.id))
        ]
    )


def _metadata_int(metadata: Mapping[str, str], name: str) -> int | None:
    value = metadata.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _metadata_float(metadata: Mapping[str, str], name: str) -> float | None:
    value = metadata.get(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _member_fingerprint(asset_ids: list[UUID]) -> str:
    return member_set_key(asset_ids)


def _member_dispositions(
    action: str,
    member_ids: list[UUID],
    primary_id: UUID | None,
) -> list[dict[str, Any]]:
    dispositions: list[dict[str, Any]] = []
    for asset_id in member_ids:
        disposition = (
            "keep"
            if action == "resolve" and asset_id == primary_id
            else "delete"
            if action == "resolve"
            else "stack"
            if action == "stack_all"
            else "keep"
            if action == "keep_all"
            else "no_change"
        )
        dispositions.append(
            {
                "asset_id": str(asset_id),
                "disposition": disposition,
                "primary": asset_id == primary_id,
            }
        )
    return dispositions


def _action_for_dispositions(dispositions: list[str]) -> str:
    """Describe a complete member partition from member-level decisions."""

    values = set(dispositions)
    if values == {"keep"}:
        return "keep_all"
    if values == {"stack"}:
        return "stack_all"
    if dispositions.count("keep") == 1 and dispositions.count("delete") == len(dispositions) - 1:
        return "resolve"
    return "mixed"


def _reviewed_delete_supported(group: ExactDuplicateGroup) -> bool:
    """Return whether reviewed member deletion is valid for the current group."""

    return group.status != "ineligible" and len(group.members) >= 2


def _metadata_keeper_for_plan(
    keep_ids: list[UUID],
    trash_ids: list[UUID],
) -> UUID | None:
    """Return the sole surviving metadata target for a destructive resolution."""

    return keep_ids[0] if trash_ids and len(keep_ids) == 1 else None


def _contained_native_resolution(
    planned: dict[str, Any],
) -> ImmichDuplicateResolution | None:
    """Return the native Immich resolution for a hidden contained child step."""

    if (
        not _is_contained_resolution_step(planned)
        or planned.get("discovery_source") != DiscoverySource.IMMICH_DUPLICATE.value
    ):
        return None
    keep_ids = [UUID(value) for value in planned.get("keep_asset_ids", [])]
    trash_ids = [UUID(value) for value in planned.get("trash_asset_ids", [])]
    if len(keep_ids) != 1 or not trash_ids:
        return None
    provider_group_id = planned.get("provider_group_id")
    if provider_group_id is None:
        raise ValueError("Contained Immich duplicate group has no provider identifier")
    return ImmichDuplicateResolution(
        duplicate_id=UUID(str(provider_group_id)),
        keep_asset_ids=keep_ids,
        trash_asset_ids=trash_ids,
    )


def _normalize_plan_group(group: dict[str, Any]) -> dict[str, Any]:
    """Normalize persisted plans to the current member-partition contract."""

    normalized = dict(group)
    legacy_id = normalized.get("duplicate_id")
    if "group_id" not in normalized and legacy_id is not None:
        normalized["group_id"] = f"immich:{legacy_id}"
    normalized.setdefault("discovery_source", DiscoverySource.IMMICH_DUPLICATE.value)
    if "provider_group_id" not in normalized:
        normalized["provider_group_id"] = legacy_id
    normalized.setdefault("action", "resolve")
    normalized.setdefault(
        "member_asset_ids",
        [
            *([normalized["keeper_asset_id"]] if normalized.get("keeper_asset_id") else []),
            *normalized.get("trash_asset_ids", []),
        ],
    )
    member_ids = [UUID(value) for value in normalized["member_asset_ids"]]
    normalized.setdefault("member_set_key", member_set_key(member_ids))
    normalized.setdefault(
        "stable_group_key",
        stable_group_key(normalized["discovery_source"], normalized["member_set_key"]),
    )
    primary_id = (
        UUID(normalized["keeper_asset_id"])
        if normalized.get("keeper_asset_id") is not None
        else None
    )
    action = normalized["action"]
    if action not in {"resolve", "keep_all", "stack_all", "mixed"}:
        action = "mixed"
        normalized["action"] = action
    normalized.setdefault(
        "keep_asset_ids",
        (
            [str(primary_id)]
            if action == "resolve" and primary_id is not None
            else [str(asset_id) for asset_id in member_ids]
            if action in {"keep_all", "stack_all"}
            else []
        ),
    )
    normalized.setdefault(
        "follow_up",
        {
            "type": "stack",
            "primary_asset_id": str(primary_id),
            "member_asset_ids": [str(asset_id) for asset_id in member_ids],
        }
        if action == "stack_all" and primary_id is not None
        else None,
    )
    if normalized["follow_up"] is not None:
        normalized["follow_up"].setdefault("resolution", "move_selected")
    normalized.setdefault("execution_state", "pending")
    normalized.setdefault("metadata_work", None)
    normalized.setdefault("member_fingerprint", _member_fingerprint(member_ids))
    if "members" not in normalized:
        keep_ids = {UUID(value) for value in normalized.get("keep_asset_ids", [])}
        trash_ids = {UUID(value) for value in normalized.get("trash_asset_ids", [])}
        stack_ids = {
            UUID(value) for value in (normalized.get("follow_up") or {}).get("member_asset_ids", [])
        }
        normalized["members"] = [
            {
                "asset_id": str(asset_id),
                "disposition": (
                    "delete"
                    if asset_id in trash_ids
                    else "stack"
                    if asset_id in stack_ids
                    else "keep"
                    if asset_id in keep_ids
                    else "no_change"
                ),
                "primary": asset_id == primary_id,
            }
            for asset_id in member_ids
        ]
    return normalized


def _public_plan(record: ActionPlanRecord) -> DuplicateResolutionPlan:
    groups = [
        DuplicateResolutionPlanGroup.model_validate(_normalize_plan_group(item))
        for item in record.relation_work.get("groups", [])
    ]
    return DuplicateResolutionPlan(
        id=record.id,
        status=record.status,
        groups=groups,
        group_count=len(groups),
        resolve_group_count=sum(group.action == "resolve" for group in groups),
        keep_all_group_count=sum(group.action == "keep_all" for group in groups),
        stack_group_count=sum(group.follow_up is not None for group in groups),
        mixed_group_count=sum(group.action == "mixed" for group in groups),
        trash_asset_count=sum(len(group.trash_asset_ids) for group in groups),
        retained_asset_count=sum(
            member.disposition in {"keep", "stack"} for group in groups for member in group.members
        ),
        zero_survivor_group_count=sum(not group.keep_asset_ids for group in groups),
        expires_at=record.expires_at,
        destructive=getattr(record, "destructive", True),
    )






class CrossSourceDuplicateTaskHandler:
    """Verify originals and populate preservation evidence for discovered groups."""

    task_type = CROSS_SOURCE_DUPLICATE_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
        integrity: IntegrityTaskHandler,
        *,
        include_preservation: bool = False,
        discovery: GroupDiscoveryProvider | None = None,
        similarity_indexer: SimilarityIndexMaintainer | None = None,
        shared_original_cache_path: Path | None = None,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._integrity = integrity
        self._include_preservation = include_preservation
        self._discovery = discovery or ImmichDuplicateProvider(immich)
        self._similarity_indexer = similarity_indexer
        self._shared_original_cache_path = shared_original_cache_path

    async def _download_shared_original(
        self,
        context: TaskContext,
        asset: ImmichAsset,
    ) -> tuple[Path, int]:
        """Acquire one caller-owned original for all stale evidence branches."""

        suffix = Path(asset.original_file_name or "").suffix.lower()
        if not suffix or len(suffix) > 16 or any(character in suffix for character in "/\\"):
            suffix = ".img"
        temporary_path: Path | None = None
        total = 0
        try:
            with NamedTemporaryFile(
                prefix="immich-companion-shared-original-",
                suffix=suffix,
                dir=self._shared_original_cache_path,
                delete=False,
            ) as prepared:
                temporary_path = Path(prepared.name)
                async with self._immich.stream_original(
                    asset.id,
                    chunk_size=INTEGRITY_CHUNK_SIZE,
                ) as original:
                    expected_stream_bytes = original.content_length
                    async for chunk in original.chunks:
                        await context.ensure_active()
                        prepared.write(chunk)
                        total += len(chunk)
            if expected_stream_bytes is not None and total != expected_stream_bytes:
                raise RetryableTaskError(
                    "The shared original stream ended before its declared content length."
                )
            if asset.file_size_bytes is not None and total != asset.file_size_bytes:
                raise RetryableTaskError(
                    "The shared original size did not match synchronized Immich metadata."
                )
            assert temporary_path is not None
            return temporary_path, total
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        options = DuplicateAnalysisOptions.model_validate(payload)
        batch_reader = getattr(self._discovery, "discover_batches", None)

        async def discovery_batches():
            if callable(batch_reader):
                async for batch in batch_reader():
                    yield batch
                return
            yield await self._discovery.discover()

        group_count = 0
        candidate_file_count = 0
        files_attempted = 0
        unavailable = 0
        visual_assets = 0
        visual_unavailable = 0
        shared_original_downloads = 0
        shared_original_bytes = 0
        processed_asset_ids: set[UUID] = set()

        await context.checkpoint(
            checkpoint={"phase": "fingerprinting"},
            counters={
                "files_attempted": 0,
                "files_unavailable": 0,
                "visual_assets": 0,
                "visual_unavailable": 0,
                "shared_original_downloads": 0,
                "shared_original_bytes": 0,
            },
            progress={
                "phase": "duplicate_fingerprints",
                "completed": 0,
                "total": None,
                "percent": None,
                "detail": "Streaming exact duplicate groups for verification…",
            },
        )
        share_capable = bool(
            self._similarity_indexer is not None
            and callable(getattr(self._similarity_indexer, "has_current", None))
        )
        async for groups in discovery_batches():
            group_count += len(groups)
            candidates: dict[UUID, ImmichAsset] = {}
            for group in groups:
                for asset in group.assets:
                    if asset.id in processed_asset_ids:
                        continue
                    if (
                        asset.library_id is not None
                        or options.verify_upload_streams
                        or self._include_preservation
                        and asset.asset_type == "IMAGE"
                    ):
                        if asset.file_size_bytes is None:
                            asset = await self._immich.get_asset(asset.id)
                        candidates[asset.id] = asset
                        processed_asset_ids.add(asset.id)

            candidate_file_count += len(candidates)
            if not candidates:
                continue
            reports = await self._reports.get_many(list(candidates))
            features = (
                await self._reports.get_preservation_features(list(candidates))
                if self._include_preservation
                else {}
            )
            pending = [
                asset
                for asset in candidates.values()
                if not asset.is_offline
                and (
                    (
                        (
                            asset.library_id is None
                            and options.verify_upload_streams
                            or asset.library_id is not None
                        )
                        and report_freshness(reports.get(asset.id), asset) != "current"
                    )
                    or (
                        self._include_preservation
                        and asset.asset_type == "IMAGE"
                        and preservation_feature_freshness(features.get(asset.id), asset)
                        != "current"
                    )
                )
            ]
            visual_candidates = [
                asset
                for asset in candidates.values()
                if asset.asset_type == "IMAGE" and not asset.is_offline
            ]
            visual_assets += len(visual_candidates)
            pending_ids = {asset.id for asset in pending}
            visual_pending_ids: set[UUID] = set()

            if self._similarity_indexer is not None:
                if share_capable:
                    for asset in visual_candidates:
                        await context.ensure_active()
                        if not await self._similarity_indexer.has_current(asset.id):
                            visual_pending_ids.add(asset.id)
                    for asset in visual_candidates:
                        if asset.id not in visual_pending_ids or asset.id in pending_ids:
                            continue
                        await context.ensure_active()
                        if not await self._similarity_indexer.ensure_asset(context, asset.id):
                            visual_unavailable += 1
                            logger.warning(
                                "Duplicate candidate visual evidence unavailable: "
                                "asset_id=%s filename=%s",
                                asset.id,
                                asset.original_file_name,
                            )
                else:
                    for asset in visual_candidates:
                        await context.ensure_active()
                        if not await self._similarity_indexer.ensure_asset(context, asset.id):
                            visual_unavailable += 1
                            logger.warning(
                                "Duplicate candidate visual evidence unavailable: "
                                "asset_id=%s filename=%s",
                                asset.id,
                                asset.original_file_name,
                            )

            for asset in pending:
                await context.ensure_active()
                files_attempted += 1
                await self._assets.refresh_asset(asset)
                appearance_needed = share_capable and asset.id in visual_pending_ids
                prepared_path: Path | None = None
                prepared_bytes: int | None = None
                shared_failed = False
                if appearance_needed:
                    try:
                        prepared_path, prepared_bytes = await self._download_shared_original(
                            context,
                            asset,
                        )
                        shared_original_downloads += 1
                        shared_original_bytes += prepared_bytes
                    except (ImmichApiError, OSError, RetryableTaskError) as error:
                        shared_failed = True
                        logger.warning(
                            "Shared duplicate original acquisition failed; falling back "
                            "to independent evidence paths: asset_id=%s filename=%s "
                            "error_type=%s reason=%s",
                            asset.id,
                            asset.original_file_name,
                            type(error).__name__,
                            error,
                        )

                try:
                    if appearance_needed and self._similarity_indexer is not None:
                        visual_ready = await self._similarity_indexer.ensure_asset(
                            context,
                            asset.id,
                            source=asset,
                            original_path=None if shared_failed else prepared_path,
                            original_source_bytes=None if shared_failed else prepared_bytes,
                        )
                        if not visual_ready:
                            visual_unavailable += 1
                            logger.warning(
                                "Duplicate candidate visual evidence unavailable: "
                                "asset_id=%s filename=%s",
                                asset.id,
                                asset.original_file_name,
                            )

                    try:
                        if prepared_path is not None and not shared_failed:
                            await self._integrity.analyze(
                                context,
                                asset.id,
                                publish_progress=False,
                                source=asset,
                                original_path=prepared_path,
                                original_source_bytes=prepared_bytes,
                            )
                        else:
                            await self._integrity.analyze(
                                context,
                                asset.id,
                                publish_progress=False,
                                source=asset,
                            )
                    except (PermanentTaskError, RetryableTaskError, ImmichApiError) as error:
                        unavailable += 1
                        logger.warning(
                            "Duplicate candidate verification failed: asset_id=%s filename=%s "
                            "source=%s error_type=%s reason=%s",
                            asset.id,
                            asset.original_file_name,
                            "upload" if asset.library_id is None else "external",
                            type(error).__name__,
                            error,
                        )
                finally:
                    if prepared_path is not None:
                        prepared_path.unlink(missing_ok=True)

                await context.checkpoint(
                    checkpoint={"phase": "fingerprinting", "asset_id": str(asset.id)},
                    counters={
                        "files_attempted": files_attempted,
                        "files_unavailable": unavailable,
                        "visual_assets": visual_assets,
                        "visual_unavailable": visual_unavailable,
                        "shared_original_downloads": shared_original_downloads,
                        "shared_original_bytes": shared_original_bytes,
                    },
                    progress={
                        "phase": "duplicate_fingerprints",
                        "completed": files_attempted,
                        "total": None,
                        "percent": None,
                        "detail": (
                            f"Verified {files_attempted} exact duplicate candidate files"
                        ),
                    },
                )

        if unavailable:
            logger.warning(
                "Duplicate candidate verification completed with unavailable files: "
                "attempted=%s unavailable=%s",
                files_attempted,
                unavailable,
            )
        await context.checkpoint(
            checkpoint={"phase": "complete"},
            counters={
                "files_attempted": files_attempted,
                "files_unavailable": unavailable,
                "visual_assets": visual_assets,
                "visual_unavailable": visual_unavailable,
                "shared_original_downloads": shared_original_downloads,
                "shared_original_bytes": shared_original_bytes,
            },
            progress={
                "phase": "complete",
                "completed": files_attempted,
                "total": files_attempted,
                "percent": 100.0,
                "detail": "Exact duplicate candidate verification is ready.",
            },
        )
        return TaskResult(
            summary={"duplicate_group_count": group_count},
            counters={
                "duplicate_groups": group_count,
                "candidate_files": candidate_file_count,
                "files_attempted": files_attempted,
                "files_unavailable": unavailable,
                "visual_assets": visual_assets,
                "visual_unavailable": visual_unavailable,
                "shared_original_downloads": shared_original_downloads,
                "shared_original_bytes": shared_original_bytes,
            },
        )

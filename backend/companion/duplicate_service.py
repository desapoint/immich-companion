"""Immich-driven exact duplicate review and bounded batch resolution."""

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


from companion.duplicate_evidence import DuplicateEvidenceMixin
from companion.duplicate_review import DuplicateReviewMixin
from companion.duplicate_resolution import DuplicateResolutionMixin


class CrossSourceDuplicateService(
    DuplicateEvidenceMixin,
    DuplicateReviewMixin,
    DuplicateResolutionMixin,
):
    """Read live groups, join cached verification, and manage reviewed plans."""

    def __init__(
        self,
        settings: Settings,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
        actions: ActionRepository,
        tasks: TaskCoordinator,
        runtime_sync_settings: object,
        reviews: DuplicateReviewRepository | None = None,
        policy: DuplicatePolicyRepository | None = None,
        similarity: SimilarityRepository | None = None,
        discovery: GroupDiscoveryProvider | None = None,
        stacks: StackService | None = None,
        search_features: SimilaritySearchRepository | None = None,
        scan_evidence: SimilarityScanRepository | None = None,
    ) -> None:
        self._settings = settings
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._actions = actions
        self._tasks = tasks
        self._runtime_sync_settings = runtime_sync_settings
        self._reviews = reviews
        self._policy = policy
        self._similarity = similarity
        self._search_features = search_features
        self._scan_evidence = scan_evidence
        self._discovery = discovery or ImmichDuplicateProvider(immich)
        self._stacks = stacks

    async def _options(
        self,
        options: DuplicateAnalysisOptions | None,
    ) -> DuplicateAnalysisOptions:
        if options is not None or self._policy is None:
            return options or DuplicateAnalysisOptions()
        return (await self._policy.get()).analysis_options()

    async def start(
        self,
        options: DuplicateAnalysisOptions,
    ) -> CrossSourceDuplicateTaskStart:
        key = _options_key(options)
        active = await self._tasks.find_active(CROSS_SOURCE_DUPLICATE_TASK_TYPE, key)
        if active is None:
            active = await self._tasks.submit(
                CROSS_SOURCE_DUPLICATE_TASK_TYPE,
                options.model_dump(mode="json"),
                priority=50,
                lane_key=INTEGRITY_TASK_TYPE,
                deduplication_key=key,
            )
            await self._tasks.start()
        return CrossSourceDuplicateTaskStart(task_id=active.id)

    async def _relation_snapshot(
        self,
        member_ids: set[UUID],
    ) -> tuple[dict[UUID, tuple[set[UUID], set[UUID]]], str]:
        relations: dict[UUID, tuple[set[UUID], set[UUID]]] = {}
        serialized: dict[str, dict[str, list[str]]] = {}
        for member_id in sorted(member_ids):
            summary = await self._assets.get_asset_summary(member_id)
            albums = {album.id for album in summary.albums} if summary is not None else set()
            tags = {UUID(str(tag.id)) for tag in summary.tags} if summary is not None else set()
            relations[member_id] = (albums, tags)
            serialized[str(member_id)] = {
                "album_ids": sorted(str(identifier) for identifier in albums),
                "tag_ids": sorted(str(identifier) for identifier in tags),
            }
        return relations, _stable_fingerprint(serialized)


from companion.duplicate_task_handlers import CrossSourceDuplicateTaskHandler

class DuplicateResolutionTaskHandler:
    """Execute one reviewed duplicate plan in the serialized action lane."""

    task_type = DUPLICATE_RESOLUTION_TASK_TYPE
    lane_key = "asset_action"
    max_concurrency = 1

    def __init__(self, service: CrossSourceDuplicateService) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        return await self._service.execute_plan(context, UUID(str(payload["plan_id"])))

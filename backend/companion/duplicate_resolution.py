"""Duplicate resolution and action orchestration mixin."""

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



from companion.duplicate_service import (
    DUPLICATE_RESOLUTION_TASK_TYPE,
    _contained_native_resolution,
    _metadata_keeper_for_plan,
    _normalize_plan_group,
    _plan_digest,
    _public_plan,
    _reviewed_delete_supported,
)


class DuplicateResolutionMixin:
    """Planning, review-state persistence, and resolution execution."""

    async def plan(self, request: DuplicateResolutionPlanRequest) -> DuplicateResolutionPlan:
        options = await self._options(request.options)
        requested_group_ids = list(dict.fromkeys(request.group_ids))
        if request.workspace_selected:
            requested_group_ids = (await self.workspace(options)).selected_group_ids
            if request.group_ids and set(request.group_ids) != set(requested_group_ids):
                raise ActionPlanConflictError(
                    "The duplicate workspace selection changed before planning"
                )

        if request.all_eligible:
            limit = getattr(self._settings, "action_max_targets", 5000)
            target_ids = await self._matching_group_ids(
                source="both",
                state="actionable",
                limit=limit + 1,
            )
            if len(target_ids) > limit:
                raise ValueError(
                    f"Eligible duplicate planning exceeds the configured {limit} group limit"
                )
        else:
            target_ids = requested_group_ids

        if not target_ids:
            raise ValueError("No duplicate groups were selected")

        batch_size = max(
            1,
            min(250, getattr(self._settings, "sync_batch_size", 250)),
        )
        found_ids: set[str] = set()
        plan_groups: list[dict[str, Any]] = []
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            _, _, _, result = await self._snapshot_groups(discovered, options)
            selected = [
                group
                for group in result.groups
                if (
                    group.auto_resolvable
                    if request.all_eligible
                    else group.group_id in batch_ids
                )
            ]
            found_ids.update(group.group_id for group in selected)

            review_records: dict[tuple[str, str], object] = {}
            if self._reviews is not None:
                for discovery_source in {
                    group.discovery_source for group in selected
                }:
                    source_groups = [
                        group
                        for group in selected
                        if group.discovery_source == discovery_source
                    ]
                    records = await self._reviews.get_many(
                        discovery_source,
                        [group.stable_group_key for group in source_groups],
                    )
                    review_records.update(
                        (
                            (discovery_source, group_key),
                            record,
                        )
                        for group_key, record in records.items()
                    )

            for group in selected:
                member_ids = {member.id for member in group.members}
                record = review_records.get(
                    (group.discovery_source, group.stable_group_key)
                )
                raw_decisions = list(getattr(record, "member_decisions", []) or [])
                draft_dispositions = {
                    UUID(decision["asset_id"]): decision["disposition"]
                    for decision in raw_decisions
                    if isinstance(decision, dict)
                    and decision.get("asset_id")
                    and decision.get("disposition") in {"keep", "delete", "stack"}
                }
                draft_is_current = (
                    record is not None
                    and getattr(record, "member_fingerprint", None)
                    == group.member_fingerprint
                    and set(draft_dispositions) == member_ids
                    and len(draft_dispositions) == len(group.members)
                )
                if raw_decisions and not draft_is_current:
                    raise ActionPlanConflictError(
                        "Every selected duplicate needs a complete current saved draft"
                    )
                if draft_is_current:
                    dispositions = [
                        draft_dispositions[member.id] for member in group.members
                    ]
                    action = _action_for_dispositions(dispositions)
                else:
                    action = request.action_overrides.get(
                        group.group_id,
                        "resolve"
                        if request.all_eligible
                        or group.group_id in request.keeper_overrides
                        else group.effective_action,
                    )
                    if action == "mixed":
                        raise ActionPlanConflictError(
                            "Mixed duplicate choices require a complete current saved draft"
                        )
                    legacy_primary = request.keeper_overrides.get(
                        group.group_id,
                        group.effective_primary_asset_id or group.keeper_asset_id,
                    )
                    dispositions = [
                        item["disposition"]
                        for item in _member_dispositions(
                            action,
                            [member.id for member in group.members],
                            legacy_primary,
                        )
                    ]
                if action == "none":
                    raise ActionPlanConflictError(
                        "Every selected group needs an action"
                    )
                has_deletions = "delete" in dispositions
                if has_deletions and not _reviewed_delete_supported(group):
                    raise ActionPlanConflictError(
                        "Deleting duplicate members requires a current "
                        "multi-member duplicate group"
                    )
                stack_ids = [
                    member.id
                    for member, disposition in zip(
                        group.members,
                        dispositions,
                        strict=True,
                    )
                    if disposition == "stack"
                ]
                if stack_ids and any(
                    member.is_offline
                    for member in group.members
                    if member.id in stack_ids
                ):
                    raise ActionPlanConflictError(
                        "Offline members cannot form a reviewed stack"
                    )
                if len(stack_ids) == 1:
                    raise ActionPlanConflictError(
                        "A stack needs at least two surviving members"
                    )
                keep_ids = [
                    member.id
                    for member, disposition in zip(
                        group.members,
                        dispositions,
                        strict=True,
                    )
                    if disposition in {"keep", "stack"}
                ]
                trash_ids = [
                    member.id
                    for member, disposition in zip(
                        group.members,
                        dispositions,
                        strict=True,
                    )
                    if disposition == "delete"
                ]
                stack_primary_id = (
                    getattr(record, "stack_primary_asset_id", None)
                    if record
                    else None
                )
                stack_resolution = getattr(
                    record,
                    "stack_resolution",
                    "move_selected",
                )
                if stack_ids:
                    if stack_primary_id not in stack_ids:
                        preferred = (
                            group.effective_primary_asset_id
                            or group.keeper_asset_id
                        )
                        stack_primary_id = (
                            preferred if preferred in stack_ids else stack_ids[0]
                        )
                else:
                    stack_primary_id = None
                metadata_keeper_id = _metadata_keeper_for_plan(
                    keep_ids,
                    trash_ids,
                )
                keeper_id = metadata_keeper_id or stack_primary_id
                if action == "resolve" and keeper_id is None:
                    raise ActionPlanConflictError(
                        "A primary asset must be chosen from the group"
                    )
                ordered_keep_ids = (
                    [
                        metadata_keeper_id,
                        *(
                            asset_id
                            for asset_id in keep_ids
                            if asset_id != metadata_keeper_id
                        ),
                    ]
                    if metadata_keeper_id is not None
                    else keep_ids
                )
                ordered_members = (
                    [
                        keeper_id,
                        *(
                            member.id
                            for member in group.members
                            if member.id != keeper_id
                        ),
                    ]
                    if keeper_id is not None
                    else [member.id for member in group.members]
                )
                metadata_work: dict[str, Any] | None = None
                if metadata_keeper_id is not None and trash_ids:
                    keeper_albums: set[UUID] = set()
                    keeper_tags: set[UUID] = set()
                    trash_albums: set[UUID] = set()
                    trash_tags: set[UUID] = set()
                    relation_snapshot, relation_fingerprint = (
                        await self._relation_snapshot(member_ids)
                    )
                    for member_id, (albums, tags) in relation_snapshot.items():
                        if member_id == metadata_keeper_id:
                            keeper_albums.update(albums)
                            keeper_tags.update(tags)
                        if member_id in trash_ids:
                            trash_albums.update(albums)
                            trash_tags.update(tags)
                    metadata_work = {
                        "keeper_asset_id": str(metadata_keeper_id),
                        "album_ids": [
                            str(identifier)
                            for identifier in sorted(
                                trash_albums - keeper_albums
                            )
                        ],
                        "tag_ids": [
                            str(identifier)
                            for identifier in sorted(
                                trash_tags - keeper_tags
                            )
                        ],
                        "source_fingerprint": relation_fingerprint,
                    }
                stack_source_fingerprint = (
                    _source_fingerprint(
                        [
                            member
                            for member in group.members
                            if member.id in stack_ids
                        ]
                    )
                    if stack_ids
                    else None
                )
                plan_groups.append(
                    {
                        "group_id": group.group_id,
                        "stable_group_key": group.stable_group_key,
                        "member_set_key": group.member_set_key,
                        "discovery_source": group.discovery_source,
                        "provider_group_id": group.provider_group_id,
                        "action": action,
                        "keeper_asset_id": (
                            str(keeper_id) if keeper_id is not None else None
                        ),
                        "member_asset_ids": [
                            str(asset_id) for asset_id in ordered_members
                        ],
                        "keep_asset_ids": [
                            str(asset_id) for asset_id in ordered_keep_ids
                        ],
                        "trash_asset_ids": [
                            str(asset_id) for asset_id in trash_ids
                        ],
                        "metadata_work": metadata_work,
                        "follow_up": (
                            {
                                "type": "stack",
                                "primary_asset_id": str(stack_primary_id),
                                "resolution": stack_resolution,
                                "member_asset_ids": [
                                    str(stack_primary_id),
                                    *(
                                        str(asset_id)
                                        for asset_id in stack_ids
                                        if asset_id != stack_primary_id
                                    ),
                                ],
                                "source_fingerprint": stack_source_fingerprint,
                                "conflict_fingerprint": None,
                            }
                            if stack_primary_id is not None
                            else None
                        ),
                        "execution_state": "pending",
                        "member_fingerprint": group.member_fingerprint,
                        "members": [
                            {
                                "asset_id": str(member.id),
                                "disposition": (
                                    draft_dispositions[member.id]
                                    if draft_is_current
                                    else dispositions[index]
                                ),
                                "primary": member.id
                                in {
                                    stack_primary_id,
                                    metadata_keeper_id,
                                },
                            }
                            for index, member in enumerate(group.members)
                        ],
                    }
                )

        if not plan_groups:
            raise ValueError("No duplicate groups were selected")
        if (
            not request.all_eligible
            and found_ids != set(requested_group_ids)
        ):
            raise ActionPlanConflictError(
                "A selected duplicate group is no longer available"
            )

        stack_plan_groups = [
            planned
            for planned in plan_groups
            if planned["follow_up"] is not None
        ]
        if stack_plan_groups and self._stacks is not None:
            stack_snapshot = await self._stacks.stack_snapshot()
            for planned in stack_plan_groups:
                follow_up = planned["follow_up"]
                member_ids = [
                    UUID(value) for value in follow_up["member_asset_ids"]
                ]
                follow_up["conflict_fingerprint"] = _stable_fingerprint(
                    self._stacks.select_conflict_snapshot(
                        member_ids,
                        stack_snapshot,
                    )
                )
        plan_groups.sort(key=lambda item: item["group_id"])
        record = await self._actions.create_duplicate_plan(
            groups=plan_groups,
            options=request.options.model_dump(mode="json"),
            target_digest=_plan_digest(plan_groups),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=self._settings.action_plan_ttl_seconds),
        )
        return _public_plan(record)

    async def start_resolution(
        self,
        request: DuplicateResolutionExecuteRequest,
    ) -> CrossSourceDuplicateTaskStart:
        record = await self._actions.get_plan(request.plan_id)
        if record is None or record.action != "resolve_duplicates":
            raise ActionPlanNotFoundError("Duplicate resolution plan was not found")
        resuming_follow_up = record.status == "failed"
        if record.status == "failed":
            record = await self._actions.reopen_duplicate_follow_up(record.id)
            if record is None:
                raise ActionPlanConflictError(
                    "This failed plan has no compatible incomplete work to resume"
                )
        if record.status != "planned":
            raise ActionPlanConflictError("Duplicate resolution plan has already been used")
        if not resuming_follow_up and record.expires_at <= datetime.now(UTC):
            await self._actions.finish_plan(record.id, "expired", {"error": "expired"})
            raise ActionPlanConflictError("Duplicate resolution plan has expired")
        if record.destructive and not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError("Duplicate resolution is disabled in safe mode")
        task = await self._tasks.submit(
            DUPLICATE_RESOLUTION_TASK_TYPE,
            {"plan_id": str(record.id)},
            priority=90,
            lane_key="asset_action",
            deduplication_key=f"duplicate-plan:{record.id}",
        )
        await self._tasks.start()
        return CrossSourceDuplicateTaskStart(task_id=task.id)

    async def execute_plan(self, context: TaskContext, plan_id: UUID) -> TaskResult:
        action_started = perf_counter()
        existing = await self._actions.get_plan(plan_id)
        if existing is None or existing.action != "resolve_duplicates":
            raise PermanentTaskError("Duplicate resolution plan was not found")
        if existing.status not in {"planned", "running"}:
            raise PermanentTaskError("Duplicate resolution plan has already been used")
        if existing.destructive and not self._settings.allow_destructive_actions:
            raise PermanentTaskError("Duplicate resolution is disabled in safe mode")

        persisted_groups = existing.relation_work.get("groups", [])
        target_digest = getattr(existing, "target_digest", None)
        if target_digest is not None and (
            not isinstance(persisted_groups, list)
            or _plan_digest(persisted_groups) != target_digest
        ):
            result = {
                "error": "plan_fingerprint_mismatch",
                "group_count": 0,
                "processed_group_count": 0,
                "resolved_group_count": 0,
                "kept_all_group_count": 0,
                "zero_survivor_group_count": 0,
                "stacked_group_count": 0,
                "failed_group_ids": [],
                "drifted_group_ids": [],
                "follow_up_pending_group_ids": [],
                "trashed_asset_count": 0,
                "verified": False,
            }
            await self._actions.finish_plan(plan_id, "drifted", result)
            return TaskResult(
                status="failed",
                summary=result,
                counters={
                    "groups_processed": 0,
                    "groups_resolved": 0,
                    "groups_kept_all": 0,
                    "groups_zero_survivor": 0,
                    "groups_stacked": 0,
                    "groups_failed": 0,
                    "assets_trashed": 0,
                },
            )
        raw_groups = [_normalize_plan_group(item) for item in persisted_groups]
        options = DuplicateAnalysisOptions.model_validate(existing.relation_work.get("options", {}))
        stored_execution = dict(
            (getattr(existing, "result", None) or {}).get("group_execution") or {}
        )
        def execution_state(planned: dict[str, Any]) -> str:
            stored = stored_execution.get(planned["group_id"])
            if isinstance(stored, dict) and isinstance(stored.get("state"), str):
                return stored["state"]
            return planned.get("execution_state", "pending")

        failed_ids: list[str] = []
        drifted_ids: list[str] = []
        trashed_ids: list[UUID] = []
        pending_resolution = [
            planned for planned in raw_groups if execution_state(planned) == "pending"
        ]
        if pending_resolution:
            stable_keys = [planned["stable_group_key"] for planned in pending_resolution]
            identities = await self._group_identities(stable_group_keys=stable_keys)
            discovered = await self._groups_by_ids(
                [identity.group_id for identity in identities]
            )
            _, _, _, live_result = await self._snapshot_groups(discovered, options)
            reviewed = {group.stable_group_key: group for group in live_result.groups}
        else:
            reviewed = {}
        preflight_ready: list[dict[str, Any]] = []
        for planned in pending_resolution:
            live_group = reviewed.get(planned["stable_group_key"])
            planned_members = {UUID(value) for value in planned["member_asset_ids"]}
            has_deletions = bool(planned.get("trash_asset_ids"))
            if (
                live_group is None
                or {asset.id for asset in live_group.members} != planned_members
                or live_group.member_fingerprint != planned["member_fingerprint"]
                or (
                    has_deletions
                    and not _reviewed_delete_supported(live_group)
                )
                or (
                    planned.get("follow_up") is not None
                    and any(
                        member.is_offline
                        for member in live_group.members
                        if str(member.id) in planned["follow_up"]["member_asset_ids"]
                    )
                )
            ):
                identifier = planned["group_id"]
                failed_ids.append(identifier)
                drifted_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "drifted",
                    "error": "group_drift",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "drifted",
                    error="group_drift",
                )
            else:
                planned["provider_group_id"] = live_group.provider_group_id
                preflight_ready.append(planned)
        pending_resolution = preflight_ready
        preflight_done = perf_counter()

        if existing.status == "planned":
            claimed = await self._actions.claim_plan(plan_id)
            if claimed is None:
                raise PermanentTaskError("Duplicate resolution plan has already been used")

        pacing = await self._runtime_sync_settings.get()
        batch_size = pacing.full_batch_size
        total_steps = len(raw_groups) + sum(
            planned.get("follow_up") is not None for planned in raw_groups
        )
        completed_steps = sum(
            2
            if execution_state(planned) == "completed" and planned.get("follow_up") is not None
            else 1
            if execution_state(planned) in {"follow_up_pending", "completed"}
            else 0
            for planned in raw_groups
        )
        resolved_ids: set[str] = {
            planned["group_id"]
            for planned in raw_groups
            if execution_state(planned) in {"duplicate_resolved", "follow_up_pending", "completed"}
        }

        async def checkpoint(detail: str) -> None:
            successful = sum(execution_state(planned) == "completed" for planned in raw_groups)
            await context.checkpoint(
                checkpoint={"phase": "processing", "steps_completed": completed_steps},
                counters={
                    "groups_completed": successful,
                    "groups_failed": len(failed_ids),
                },
                progress={
                    "phase": "duplicate_resolution",
                    "completed": completed_steps,
                    "total": total_steps,
                    "percent": round(completed_steps / total_steps * 100, 1),
                    "detail": detail,
                },
            )

        metadata_ready: list[dict[str, Any]] = []
        for planned in pending_resolution:
            metadata_work = planned.get("metadata_work")
            if metadata_work is None:
                metadata_ready.append(planned)
                continue
            identifier = planned["group_id"]
            keeper_asset_id = UUID(metadata_work["keeper_asset_id"])
            try:
                expected_fingerprint = metadata_work.get("source_fingerprint")
                if expected_fingerprint is not None:
                    _, current_fingerprint = await self._relation_snapshot(
                        {UUID(value) for value in planned["member_asset_ids"]}
                    )
                    if current_fingerprint != expected_fingerprint:
                        raise ActionPlanConflictError(
                            "Duplicate metadata inputs changed after review"
                        )
                for album_id in metadata_work.get("album_ids", []):
                    await self._immich.add_assets_to_album(
                        UUID(album_id),
                        [keeper_asset_id],
                    )
                for tag_id in metadata_work.get("tag_ids", []):
                    await self._immich.add_assets_to_tag(
                        UUID(tag_id),
                        [keeper_asset_id],
                    )
            except ActionPlanConflictError:
                failed_ids.append(identifier)
                drifted_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "drifted",
                    "error": "metadata_input_drift",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "drifted",
                    error="metadata_input_drift",
                )
            except ImmichApiError:
                failed_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "failed",
                    "error": "metadata_reconciliation_failed",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "failed",
                    error="metadata_reconciliation_failed",
                )
            else:
                metadata_ready.append(planned)
        pending_resolution = metadata_ready
        metadata_done = perf_counter()

        action_batches = [
            pending_resolution[offset : offset + batch_size]
            for offset in range(0, len(pending_resolution), batch_size)
        ]
        for batch_index, batch in enumerate(action_batches):
            await context.ensure_active()
            for planned in batch:
                identifier = planned["group_id"]
                group_trash_ids = [
                    UUID(value) for value in planned.get("trash_asset_ids", [])
                ]
                try:
                    if group_trash_ids:
                        try:
                            native_resolution = _contained_native_resolution(planned)
                        except (TypeError, ValueError) as error:
                            raise ImmichApiError("resolve contained duplicate group") from error
                        if native_resolution is not None:
                            await self._immich.resolve_duplicate_groups([native_resolution])
                        else:
                            await self._immich.trash_assets(group_trash_ids)
                        refreshed = [
                            await self._immich.get_asset(asset_id)
                            for asset_id in group_trash_ids
                        ]
                        if any(not asset.is_trashed for asset in refreshed):
                            raise ImmichApiError("verify trashed duplicate members")
                except ImmichApiError:
                    if identifier not in failed_ids:
                        failed_ids.append(identifier)
                    stored_execution[identifier] = {
                        "state": "failed",
                        "error": "duplicate_member_trash_failed",
                    }
                    await self._actions.record_duplicate_group_execution(
                        plan_id,
                        identifier,
                        "failed",
                        error="duplicate_member_trash_failed",
                    )
                    continue

                resolved_ids.add(identifier)
                trashed_ids.extend(group_trash_ids)
                state = (
                    "follow_up_pending"
                    if planned.get("follow_up") is not None
                    else "completed"
                )
                stored_execution[identifier] = {"state": state, "error": None}
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    state,
                )
                completed_steps += 1

            await checkpoint("Applied reviewed duplicate member actions.")
            if batch_index + 1 < len(action_batches):
                await asyncio.sleep(pacing.full_min_batch_delay_seconds)

        if trashed_ids:
            await self._assets.remove_assets(trashed_ids)

        resolution_done = perf_counter()

        stack_groups = [item for item in raw_groups if execution_state(item) == "follow_up_pending"]
        for planned in stack_groups:
            await context.ensure_active()
            identifier = planned["group_id"]
            try:
                follow_up = planned["follow_up"]
                member_ids = [UUID(value) for value in follow_up["member_asset_ids"]]
                refreshed_assets: list[ImmichAsset] = []
                for asset_id in member_ids:
                    asset = await self._immich.get_asset(asset_id)
                    refreshed_assets.append(asset)
                expected_source = follow_up.get("source_fingerprint")
                if (
                    expected_source is not None
                    and _source_fingerprint(refreshed_assets) != expected_source
                ):
                    raise ActionPlanConflictError("Stack member files changed after review")
                expected_conflicts = follow_up.get("conflict_fingerprint")
                if expected_conflicts is not None and (
                    self._stacks is None
                    or _stable_fingerprint(await self._stacks.conflict_snapshot(member_ids))
                    != expected_conflicts
                ):
                    raise ActionPlanConflictError("Existing stack memberships changed after review")
                stack_ids = {
                    str(asset.stack.get("id"))
                    for asset in refreshed_assets
                    if asset.stack is not None and asset.stack.get("id") is not None
                }
                existing_stack_complete = (
                    bool(stack_ids)
                    and len(stack_ids) == 1
                    and all(asset.stack is not None for asset in refreshed_assets)
                )
                if not existing_stack_complete:
                    if self._stacks is None:
                        raise StackSelectionError("Shared stack execution is unavailable")
                    preparation = await self._stacks.prepare(
                        member_ids,
                        follow_up.get("resolution", "move_selected"),
                        UUID(follow_up["primary_asset_id"]),
                    )
                    if not await self._stacks.execute(preparation):
                        raise ImmichApiError("verify created stack")
                    refreshed_assets = [
                        await self._immich.get_asset(asset_id) for asset_id in member_ids
                    ]
                if (
                    any(asset.stack is None for asset in refreshed_assets)
                    or len(
                        {
                            str(asset.stack.get("id"))
                            for asset in refreshed_assets
                            if asset.stack is not None
                        }
                    )
                    != 1
                ):
                    raise ImmichApiError("verify created stack")
                for asset in refreshed_assets:
                    await self._assets.refresh_asset(asset)
            except ActionPlanConflictError:
                if identifier not in failed_ids:
                    failed_ids.append(identifier)
                if identifier not in drifted_ids:
                    drifted_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "drifted",
                    "error": "stack_input_drift",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "drifted",
                    error="stack_input_drift",
                )
            except (ImmichApiError, StackSelectionError):
                if identifier not in failed_ids:
                    failed_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "follow_up_pending",
                    "error": "stack_follow_up_failed",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "follow_up_pending",
                    error="stack_follow_up_failed",
                )
            else:
                stored_execution[identifier] = {"state": "completed", "error": None}
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "completed",
                )
                completed_steps += 1
            await checkpoint("Completing post-resolution Immich stacks…")

        successful_ids = {
            planned["group_id"] for planned in raw_groups if execution_state(planned) == "completed"
        }
        kept_ids = {
            planned["group_id"]
            for planned in raw_groups
            if planned["action"] == "keep_all" and planned["group_id"] in successful_ids
        }
        zero_survivor_ids = {
            planned["group_id"]
            for planned in raw_groups
            if not planned.get("keep_asset_ids") and planned["group_id"] in successful_ids
        }
        stacked_ids = {
            planned["group_id"]
            for planned in raw_groups
            if planned.get("follow_up") is not None and planned["group_id"] in successful_ids
        }

        if self._reviews is not None:
            review_statuses = {
                "resolve": "reviewed_resolve",
                "keep_all": "reviewed_keep_all",
                "stack_all": "reviewed_stack_all",
                "mixed": "reviewed_mixed",
            }
            for planned in raw_groups:
                if planned["group_id"] not in successful_ids:
                    continue
                await self._reviews.save(
                    discovery_source=planned["discovery_source"],
                    provider_group_id=planned.get("provider_group_id") or planned["group_id"],
                    stable_group_key=planned["stable_group_key"],
                    member_set_key=planned["member_set_key"],
                    member_fingerprint=planned["member_fingerprint"],
                    manual_action=planned["action"],
                    manual_primary_asset_id=(
                        UUID(planned["keeper_asset_id"])
                        if planned.get("keeper_asset_id") is not None
                        else None
                    ),
                    review_status=review_statuses[planned["action"]],
                )
                await self._reviews.complete_draft(
                    planned["discovery_source"],
                    planned["stable_group_key"],
                    planned["member_fingerprint"],
                )
            await self._reviews.consume_workspace_groups(
                [
                    planned["stable_group_key"]
                    for planned in raw_groups
                    if planned["group_id"] in successful_ids
                ],
                list(successful_ids),
            )

        status = "completed" if not failed_ids else "failed"
        follow_up_pending_ids = [
            planned["group_id"]
            for planned in raw_groups
            if execution_state(planned) == "follow_up_pending"
        ]
        result = {
            "group_count": len(raw_groups),
            "processed_group_count": len(successful_ids),
            "resolved_group_count": len(resolved_ids),
            "kept_all_group_count": len(kept_ids),
            "zero_survivor_group_count": len(zero_survivor_ids),
            "stacked_group_count": len(stacked_ids),
            "failed_group_ids": failed_ids,
            "drifted_group_ids": drifted_ids,
            "follow_up_pending_group_ids": follow_up_pending_ids,
            "trashed_asset_count": len(trashed_ids),
            "verified": not failed_ids,
        }
        await self._actions.finish_plan(plan_id, status, result)
        logger.info(
            "Duplicate action timing: groups=%s resolved=%s failed=%s "
            "preflight_seconds=%.3f metadata_seconds=%.3f "
            "immich_resolution_seconds=%.3f follow_up_seconds=%.3f total_seconds=%.3f",
            len(raw_groups),
            len(resolved_ids),
            len(failed_ids),
            preflight_done - action_started,
            metadata_done - preflight_done,
            resolution_done - metadata_done,
            perf_counter() - resolution_done,
            perf_counter() - action_started,
        )
        return TaskResult(
            status=status,
            summary=result,
            counters={
                "groups_processed": len(successful_ids),
                "groups_resolved": len(resolved_ids),
                "groups_kept_all": len(kept_ids),
                "groups_zero_survivor": len(zero_survivor_ids),
                "groups_stacked": len(stacked_ids),
                "groups_failed": len(failed_ids),
                "assets_trashed": len(trashed_ids),
            },
        )

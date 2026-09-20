"""Duplicate review state, scoring, and workspace mixin."""

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






class DuplicateReviewMixin:
    """Assemble scored groups and persist review/workspace state."""

    async def _apply_review_states(
        self,
        result: CrossSourceDuplicateResult,
    ) -> CrossSourceDuplicateResult:
        assert self._reviews is not None
        states_by_source: dict[tuple[str, str], Any] = {}
        for discovery_source in {group.discovery_source for group in result.groups}:
            source_groups = [
                group for group in result.groups if group.discovery_source == discovery_source
            ]
            states = await self._reviews.get_many(
                discovery_source,
                [group.stable_group_key for group in source_groups],
            )
            states_by_source.update(
                ((discovery_source, group_key), state) for group_key, state in states.items()
            )
        groups: list[ExactDuplicateGroup] = []
        for group in result.groups:
            state = states_by_source.get((group.discovery_source, group.stable_group_key))
            if state is None:
                groups.append(group)
                continue
            if state.member_fingerprint != group.member_fingerprint:
                groups.append(group.model_copy(update={"review_status": "drifted"}))
                continue
            if state.review_status in COMPLETED_DUPLICATE_REVIEW_STATUSES:
                continue
            manual_action = state.manual_action
            manual_primary = state.manual_primary_asset_id
            effective_action = manual_action or group.recommended_action
            primary_required = effective_action in {"resolve", "stack_all"}
            effective_primary = (
                manual_primary or group.recommended_primary_asset_id
                if effective_action in {"resolve", "stack_all"}
                else None
            )
            groups.append(
                group.model_copy(
                    update={
                        "manual_action": manual_action,
                        "manual_primary_asset_id": manual_primary,
                        "effective_action": effective_action,
                        "effective_primary_asset_id": effective_primary,
                        "action_source": (
                            "manual" if manual_action is not None else group.action_source
                        ),
                        "primary_source": (
                            "manual"
                            if primary_required and manual_primary is not None
                            else group.primary_source
                            if effective_primary is not None
                            else "none"
                        ),
                        "review_status": state.review_status,
                    }
                )
            )
        counts = {
            name: sum(group.status == name for group in groups)
            for name in ("exact", "unverified", "mismatch", "ineligible")
        }
        return result.model_copy(
            update={
                "groups": groups,
                "group_count": len(groups),
                "exact_group_count": counts["exact"],
                "unverified_group_count": counts["unverified"],
                "mismatch_group_count": counts["mismatch"],
                "ineligible_group_count": counts["ineligible"],
            }
        )

    @staticmethod
    def _verification_candidates(
        groups: list[DiscoveredGroup],
        options: DuplicateAnalysisOptions,
        *,
        include_preservation: bool = False,
    ) -> list[ImmichAsset]:
        candidates = {
            asset.id: asset
            for group in groups
            for asset in group.assets
            if not asset.is_offline
            and (
                asset.library_id is not None
                or options.verify_upload_streams
                or include_preservation
                and asset.asset_type == "IMAGE"
            )
        }
        return list(candidates.values())

    @classmethod
    def _pending_verification(
        cls,
        groups: list[DiscoveredGroup],
        reports: dict[UUID, AssetIntegrityReportRecord],
        features: dict[UUID, AssetImagePreservationFeatureRecord],
        options: DuplicateAnalysisOptions,
        *,
        include_preservation: bool = False,
    ) -> list[ImmichAsset]:
        return [
            asset
            for asset in cls._verification_candidates(
                groups,
                options,
                include_preservation=include_preservation,
            )
            if (
                (asset.library_id is not None or options.verify_upload_streams)
                and report_freshness(reports.get(asset.id), asset) != "current"
            )
            or (
                include_preservation
                and asset.asset_type == "IMAGE"
                and preservation_feature_freshness(features.get(asset.id), asset) != "current"
            )
        ]

    @staticmethod
    def _recommended_disposition(
        action: str,
        asset_id: UUID,
        primary_asset_id: UUID | None,
        *,
        auto_resolvable: bool,
    ) -> str | None:
        if not auto_resolvable:
            return None
        if action == "resolve":
            return "keep" if asset_id == primary_asset_id else "delete"
        if action == "keep_all":
            return "keep"
        if action == "stack_all":
            return "stack"
        return None

    @staticmethod
    def _member_recommendation_reasons(
        disposition: str | None,
        *,
        primary: bool,
    ) -> list[str]:
        if disposition is None:
            return []
        if disposition == "delete":
            return ["verified_exact_copy"]
        if disposition == "stack":
            return [
                "policy_stack_all",
                *(("recommended_stack_primary",) if primary else ()),
            ]
        return ["recommended_keeper" if primary else "policy_keep_all"]

    @staticmethod
    def assemble(
        groups: list[DiscoveredGroup],
        reports: dict[UUID, AssetIntegrityReportRecord],
        options: DuplicateAnalysisOptions,
        immich: ImmichApiClient | None = None,
    ) -> CrossSourceDuplicateResult:
        allowed = set(options.external_library_ids)
        public_groups: list[ExactDuplicateGroup] = []
        for group in groups:
            assets = group.assets
            reason: str | None = None
            status = "unverified"
            hashes: dict[UUID, str | None] = {}
            invalid_upload_checksum = False

            if len(assets) < 2:
                reason = "Immich returned fewer than two members."
                status = "ineligible"
            elif any(asset.is_trashed for asset in assets):
                reason = "The group contains a trashed asset."
                status = "ineligible"
            elif any(
                asset.library_id is not None and allowed and asset.library_id not in allowed
                for asset in assets
            ):
                reason = "The group contains an external library excluded by this review."
                status = "ineligible"

            for asset in assets:
                if asset.library_id is None:
                    if options.verify_upload_streams:
                        report = reports.get(asset.id)
                        current = (
                            report is not None and report_freshness(report, asset) == "current"
                        )
                        invalid_upload_checksum = invalid_upload_checksum or bool(
                            current and report.immich_checksum_match is False
                        )
                        hashes[asset.id] = (
                            report.sha1_hex
                            if current and report.immich_checksum_match is True
                            else None
                        )
                    else:
                        digest = decode_immich_sha1(asset.checksum)
                        hashes[asset.id] = digest.hex() if digest is not None else None
                else:
                    report = reports.get(asset.id)
                    hashes[asset.id] = (
                        report.sha1_hex
                        if not asset.is_offline
                        and report is not None
                        and report_freshness(report, asset) == "current"
                        else None
                    )

            known = {value for value in hashes.values() if value is not None}
            if status != "ineligible":
                if any(asset.is_offline for asset in assets):
                    reason = "An original is offline or unavailable."
                elif invalid_upload_checksum:
                    reason = "An upload stream does not match its Immich content checksum."
                elif any(value is None for value in hashes.values()):
                    reason = "Content verification is still required."
                elif len(known) == 1:
                    status = "exact"
                    reason = "Every original has the same content SHA-1."
                else:
                    status = "mismatch"
                    reason = "Immich grouped these assets, but their file contents differ."

            if group.discovery_source is DiscoverySource.COMPANION_SIMILARITY:
                classification = GroupClassification.SIMILAR
            elif status == "exact":
                classification = GroupClassification.EXACT_FILE
            elif status == "mismatch":
                classification = GroupClassification.MISMATCH
            elif status == "ineligible":
                classification = GroupClassification.INELIGIBLE
            elif any(asset.is_offline for asset in assets):
                classification = GroupClassification.UNAVAILABLE
            else:
                classification = GroupClassification.UNVERIFIED
            candidate = CandidateGroup(
                group_id=group.group_id,
                discovery_source=group.discovery_source,
                provider_group_id=group.provider_group_id,
                classification=classification,
                members=tuple(
                    CandidateMember(
                        asset_id=asset.id,
                        source_kind=("upload" if asset.library_id is None else "external"),
                        uploaded_at=asset.created_at,
                        available=not asset.is_offline,
                        library_id=asset.library_id,
                        is_favorite=asset.is_favorite,
                        width=asset.width,
                        height=asset.height,
                        file_size_bytes=asset.file_size_bytes,
                        metadata_richness=sum(
                            value not in (None, "", False, [], {})
                            for value in (asset.exif_info or {}).values()
                        ),
                        captured_at=asset.local_date_time or asset.file_created_at,
                    )
                    for asset in assets
                ),
            )
            decision = decide_group(
                candidate,
                ResolutionPolicy(
                    keeper_preference=options.keeper_policy,
                    source_priority=tuple(options.source_priority),
                    keeper_tiebreakers=tuple(options.keeper_tiebreakers),
                    automatic_handling=options.automatic_handling_enabled,
                    preselect_safe_groups=options.preselect_safe_groups,
                    exact_file_action=options.exact_file_action,
                ),
            )
            reference_hash = (
                hashes.get(decision.recommended_primary_asset_id)
                if decision.recommended_primary_asset_id is not None
                else next((value for value in hashes.values() if value is not None), None)
            )
            members = [
                DuplicateMember(
                    id=asset.id,
                    source_kind="upload" if asset.library_id is None else "external",
                    library_id=asset.library_id,
                    original_file_name=asset.original_file_name,
                    original_mime_type=asset.original_mime_type,
                    file_size_bytes=asset.file_size_bytes,
                    file_modified_at=asset.file_modified_at,
                    uploaded_at=asset.created_at,
                    is_offline=asset.is_offline,
                    is_stacked=asset.stack is not None,
                    immich_url=immich.public_asset_url(asset.id) if immich is not None else None,
                    verification=(
                        "unverified"
                        if hashes.get(asset.id) is None
                        else "matching"
                        if reference_hash is not None and hashes[asset.id] == reference_hash
                        else "mismatch"
                    ),
                    content_checksum=hashes.get(asset.id),
                    evidence=self._member_evidence(
                        asset,
                        reports.get(asset.id),
                    ),
                    recommended_disposition=(
                        disposition := self._recommended_disposition(
                            decision.recommended_action.value,
                            asset.id,
                            decision.recommended_primary_asset_id,
                            auto_resolvable=decision.auto_resolvable,
                        )
                    ),
                    recommendation_reason_codes=(
                        self._member_recommendation_reasons(
                            disposition,
                            primary=asset.id == decision.recommended_primary_asset_id,
                        )
                    ),
                )
                for asset in assets
            ]
            members_key = member_set_key([asset.id for asset in assets])
            group_key = stable_group_key(candidate.discovery_source.value, members_key)
            public_groups.append(
                ExactDuplicateGroup(
                    group_id=candidate.group_id,
                    stable_group_key=group_key,
                    member_set_key=members_key,
                    discovery_source=candidate.discovery_source.value,
                    discovery_sources=[
                        evidence.discovery_source.value for evidence in group.evidence
                    ],
                    discovery_evidence=[
                        {
                            "discovery_source": evidence.discovery_source.value,
                            "provider_group_id": evidence.provider_group_id,
                            "metadata": dict(evidence.metadata),
                        }
                        for evidence in group.evidence
                    ],
                    provider_group_id=group.provider_group_id,
                    discovery_metadata=dict(group.provider_metadata),
                    classification=candidate.classification.value,
                    status=status,
                    reason=reason,
                    keeper_asset_id=decision.recommended_primary_asset_id,
                    recommended_action=decision.recommended_action.value,
                    recommended_primary_asset_id=decision.recommended_primary_asset_id,
                    recommendation_reason_codes=[
                        code.value for code in decision.recommendation_reason_codes
                    ],
                    auto_resolvable=decision.auto_resolvable,
                    auto_selected=decision.auto_selected,
                    action_source=decision.action_source.value,
                    primary_source=decision.primary_source.value,
                    effective_action=decision.recommended_action.value,
                    effective_primary_asset_id=decision.recommended_primary_asset_id,
                    member_fingerprint=_member_fingerprint([asset.id for asset in assets]),
                    members=members,
                    eligible=(
                        status == "exact"
                        and group.discovery_source is not DiscoverySource.COMPANION_SIMILARITY
                    ),
                )
            )

        counts = {
            name: sum(group.status == name for group in public_groups)
            for name in ("exact", "unverified", "mismatch", "ineligible")
        }
        return CrossSourceDuplicateResult(
            generated_at=datetime.now(UTC),
            group_count=len(public_groups),
            exact_group_count=counts["exact"],
            unverified_group_count=counts["unverified"],
            mismatch_group_count=counts["mismatch"],
            ineligible_group_count=counts["ineligible"],
            groups=public_groups,
        )

    @staticmethod
    def _member_evidence(
        asset: ImmichAsset,
        report: AssetIntegrityReportRecord | None,
    ) -> DuplicateMemberEvidence:
        freshness = report_freshness(report, asset)
        if report is None:
            return DuplicateMemberEvidence(analysis_freshness=freshness)
        detected_format = "unknown" if report.detected_format == "other" else report.detected_format
        return DuplicateMemberEvidence(
            analysis_freshness=freshness,
            integrity_status=report.classification,  # type: ignore[arg-type]
            issue_codes=list(report.issues or []),
            detected_format=detected_format,  # type: ignore[arg-type]
            format_matches_declared=report.format_matches_declared,
            decode_supported=report.decode_supported,
            decode_valid=report.decode_valid,
            decoded_width=report.decoded_width,
            decoded_height=report.decoded_height,
            dimensions_match_immich=report.dimensions_match_immich,
        )

    async def save_review(
        self,
        request: DuplicateReviewUpdate,
        options: DuplicateAnalysisOptions | None = None,
    ) -> ExactDuplicateGroup:
        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        resolved_options = await self._options(options)
        discovered = await self._groups_by_ids([request.group_id])
        _, _, _, result = await self._snapshot_groups(discovered, resolved_options)
        group = next(
            (candidate for candidate in result.groups if candidate.group_id == request.group_id),
            None,
        )
        if group is None:
            raise ActionPlanConflictError("The duplicate group is no longer available")
        member_ids = {member.id for member in group.members}
        action = request.manual_action
        primary_id = request.manual_primary_asset_id
        if primary_id is not None and primary_id not in member_ids:
            raise ActionPlanConflictError("The selected primary is not a group member")
        if action == "resolve" and not group.eligible:
            raise ActionPlanConflictError(
                "This duplicate group is not eligible for reviewed resolution"
            )
        if action == "stack_all" and any(
            member.is_offline or member.is_stacked for member in group.members
        ):
            raise ActionPlanConflictError(
                "Offline or already-stacked members cannot form a new stack"
            )
        review_status = (
            "pending"
            if action is None
            else "review_later"
            if action == "none"
            else "manually_configured"
        )
        await self._reviews.save(
            discovery_source=group.discovery_source,
            provider_group_id=group.provider_group_id or group.group_id,
            stable_group_key=group.stable_group_key,
            member_set_key=group.member_set_key,
            member_fingerprint=group.member_fingerprint,
            manual_action=action,
            manual_primary_asset_id=primary_id,
            review_status=review_status,
        )
        refreshed_discovered = await self._groups_by_ids([request.group_id])
        _, _, _, refreshed = await self._snapshot_groups(
            refreshed_discovered,
            resolved_options,
        )
        updated = next(
            (candidate for candidate in refreshed.groups if candidate.group_id == request.group_id),
            None,
        )
        if updated is None:
            raise ActionPlanConflictError("The duplicate group is no longer available")
        return updated

    async def workspace(
        self,
        options: DuplicateAnalysisOptions | None = None,
    ) -> DuplicateWorkspaceState:
        """Restore durable selections/drafts without hydrating the duplicate universe."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        workspace = await self._reviews.get_workspace()
        selected_references = list(getattr(workspace, "selected_groups", []) or [])
        active_reference = getattr(workspace, "active_group", None)
        parsed_references = [
            DuplicateWorkspaceGroupReference.model_validate(raw) for raw in selected_references
        ]
        parsed_active = (
            DuplicateWorkspaceGroupReference.model_validate(active_reference)
            if active_reference
            else None
        )

        list_drafts = getattr(self._reviews, "list_drafts", None)
        if not callable(list_drafts):
            raise RuntimeError(
                "Duplicate workspace restore requires persisted V2 draft storage"
            )
        records = await list_drafts()
        stable_keys = [
            reference.stable_group_key
            or stable_group_key(
                reference.discovery_source,
                reference.member_set_key or reference.member_fingerprint,
            )
            for reference in [
                *parsed_references,
                *([parsed_active] if parsed_active else []),
            ]
        ]
        stable_keys.extend(record.stable_group_key for record in records)
        identities = await self._group_identities(
            stable_group_keys=list(dict.fromkeys(stable_keys))
        )

        def source_value(item: Any) -> str:
            value = item.discovery_source
            return value.value if isinstance(value, DiscoverySource) else str(value)

        groups_by_stable_key = {item.stable_group_key: item for item in identities}
        selected_ids: list[str] = []
        stale_selected: list[DuplicateWorkspaceGroupReference] = []
        for reference in parsed_references:
            reference_key = reference.stable_group_key or stable_group_key(
                reference.discovery_source,
                reference.member_set_key or reference.member_fingerprint,
            )
            current = groups_by_stable_key.get(reference_key)
            if (
                current is not None
                and source_value(current) == reference.discovery_source
                and current.member_fingerprint == reference.member_fingerprint
            ):
                selected_ids.append(current.group_id)
            else:
                stale_selected.append(reference)

        active_group_id = None
        if parsed_active is not None:
            active_key = parsed_active.stable_group_key or stable_group_key(
                parsed_active.discovery_source,
                parsed_active.member_set_key or parsed_active.member_fingerprint,
            )
            current = groups_by_stable_key.get(active_key)
            if (
                current is not None
                and source_value(current) == parsed_active.discovery_source
                and current.member_fingerprint == parsed_active.member_fingerprint
            ):
                active_group_id = current.group_id

        drafts: list[DuplicateGroupDraft] = []
        for record in records:
            current = groups_by_stable_key.get(record.stable_group_key)
            if current is None:
                continue
            record_source = getattr(record, "discovery_source", None)
            if record_source is not None and source_value(current) != record_source:
                continue
            decisions = list(getattr(record, "member_decisions", []) or [])
            if not decisions and not getattr(record, "stack_primary_asset_id", None):
                continue
            drafts.append(
                DuplicateGroupDraft(
                    group_id=current.group_id,
                    discovery_source=source_value(current),
                    member_fingerprint=record.member_fingerprint,
                    decisions=decisions,
                    stack_primary_asset_id=getattr(record, "stack_primary_asset_id", None),
                    stack_resolution=getattr(record, "stack_resolution", "move_selected"),
                    metadata_keeper_asset_id=getattr(record, "metadata_keeper_asset_id", None),
                    status=getattr(record, "draft_status", "pending"),
                    stale=record.member_fingerprint != current.member_fingerprint,
                )
            )
        return DuplicateWorkspaceState(
            initialized=workspace is not None,
            revision=int(getattr(workspace, "revision", 0) or 0),
            selected_count=len(selected_ids),
            selected_group_ids=selected_ids,
            active_group_id=active_group_id,
            stale_selected_groups=stale_selected,
            drafts=drafts,
        )

    async def save_workspace_selection(
        self,
        request: DuplicateWorkspaceSelectionUpdate,
    ) -> DuplicateWorkspaceState:
        """Save persisted group identities without materializing duplicate evidence."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        requested_ids = list(
            dict.fromkeys(
                [
                    *request.selected_group_ids,
                    *([request.active_group_id] if request.active_group_id else []),
                ]
            )
        )
        identities = await self._group_identities(group_ids=requested_ids)
        groups_by_id: dict[str, Any] = {group.group_id: group for group in identities}
        missing = [group_id for group_id in requested_ids if group_id not in groups_by_id]
        if missing:
            raise ActionPlanConflictError("A selected duplicate group is no longer available")

        def reference(group_id: str) -> dict[str, str]:
            group = groups_by_id[group_id]
            source = group.discovery_source
            source_name = source.value if isinstance(source, DiscoverySource) else str(source)
            fingerprint = group.member_fingerprint
            return DuplicateWorkspaceGroupReference(
                group_id=group.group_id,
                discovery_source=source_name,
                member_fingerprint=fingerprint,
                stable_group_key=group.stable_group_key,
                member_set_key=getattr(group, "member_set_key", fingerprint),
            ).model_dump(mode="json")

        try:
            await self._reviews.save_workspace(
                selected_groups=[reference(group_id) for group_id in request.selected_group_ids],
                active_group=(
                    reference(request.active_group_id) if request.active_group_id is not None else None
                ),
                revision=request.revision,
            )
        except ValueError as error:
            # The repository uses ValueError for an optimistic-concurrency miss.
            # Keep that storage detail out of the HTTP layer so stale viewer writes
            # become a retryable 409 instead of an opaque 500.
            raise ActionPlanConflictError(str(error)) from error
        return await self.workspace(request.options)

    async def update_workspace_selection(
        self, request: DuplicateWorkspaceSelectionDelta
    ) -> DuplicateWorkspaceState:
        current = await self.workspace(request.options)
        if current.revision != request.revision:
            raise ActionPlanConflictError("Duplicate workspace changed; reload its membership")
        selected = set(current.selected_group_ids)
        selected.difference_update(request.removed_group_ids)
        selected.update(request.added_group_ids)
        return await self.save_workspace_selection(
            DuplicateWorkspaceSelectionUpdate(
                options=request.options,
                selected_group_ids=sorted(selected),
                active_group_id=request.active_group_id,
                revision=request.revision,
            )
        )

    async def workspace_membership(
        self, request: DuplicateWorkspaceMembershipRequest
    ) -> DuplicateWorkspaceMembership:
        current = await self.workspace(request.options)
        requested = set(request.group_ids)
        return DuplicateWorkspaceMembership(
            revision=current.revision,
            selected_count=current.selected_count,
            selected_group_ids=[
                group_id for group_id in current.selected_group_ids if group_id in requested
            ],
        )

    async def apply_rules(
        self,
        options: DuplicateAnalysisOptions,
    ) -> DuplicateWorkspaceState:
        """Persist automatic recommendations in bounded projection-backed batches."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        safe_options = options.model_copy(update={"analyze_automatically": False})
        limit = getattr(self._settings, "action_max_targets", 5000)
        target_ids = await self._matching_group_ids(
            source="both",
            state="auto_ready",
            limit=limit + 1,
        )
        if len(target_ids) > limit:
            raise ValueError(
                f"Automatic duplicate rules match more than the configured {limit} group limit"
            )
        current_workspace = await self.workspace(safe_options)
        applied_group_ids: list[str] = []
        batch_size = max(
            1,
            min(250, getattr(self._settings, "sync_batch_size", 250)),
        )
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            _, _, _, snapshot = await self._snapshot_groups(discovered, safe_options)
            for discovery_source in {
                group.discovery_source for group in snapshot.groups
            }:
                groups = [
                    group
                    for group in snapshot.groups
                    if group.discovery_source == discovery_source and group.auto_selected
                ]
                records = await self._reviews.get_many(
                    discovery_source,
                    [group.stable_group_key for group in groups],
                )
                for group in groups:
                    record = records.get(group.stable_group_key)
                    existing_decisions = (
                        list(getattr(record, "member_decisions", []) or [])
                        if record
                        else []
                    )
                    if getattr(record, "manual_action", None) is not None or any(
                        decision.get("source") == "manual"
                        for decision in existing_decisions
                        if isinstance(decision, dict)
                    ):
                        continue
                    recommended = [
                        {
                            "asset_id": str(member.id),
                            "disposition": member.recommended_disposition,
                            "source": "automatic",
                            "status": "pending",
                        }
                        for member in group.members
                        if member.recommended_disposition is not None
                    ]
                    if len(recommended) != len(group.members):
                        continue
                    await self._reviews.save_draft(
                        discovery_source=group.discovery_source,
                        provider_group_id=group.provider_group_id or group.group_id,
                        stable_group_key=group.stable_group_key,
                        member_set_key=group.member_set_key,
                        member_fingerprint=group.member_fingerprint,
                        member_decisions=recommended,
                        stack_primary_asset_id=(
                            group.recommended_primary_asset_id
                            if group.recommended_action == "stack_all"
                            else None
                        ),
                        stack_resolution="move_selected",
                        metadata_keeper_asset_id=None,
                        draft_status="pending",
                    )
                    applied_group_ids.append(group.group_id)

        selected_group_ids = list(
            dict.fromkeys([*current_workspace.selected_group_ids, *applied_group_ids])
        )
        return await self.save_workspace_selection(
            DuplicateWorkspaceSelectionUpdate(
                options=safe_options,
                selected_group_ids=selected_group_ids,
                active_group_id=current_workspace.active_group_id,
                revision=current_workspace.revision,
            )
        )

    async def reset_workspace_decisions(
        self,
        request: DuplicateWorkspaceResetRequest,
    ) -> DuplicateWorkspaceState:
        """Clear saved choices and remove those groups from the durable selection."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        if request.all_decisions:
            cleared_group_count = await self._reviews.reset_all_decisions()
            return DuplicateWorkspaceState(cleared_group_count=cleared_group_count)
        requested_ids = list(dict.fromkeys(request.group_ids))
        identities = await self._group_identities(group_ids=requested_ids)
        groups_by_id: dict[str, Any] = {group.group_id: group for group in identities}
        missing = [group_id for group_id in requested_ids if group_id not in groups_by_id]
        if missing:
            raise ActionPlanConflictError("A duplicate group is no longer available")

        stable_keys_by_source: dict[str, list[str]] = {}
        for group_id in requested_ids:
            group = groups_by_id[group_id]
            source = group.discovery_source
            source_name = source.value if isinstance(source, DiscoverySource) else str(source)
            stable_keys_by_source.setdefault(source_name, []).append(group.stable_group_key)
        for discovery_source, stable_group_keys in stable_keys_by_source.items():
            await self._reviews.clear_decisions(discovery_source, stable_group_keys)

        await self._reviews.consume_workspace_groups(
            [groups_by_id[group_id].stable_group_key for group_id in requested_ids],
            requested_ids,
        )
        return await self.workspace(request.options)

    @staticmethod
    def _review_state_query(review_filter: str) -> str:
        return {
            "All groups": "all",
            "Needs review": "needs_review",
            "Auto-ready": "auto_ready",
            "Blocked": "blocked",
            "Actionable": "actionable",
            "Needs decisions": "needs_decisions",
        }.get(review_filter, "all")

    async def _matching_group_ids(
        self,
        *,
        source: str,
        state: str,
        limit: int,
    ) -> list[str]:
        resolver = getattr(self._discovery, "resolve_matching_group_ids", None)
        if not callable(resolver):
            raise RuntimeError(
                "Filtered duplicate ID lookup requires the persisted V2 projection"
            )
        return await resolver(source=source, state=state, limit=limit)

    async def _keeper_target_ids(
        self,
        request: DuplicateKeeperSelectionRequest,
    ) -> tuple[list[str], bool]:
        if request.scope == "current_page":
            return list(dict.fromkeys(request.group_ids)), False

        limit = self._settings.action_max_targets
        group_ids = await self._matching_group_ids(
            source=request.source_filter,
            state=self._review_state_query(request.review_filter),
            limit=limit + 1,
        )
        return group_ids[:limit], len(group_ids) > limit

    async def _run_keeper_selection(
        self,
        request: DuplicateKeeperSelectionRequest,
        *,
        apply: bool,
    ) -> DuplicateKeeperSelectionResult:
        """Preview or persist bounded rule-driven keep/delete drafts."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        target_ids, limit_exceeded = await self._keeper_target_ids(request)
        counts = {
            "matched_group_count": len(target_ids),
            "valid_group_count": 0,
            "resolved_group_count": 0,
            "would_apply_group_count": 0,
            "applied_group_count": 0,
            "ambiguous_group_count": 0,
            "blocked_group_count": 0,
            "preserved_manual_group_count": 0,
            "missing_group_count": 0,
            "keeper_count": 0,
            "trash_count": 0,
        }
        if limit_exceeded:
            counts["matched_group_count"] = self._settings.action_max_targets + 1
            return DuplicateKeeperSelectionResult(**counts, limit_exceeded=True)

        options = await self._options(request.options)
        batch_size = max(1, min(250, getattr(self._settings, "sync_batch_size", 250)))
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            discovered_by_id = {group.group_id: group for group in discovered}
            _, _, _, snapshot = await self._snapshot_groups(discovered, options)
            exact_by_id = {group.group_id: group for group in snapshot.groups}
            missing = set(batch_ids) - set(exact_by_id)
            counts["missing_group_count"] += len(missing)

            asset_ids = {asset.id for group in discovered for asset in group.assets}
            relations = await self._assets.get_relation_ids(asset_ids)

            review_records: dict[tuple[str, str], Any] = {}
            for discovery_source in {group.discovery_source for group in snapshot.groups}:
                source_groups = [
                    group for group in snapshot.groups if group.discovery_source == discovery_source
                ]
                records = await self._reviews.get_many(
                    discovery_source,
                    [group.stable_group_key for group in source_groups],
                )
                review_records.update(
                    ((discovery_source, key), record) for key, record in records.items()
                )

            drafts: list[dict[str, Any]] = []
            for group_id in batch_ids:
                exact = exact_by_id.get(group_id)
                source = discovered_by_id.get(group_id)
                if exact is None or source is None:
                    continue
                invalid = not exact.eligible or len(exact.members) < 2
                if invalid:
                    counts["blocked_group_count"] += 1
                    continue
                counts["valid_group_count"] += 1

                record = review_records.get((exact.discovery_source, exact.stable_group_key))
                existing_decisions = list(getattr(record, "member_decisions", []) or [])
                has_manual = any(
                    isinstance(decision, dict) and decision.get("source") == "manual"
                    for decision in existing_decisions
                )
                if has_manual and not request.overwrite_manual:
                    counts["preserved_manual_group_count"] += 1
                    continue

                choice = choose_keeper(exact, source, request.rules, relations)
                if choice.keeper_asset_id is None:
                    counts["ambiguous_group_count"] += 1
                    continue
                counts["resolved_group_count"] += 1
                counts["would_apply_group_count"] += 1
                counts["keeper_count"] += 1
                counts["trash_count"] += len(exact.members) - 1

                if apply:
                    drafts.append(
                        {
                            "discovery_source": exact.discovery_source,
                            "provider_group_id": exact.provider_group_id or exact.group_id,
                            "stable_group_key": exact.stable_group_key,
                            "member_set_key": exact.member_set_key,
                            "member_fingerprint": exact.member_fingerprint,
                            "member_decisions": [
                                {
                                    "asset_id": str(member.id),
                                    "disposition": (
                                        "keep"
                                        if member.id == choice.keeper_asset_id
                                        else "delete"
                                    ),
                                    "source": "automatic",
                                    "status": "pending",
                                }
                                for member in exact.members
                            ],
                            "stack_primary_asset_id": None,
                            "stack_resolution": "move_selected",
                            "metadata_keeper_asset_id": choice.keeper_asset_id,
                            "draft_status": "completed",
                        }
                    )

            if apply and drafts:
                save_many = getattr(self._reviews, "save_drafts", None)
                if callable(save_many):
                    await save_many(drafts)
                else:
                    for draft in drafts:
                        await self._reviews.save_draft(**draft)
                counts["applied_group_count"] += len(drafts)

        return DuplicateKeeperSelectionResult(**counts, limit_exceeded=False)

    async def preview_keeper_selection(
        self,
        request: DuplicateKeeperSelectionRequest,
    ) -> DuplicateKeeperSelectionResult:
        return await self._run_keeper_selection(request, apply=False)

    async def apply_keeper_selection(
        self,
        request: DuplicateKeeperSelectionRequest,
    ) -> DuplicateKeeperSelectionResult:
        return await self._run_keeper_selection(request, apply=True)

    async def apply_workspace_preset(
        self, request: DuplicateWorkspacePresetRequest
    ) -> DuplicateWorkspaceState:
        """Persist a preset without hydrating the complete duplicate projection."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        options = await self._options(request.options)
        if request.scope == "all_matching":
            limit = getattr(self._settings, "action_max_targets", 5000)
            resolved_ids = await self._matching_group_ids(
                source=request.source_filter,
                state=self._review_state_query(request.review_filter),
                limit=limit + 1,
            )
            if len(resolved_ids) > limit:
                raise ValueError(
                    f"Duplicate preset matches more than the configured {limit} group limit"
                )
            target_ids = resolved_ids
        else:
            target_ids = list(dict.fromkeys(request.group_ids))

        expected_source = (
            "immich_duplicate"
            if request.source_filter == "immich"
            else "companion_similarity"
        )
        applied: list[str] = []
        skipped: list[str] = []
        batch_size = max(1, min(250, self._settings.sync_batch_size))
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            _, _, _, snapshot = await self._snapshot_groups(discovered, options)
            groups_by_id = {group.group_id: group for group in snapshot.groups}
            for group_id in batch_ids:
                group = groups_by_id.get(group_id)
                if group is None:
                    skipped.append(group_id)
                    continue
                if (
                    request.source_filter != "both"
                    and expected_source not in group.discovery_sources
                ):
                    skipped.append(group_id)
                    continue
                invalid = (
                    not group.members
                    or (request.disposition == "delete" and not group.eligible)
                    or (
                        request.disposition == "stack"
                        and (
                            len(group.members) < 2
                            or any(member.is_offline for member in group.members)
                        )
                    )
                )
                if invalid:
                    skipped.append(group.group_id)
                    continue
                primary = group.effective_primary_asset_id or group.keeper_asset_id
                member_ids = {member.id for member in group.members}
                if primary not in member_ids:
                    primary = group.members[0].id
                await self._reviews.save_draft(
                    discovery_source=group.discovery_source,
                    provider_group_id=group.provider_group_id or group.group_id,
                    stable_group_key=group.stable_group_key,
                    member_set_key=group.member_set_key,
                    member_fingerprint=group.member_fingerprint,
                    member_decisions=[
                        {
                            "asset_id": str(member.id),
                            "disposition": request.disposition,
                            "source": "manual",
                            "status": "pending",
                        }
                        for member in group.members
                    ],
                    stack_primary_asset_id=(
                        primary if request.disposition == "stack" else None
                    ),
                    stack_resolution="move_selected",
                    metadata_keeper_asset_id=None,
                    draft_status="completed",
                )
                applied.append(group.group_id)

        workspace = await self.workspace(options)
        updated = await self.save_workspace_selection(
            DuplicateWorkspaceSelectionUpdate(
                options=options,
                selected_group_ids=list(
                    dict.fromkeys([*workspace.selected_group_ids, *applied])
                ),
                active_group_id=workspace.active_group_id,
                revision=workspace.revision,
            )
        )
        return updated.model_copy(
            update={
                "last_applied_group_ids": applied,
                "last_skipped_group_ids": skipped,
            }
        )

    async def save_group_draft(
        self,
        request: DuplicateGroupDraftUpdate,
    ) -> DuplicateGroupDraft:
        """Validate and save member-level choices independently of execution."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        options = await self._options(request.options)
        groups = await self._groups_by_ids([request.group_id])
        _, _, _, result = await self._snapshot_groups(groups, options)
        group = next(
            (candidate for candidate in result.groups if candidate.group_id == request.group_id),
            None,
        )
        if group is None or group.member_fingerprint != request.member_fingerprint:
            raise ActionPlanConflictError("The duplicate group changed before its draft was saved")
        member_ids = {member.id for member in group.members}
        decisions = {decision.asset_id: decision for decision in request.decisions}
        if not set(decisions).issubset(member_ids):
            raise ActionPlanConflictError("A draft decision references a non-member asset")
        if request.stack_primary_asset_id is not None:
            primary = decisions.get(request.stack_primary_asset_id)
            if primary is None or primary.disposition != "stack":
                raise ActionPlanConflictError(
                    "The stack primary must first have the Stack disposition"
                )
        stack_ids = [
            decision.asset_id for decision in request.decisions if decision.disposition == "stack"
        ]
        stack_primary_asset_id = request.stack_primary_asset_id
        if stack_ids and stack_primary_asset_id is None:
            preferred_primary = group.effective_primary_asset_id or group.keeper_asset_id
            stack_primary_asset_id = (
                preferred_primary if preferred_primary in stack_ids else stack_ids[0]
            )
        survivor_ids = [
            decision.asset_id for decision in request.decisions if decision.disposition != "delete"
        ]
        has_deletions = any(decision.disposition == "delete" for decision in request.decisions)
        metadata_keeper_asset_id = (
            survivor_ids[0]
            if request.status == "completed"
            and len(decisions) == len(member_ids)
            and has_deletions
            and len(survivor_ids) == 1
            else None
        )
        record = await self._reviews.save_draft(
            discovery_source=group.discovery_source,
            provider_group_id=group.provider_group_id or group.group_id,
            stable_group_key=group.stable_group_key,
            member_set_key=group.member_set_key,
            member_fingerprint=group.member_fingerprint,
            member_decisions=[decision.model_dump(mode="json") for decision in request.decisions],
            stack_primary_asset_id=stack_primary_asset_id,
            stack_resolution=request.stack_resolution,
            metadata_keeper_asset_id=metadata_keeper_asset_id,
            draft_status=request.status,
        )
        return DuplicateGroupDraft(
            group_id=group.group_id,
            discovery_source=group.discovery_source,
            member_fingerprint=record.member_fingerprint,
            decisions=record.member_decisions,
            stack_primary_asset_id=record.stack_primary_asset_id,
            stack_resolution=record.stack_resolution,
            metadata_keeper_asset_id=record.metadata_keeper_asset_id,
            status=record.draft_status,
            stale=False,
        )

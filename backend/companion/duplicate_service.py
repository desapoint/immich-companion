"""Immich-driven exact duplicate review and bounded batch resolution."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

from companion.action_repository import ActionRepository
from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
    DestructiveActionsDisabledError,
)
from companion.asset_repository import AssetRepository
from companion.config import Settings
from companion.discovery import (
    DiscoveredGroup,
    GroupDiscoveryProvider,
    ImmichDuplicateProvider,
)
from companion.duplicate_policy import DuplicatePolicyRepository
from companion.duplicate_review_repository import DuplicateReviewRepository
from companion.duplicate_schema import (
    CrossSourceDuplicateResult,
    CrossSourceDuplicateTaskStart,
    DuplicateAnalysisOptions,
    DuplicateMember,
    DuplicateMemberEvidence,
    DuplicatePreservationEvidence,
    DuplicateResolutionExecuteRequest,
    DuplicateResolutionPlan,
    DuplicateResolutionPlanGroup,
    DuplicateResolutionPlanRequest,
    DuplicateReviewUpdate,
    DuplicateSimilarityEvidence,
    DuplicateSimilarityReferenceRequest,
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
    report_freshness,
    similarity_feature_freshness,
)
from companion.integrity_service import INTEGRITY_TASK_TYPE, IntegrityTaskHandler
from companion.models import (
    ActionPlanRecord,
    AssetIntegrityReportRecord,
    AssetSimilarityFeatureRecord,
)
from companion.similarity_repository import PairSimilarityEvidence, SimilarityRepository
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"


def _options_key(options: DuplicateAnalysisOptions) -> str:
    raw = json.dumps(options.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _plan_digest(groups: list[dict[str, Any]]) -> str:
    raw = json.dumps(groups, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _member_fingerprint(asset_ids: list[UUID]) -> str:
    raw = ",".join(sorted(str(asset_id) for asset_id in asset_ids))
    return sha256(raw.encode()).hexdigest()


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
            if action in {"resolve", "delete_all"}
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


def _normalize_plan_group(group: dict[str, Any]) -> dict[str, Any]:
    """Read legacy Immich plans without invalidating them."""

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
        [normalized["keeper_asset_id"], *normalized.get("trash_asset_ids", [])],
    )
    member_ids = [UUID(value) for value in normalized["member_asset_ids"]]
    primary_id = (
        UUID(normalized["keeper_asset_id"])
        if normalized.get("keeper_asset_id") is not None
        else None
    )
    normalized.setdefault("member_fingerprint", _member_fingerprint(member_ids))
    normalized.setdefault(
        "members",
        _member_dispositions(normalized["action"], member_ids, primary_id),
    )
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
        delete_all_group_count=sum(group.action == "delete_all" for group in groups),
        stack_group_count=sum(group.action == "stack_all" for group in groups),
        trash_asset_count=sum(len(group.trash_asset_ids) for group in groups),
        retained_asset_count=sum(
            member.disposition in {"keep", "stack"} for group in groups for member in group.members
        ),
        zero_survivor_group_count=sum(group.action == "delete_all" for group in groups),
        expires_at=record.expires_at,
        destructive=getattr(record, "destructive", True),
    )


class CrossSourceDuplicateService:
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
        self._discovery = discovery or ImmichDuplicateProvider(immich)

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

    async def _live_groups(self) -> list[DiscoveredGroup]:
        return await self._discovery.discover()

    async def result(
        self,
        options: DuplicateAnalysisOptions | None = None,
    ) -> CrossSourceDuplicateResult:
        options = await self._options(options)
        _, _, _, result = await self._snapshot(options)
        return result

    async def review(
        self,
        options: DuplicateAnalysisOptions | None = None,
    ) -> CrossSourceDuplicateResult:
        """Return live Immich groups and idempotently queue missing verification."""

        options = await self._options(options)
        groups, reports, features, result = await self._snapshot(options)
        include_similarity = self._similarity is not None
        candidates = self._verification_candidates(
            groups,
            options,
            include_similarity=include_similarity,
        )
        pending_count = len(
            self._pending_verification(
                groups,
                reports,
                features,
                options,
                include_similarity=include_similarity,
            )
        )
        task_id: UUID | None = None
        if pending_count and options.analyze_automatically:
            task_id = (await self.start(options)).task_id
        return result.model_copy(
            update={
                "analysis_task_id": task_id,
                "analysis_pending_count": pending_count,
                "analysis_candidate_count": len(candidates),
                "analysis_cached_count": len(candidates) - pending_count,
            }
        )

    async def _snapshot(
        self,
        options: DuplicateAnalysisOptions,
    ) -> tuple[
        list[DiscoveredGroup],
        dict[UUID, AssetIntegrityReportRecord],
        dict[UUID, AssetSimilarityFeatureRecord],
        CrossSourceDuplicateResult,
    ]:
        groups = await self._live_groups()
        report_ids = [
            asset.id
            for group in groups
            for asset in group.assets
            if asset.library_id is not None or options.verify_upload_streams
        ]
        reports = await self._reports.get_many(report_ids)
        image_ids = [
            asset.id
            for group in groups
            for asset in group.assets
            if asset.asset_type == "IMAGE" and not asset.is_offline
        ]
        loaded_features = (
            await self._reports.get_similarity_features(image_ids)
            if self._similarity is not None
            else {}
        )
        source_assets = {asset.id: asset for group in groups for asset in group.assets}
        features = {
            asset_id: feature
            for asset_id, feature in loaded_features.items()
            if similarity_feature_freshness(feature, source_assets[asset_id]) == "current"
        }
        result = self.assemble(groups, reports, options, self._immich)
        if self._similarity is not None:
            edges = await self._similarity.reference_edges(
                [[asset.id for asset in group.assets] for group in groups],
                features,
            )
            result = self._apply_similarity(result, groups, edges, features)
        if self._reviews is not None:
            result = await self._apply_review_states(result)
        return groups, reports, features, result

    async def similarity_reference(
        self,
        group_id: str,
        request: DuplicateSimilarityReferenceRequest,
    ) -> ExactDuplicateGroup:
        """Return one live group relative to a requested member-owned reference."""

        if self._similarity is None:
            raise RuntimeError("Duplicate similarity persistence is unavailable")
        source = next(
            (
                group
                for group in await self._live_groups()
                if group.group_id == group_id
            ),
            None,
        )
        if source is None:
            raise ActionPlanNotFoundError("The duplicate group is no longer available")
        members = {asset.id: asset for asset in source.assets}
        if request.reference_asset_id not in members:
            raise ActionPlanConflictError(
                "The similarity reference is not a member of this duplicate group"
            )
        options = await self._options(None)
        report_ids = [
            asset.id
            for asset in source.assets
            if asset.library_id is not None or options.verify_upload_streams
        ]
        reports = await self._reports.get_many(report_ids)
        image_assets = [
            asset for asset in source.assets if asset.asset_type == "IMAGE" and not asset.is_offline
        ]
        loaded_features = await self._reports.get_similarity_features(
            [asset.id for asset in image_assets]
        )
        features = {
            asset.id: loaded_features[asset.id]
            for asset in image_assets
            if asset.id in loaded_features
            and similarity_feature_freshness(loaded_features[asset.id], asset) == "current"
        }
        ordered_ids = [
            request.reference_asset_id,
            *(asset.id for asset in source.assets if asset.id != request.reference_asset_id),
        ]
        edges = await self._similarity.reference_edges([ordered_ids], features)
        result = self.assemble([source], reports, options, self._immich)
        reordered_source = replace(
            source,
            assets=tuple(members[asset_id] for asset_id in ordered_ids),
        )
        result = self._apply_similarity(
            result,
            [reordered_source],
            edges,
            features,
        )
        if self._reviews is not None:
            result = await self._apply_review_states(result)
        return result.groups[0]

    @staticmethod
    def _apply_similarity(
        result: CrossSourceDuplicateResult,
        source_groups: list[DiscoveredGroup],
        edges: dict[tuple[UUID, UUID], PairSimilarityEvidence],
        features: dict[UUID, AssetSimilarityFeatureRecord],
    ) -> CrossSourceDuplicateResult:
        source_by_id = {group.group_id: group for group in source_groups}
        updated_groups: list[ExactDuplicateGroup] = []
        for group in result.groups:
            source = source_by_id[group.group_id]
            if not source.assets:
                updated_groups.append(group)
                continue
            reference = source.assets[0]
            source_members = {asset.id: asset for asset in source.assets}
            members: list[DuplicateMember] = []
            for member in group.members:
                source_member = source_members[member.id]
                edge = edges.get((reference.id, member.id))
                feature = features.get(member.id)
                if member.id == reference.id:
                    similarity = DuplicateSimilarityEvidence(
                        state="reference",
                        reference_asset_id=reference.id,
                        similarity_percent=100.0,
                        structural_percent=100.0,
                        perceptual_percent=100.0,
                        color_percent=100.0,
                        exact_thumbnail_match=True if feature is not None else None,
                        exact_pixel_match=True if feature is not None else None,
                        model_version=feature.model_version if feature is not None else None,
                        feature_version=feature.feature_version if feature is not None else None,
                    )
                elif edge is not None:
                    similarity = DuplicateSimilarityEvidence(
                        state="current",
                        reference_asset_id=reference.id,
                        similarity_percent=edge.similarity_percent,
                        structural_percent=edge.structural_percent,
                        perceptual_percent=edge.perceptual_percent,
                        color_percent=edge.color_percent,
                        exact_thumbnail_match=edge.exact_thumbnail_match,
                        exact_pixel_match=edge.exact_pixel_match,
                        model_version=edge.model_version,
                        feature_version=edge.feature_version,
                        comparison_version=edge.comparison_version,
                    )
                else:
                    similarity = DuplicateSimilarityEvidence(
                        state=(
                            "unavailable"
                            if source_member.is_offline or source_member.asset_type != "IMAGE"
                            else "pending"
                        ),
                        reference_asset_id=reference.id,
                    )
                preservation = (
                    DuplicatePreservationEvidence(
                        pixel_normalization_version=feature.pixel_normalization_version,
                        pixel_sha256=feature.pixel_sha256,
                        decoded_width=feature.width,
                        decoded_height=feature.height,
                        bit_depth=feature.bit_depth,
                        channel_count=feature.channel_count,
                        has_alpha=feature.has_alpha,
                        color_space=feature.color_space,
                        orientation=feature.orientation,
                        icc_profile_present=feature.icc_profile_present,
                        has_exif=feature.has_exif,
                        has_capture_time=feature.has_capture_time,
                        has_camera_info=feature.has_camera_info,
                        has_gps=feature.has_gps,
                        has_orientation_metadata=feature.has_orientation_metadata,
                        metadata_richness=feature.metadata_richness,
                    )
                    if feature is not None
                    else None
                )
                members.append(
                    member.model_copy(
                        update={
                            "similarity": similarity,
                            "preservation": preservation,
                        }
                    )
                )
            group_update: dict[str, object] = {"members": members}
            if source.discovery_source is DiscoverySource.COMPANION_SIMILARITY:
                pair_evidence = next(
                    (
                        member.similarity
                        for member in members
                        if member.similarity is not None
                        and member.similarity.state == "current"
                    ),
                    None,
                )
                threshold = source.provider_metadata.get("scan_threshold_percent")
                if pair_evidence is not None:
                    score = pair_evidence.similarity_percent
                    classification = (
                        GroupClassification.EXACT_PIXELS.value
                        if pair_evidence.exact_pixel_match
                        else GroupClassification.LIKELY_SAME.value
                        if score is not None and score >= 98
                        else GroupClassification.SIMILAR.value
                    )
                    threshold_detail = f" at a {threshold}% scan threshold" if threshold else ""
                    group_update.update(
                        {
                            "classification": classification,
                            "reason": (
                                f"Companion found a {score:.1f}% visual match"
                                f"{threshold_detail}. Review it manually before acting."
                                if score is not None
                                else (
                                    "Companion found a visual match. Review it manually "
                                    "before acting."
                                )
                            ),
                        }
                    )
                group_update.update(
                    {
                        "eligible": False,
                        "auto_resolvable": False,
                        "auto_selected": False,
                        "recommended_action": "none",
                        "recommended_primary_asset_id": None,
                        "keeper_asset_id": None,
                        "effective_action": "none",
                        "effective_primary_asset_id": None,
                        "action_source": "none",
                        "primary_source": "none",
                        "recommendation_reason_codes": ["non_exact_match"],
                    }
                )
            updated_groups.append(group.model_copy(update=group_update))
        return result.model_copy(update={"groups": updated_groups})

    async def _apply_review_states(
        self,
        result: CrossSourceDuplicateResult,
    ) -> CrossSourceDuplicateResult:
        assert self._reviews is not None
        states_by_source: dict[tuple[str, str], Any] = {}
        for discovery_source in {group.discovery_source for group in result.groups}:
            source_groups = [
                group
                for group in result.groups
                if group.discovery_source == discovery_source
            ]
            review_keys = list(
                dict.fromkeys(
                    [group.group_id for group in source_groups]
                    + [
                        group.provider_group_id
                        for group in source_groups
                        if group.provider_group_id is not None
                    ]
                )
            )
            states = await self._reviews.get_many(
                discovery_source,
                review_keys,
            )
            states_by_source.update(
                ((discovery_source, provider_id), state)
                for provider_id, state in states.items()
            )
        groups: list[ExactDuplicateGroup] = []
        for group in result.groups:
            state = states_by_source.get((group.discovery_source, group.group_id)) or (
                states_by_source.get((group.discovery_source, group.provider_group_id))
                if group.provider_group_id
                else None
            )
            if state is None:
                groups.append(group)
                continue
            if state.member_fingerprint != group.member_fingerprint:
                groups.append(group.model_copy(update={"review_status": "drifted"}))
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
        return result.model_copy(update={"groups": groups})

    @staticmethod
    def _verification_candidates(
        groups: list[DiscoveredGroup],
        options: DuplicateAnalysisOptions,
        *,
        include_similarity: bool = False,
    ) -> list[ImmichAsset]:
        candidates = {
            asset.id: asset
            for group in groups
            for asset in group.assets
            if not asset.is_offline
            and (
                asset.library_id is not None
                or options.verify_upload_streams
                or include_similarity
                and asset.asset_type == "IMAGE"
            )
        }
        return list(candidates.values())

    @classmethod
    def _pending_verification(
        cls,
        groups: list[DiscoveredGroup],
        reports: dict[UUID, AssetIntegrityReportRecord],
        features: dict[UUID, AssetSimilarityFeatureRecord],
        options: DuplicateAnalysisOptions,
        *,
        include_similarity: bool = False,
    ) -> list[ImmichAsset]:
        return [
            asset
            for asset in cls._verification_candidates(
                groups,
                options,
                include_similarity=include_similarity,
            )
            if (
                (asset.library_id is not None or options.verify_upload_streams)
                and report_freshness(reports.get(asset.id), asset) != "current"
            )
            or (
                include_similarity
                and asset.asset_type == "IMAGE"
                and similarity_feature_freshness(features.get(asset.id), asset) != "current"
            )
        ]

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
                    )
                    for asset in assets
                ),
            )
            decision = decide_group(
                candidate,
                ResolutionPolicy(
                    keeper_preference=options.keeper_policy,
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
                    evidence=CrossSourceDuplicateService._member_evidence(
                        asset,
                        reports.get(asset.id),
                    ),
                )
                for asset in assets
            ]
            public_groups.append(
                ExactDuplicateGroup(
                    group_id=candidate.group_id,
                    discovery_source=candidate.discovery_source.value,
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
        result = await self.result(options)
        group = next(
            (
                candidate
                for candidate in result.groups
                if candidate.group_id == request.group_id
            ),
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
            raise ActionPlanConflictError("Only verified exact groups can be resolved")
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
            provider_group_id=group.group_id,
            member_fingerprint=group.member_fingerprint,
            manual_action=action,
            manual_primary_asset_id=primary_id,
            review_status=review_status,
        )
        refreshed = await self.result(options)
        return next(
            candidate
            for candidate in refreshed.groups
            if candidate.group_id == request.group_id
        )

    async def plan(self, request: DuplicateResolutionPlanRequest) -> DuplicateResolutionPlan:
        result = await self.result(request.options)
        selected = (
            [group for group in result.groups if group.auto_resolvable]
            if request.all_eligible
            else [group for group in result.groups if group.group_id in request.group_ids]
        )
        if not selected:
            raise ValueError("No duplicate groups were selected")
        if not request.all_eligible and {group.group_id for group in selected} != set(
            request.group_ids
        ):
            raise ActionPlanConflictError("A selected duplicate group is no longer available")
        plan_groups: list[dict[str, Any]] = []
        for group in selected:
            member_ids = {member.id for member in group.members}
            action = request.action_overrides.get(
                group.group_id,
                "resolve"
                if request.all_eligible or group.group_id in request.keeper_overrides
                else group.effective_action,
            )
            if action == "none":
                raise ActionPlanConflictError("Every selected group needs an action")
            if action == "resolve" and (
                not group.eligible or any(member.is_offline for member in group.members)
            ):
                raise ActionPlanConflictError(
                    "Only available, verified exact groups can be resolved"
                )
            if action == "stack_all" and any(
                member.is_offline or member.is_stacked for member in group.members
            ):
                raise ActionPlanConflictError(
                    "Offline or already-stacked members cannot form a new stack"
                )
            primary_required = action in {"resolve", "stack_all"}
            keeper_id = (
                request.keeper_overrides.get(
                    group.group_id,
                    group.effective_primary_asset_id or group.keeper_asset_id,
                )
                if primary_required
                else None
            )
            if primary_required and (keeper_id is None or keeper_id not in member_ids):
                raise ActionPlanConflictError("A primary asset must be chosen from the group")
            ordered_members = (
                [
                    keeper_id,
                    *(member.id for member in group.members if member.id != keeper_id),
                ]
                if keeper_id is not None
                else [member.id for member in group.members]
            )
            trash_ids = (
                [member.id for member in group.members if member.id != keeper_id]
                if action == "resolve"
                else [member.id for member in group.members]
                if action == "delete_all"
                else []
            )
            plan_groups.append(
                {
                    "group_id": group.group_id,
                    "discovery_source": group.discovery_source,
                    "provider_group_id": group.provider_group_id,
                    "action": action,
                    "keeper_asset_id": str(keeper_id) if keeper_id is not None else None,
                    "member_asset_ids": [str(asset_id) for asset_id in ordered_members],
                    "trash_asset_ids": [str(asset_id) for asset_id in trash_ids],
                    "member_fingerprint": group.member_fingerprint,
                    "members": _member_dispositions(action, ordered_members, keeper_id),
                }
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
        if record.status != "planned":
            raise ActionPlanConflictError("Duplicate resolution plan has already been used")
        if record.expires_at <= datetime.now(UTC):
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
        existing = await self._actions.get_plan(plan_id)
        if existing is None or existing.action != "resolve_duplicates":
            raise PermanentTaskError("Duplicate resolution plan was not found")
        if existing.status not in {"planned", "running"}:
            raise PermanentTaskError("Duplicate resolution plan has already been used")
        if existing.destructive and not self._settings.allow_destructive_actions:
            raise PermanentTaskError("Duplicate resolution is disabled in safe mode")

        raw_groups = [
            _normalize_plan_group(item) for item in existing.relation_work.get("groups", [])
        ]
        options = DuplicateAnalysisOptions.model_validate(existing.relation_work.get("options", {}))
        reviewed = {group.group_id: group for group in (await self.result(options)).groups}
        for planned in raw_groups:
            live_group = reviewed.get(planned["group_id"])
            planned_members = {UUID(value) for value in planned["member_asset_ids"]}
            if (
                live_group is None
                or {asset.id for asset in live_group.members} != planned_members
                or live_group.member_fingerprint != planned["member_fingerprint"]
                or (planned["action"] == "resolve" and not live_group.eligible)
                or (
                    planned["action"] == "stack_all"
                    and any(member.is_offline or member.is_stacked for member in live_group.members)
                )
            ):
                await self._actions.finish_plan(plan_id, "drifted", {"error": "group_drift"})
                raise PermanentTaskError("A duplicate group changed after review")

        if existing.status == "planned":
            claimed = await self._actions.claim_plan(plan_id)
            if claimed is None:
                raise PermanentTaskError("Duplicate resolution plan has already been used")

        pacing = await self._runtime_sync_settings.get()
        batch_size = pacing.full_batch_size
        processed = 0
        successful_ids: set[str] = set()
        resolved_ids: set[str] = set()
        kept_ids: set[str] = set()
        deleted_ids: set[str] = set()
        stacked_ids: set[str] = set()
        failed_ids: list[str] = []
        trashed_ids: list[UUID] = []

        async def checkpoint(detail: str) -> None:
            await context.checkpoint(
                checkpoint={"phase": "processing", "groups_completed": processed},
                counters={
                    "groups_completed": len(successful_ids),
                    "groups_failed": len(failed_ids),
                },
                progress={
                    "phase": "duplicate_resolution",
                    "completed": processed,
                    "total": len(raw_groups),
                    "percent": round(processed / len(raw_groups) * 100, 1),
                    "detail": detail,
                },
            )

        resolve_groups = [item for item in raw_groups if item["action"] == "resolve"]
        delete_groups = [item for item in raw_groups if item["action"] == "delete_all"]
        keep_groups = [item for item in raw_groups if item["action"] == "keep_all"]
        stack_groups = [item for item in raw_groups if item["action"] == "stack_all"]

        for offset in range(0, len(resolve_groups), batch_size):
            await context.ensure_active()
            batch = resolve_groups[offset : offset + batch_size]
            resolutions = [
                ImmichDuplicateResolution(
                    duplicate_id=UUID(item["provider_group_id"]),
                    keep_asset_id=UUID(item["keeper_asset_id"]),
                    trash_asset_ids=[UUID(value) for value in item["trash_asset_ids"]],
                )
                for item in batch
                if item["discovery_source"] == DiscoverySource.IMMICH_DUPLICATE.value
                and item.get("provider_group_id") is not None
            ]
            if len(resolutions) != len(batch):
                await self._actions.finish_plan(
                    plan_id,
                    "failed",
                    {"error": "unsupported_discovery_provider"},
                )
                raise PermanentTaskError(
                    "Duplicate resolution is not supported for this discovery provider"
                )
            try:
                responses = await self._immich.resolve_duplicate_groups(resolutions)
            except ImmichApiError:
                responses = []
            for index, resolution in enumerate(resolutions):
                identifier = batch[index]["group_id"]
                response = responses[index] if index < len(responses) else {}
                if response.get("success") is True:
                    successful_ids.add(identifier)
                    resolved_ids.add(identifier)
                    trashed_ids.extend(resolution.trash_asset_ids)
                else:
                    failed_ids.append(identifier)
                processed += 1
            await checkpoint("Resolving reviewed duplicate groups through Immich…")
            if offset + len(batch) < len(resolve_groups):
                await asyncio.sleep(pacing.full_min_batch_delay_seconds)

        if trashed_ids:
            await self._assets.remove_assets(trashed_ids)

        for planned in delete_groups:
            await context.ensure_active()
            identifier = planned["group_id"]
            member_ids = [UUID(value) for value in planned["member_asset_ids"]]
            verified_trashed: list[UUID] = []
            try:
                await self._immich.trash_assets(member_ids)
                for asset_id in member_ids:
                    asset = await self._immich.get_asset(asset_id)
                    if not asset.is_trashed:
                        raise ImmichApiError("verify trashed duplicate member")
                    verified_trashed.append(asset_id)
            except ImmichApiError:
                failed_ids.append(identifier)
            else:
                successful_ids.add(identifier)
                deleted_ids.add(identifier)
                trashed_ids.extend(verified_trashed)
                await self._assets.remove_assets(verified_trashed)
            processed += 1
            await checkpoint("Trashing every member of approved duplicate groups…")

        for planned in keep_groups:
            await context.ensure_active()
            identifier = planned["group_id"]
            successful_ids.add(identifier)
            kept_ids.add(identifier)
            processed += 1
            await checkpoint("Recording groups that should keep every copy…")

        for planned in stack_groups:
            await context.ensure_active()
            identifier = planned["group_id"]
            try:
                member_ids = [UUID(value) for value in planned["member_asset_ids"]]
                await self._immich.create_stack(member_ids)
                refreshed_assets: list[ImmichAsset] = []
                for asset_id in member_ids:
                    asset = await self._immich.get_asset(asset_id)
                    refreshed_assets.append(asset)
                    await self._assets.refresh_asset(asset)
                if any(asset.stack is None for asset in refreshed_assets):
                    raise ImmichApiError("verify created stack")
            except ImmichApiError:
                failed_ids.append(identifier)
            else:
                successful_ids.add(identifier)
                stacked_ids.add(identifier)
            processed += 1
            await checkpoint("Creating reviewed Immich duplicate stacks…")

        remaining = {
            str(group.duplicate_id) for group in await self._immich.list_duplicate_groups()
        }
        unresolved = [
            item["group_id"]
            for item in resolve_groups
            if item["action"] == "resolve" and item.get("provider_group_id") in remaining
        ]
        for identifier in unresolved:
            successful_ids.discard(identifier)
            resolved_ids.discard(identifier)
            if identifier not in failed_ids:
                failed_ids.append(identifier)

        if self._reviews is not None:
            review_statuses = {
                "resolve": "reviewed_resolve",
                "keep_all": "reviewed_keep_all",
                "delete_all": "reviewed_delete_all",
                "stack_all": "reviewed_stack_all",
            }
            for planned in raw_groups:
                if planned["group_id"] not in successful_ids:
                    continue
                await self._reviews.save(
                    discovery_source=planned["discovery_source"],
                    provider_group_id=planned["group_id"],
                    member_fingerprint=planned["member_fingerprint"],
                    manual_action=planned["action"],
                    manual_primary_asset_id=(
                        UUID(planned["keeper_asset_id"])
                        if planned.get("keeper_asset_id") is not None
                        else None
                    ),
                    review_status=review_statuses[planned["action"]],
                )

        status = "completed" if not failed_ids else "failed"
        result = {
            "group_count": len(raw_groups),
            "processed_group_count": len(successful_ids),
            "resolved_group_count": len(resolved_ids),
            "kept_all_group_count": len(kept_ids),
            "deleted_all_group_count": len(deleted_ids),
            "stacked_group_count": len(stacked_ids),
            "failed_group_ids": failed_ids,
            "trashed_asset_count": len(trashed_ids),
            "verified": not failed_ids,
        }
        await self._actions.finish_plan(plan_id, status, result)
        return TaskResult(
            status=status,
            summary=result,
            counters={
                "groups_processed": len(successful_ids),
                "groups_resolved": len(resolved_ids),
                "groups_kept_all": len(kept_ids),
                "groups_deleted_all": len(deleted_ids),
                "groups_stacked": len(stacked_ids),
                "groups_failed": len(failed_ids),
                "assets_trashed": len(trashed_ids),
            },
        )


class CrossSourceDuplicateTaskHandler:
    """Boundedly refresh integrity and visual evidence for Immich duplicate groups."""

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
        include_similarity: bool = False,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._integrity = integrity
        self._include_similarity = include_similarity

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        options = DuplicateAnalysisOptions.model_validate(payload)
        groups = await self._immich.list_duplicate_groups()
        candidates: dict[UUID, ImmichAsset] = {}
        for group in groups:
            for asset in group.assets:
                if (
                    asset.library_id is not None
                    or options.verify_upload_streams
                    or self._include_similarity
                    and asset.asset_type == "IMAGE"
                ):
                    if asset.file_size_bytes is None:
                        asset = await self._immich.get_asset(asset.id)
                    candidates[asset.id] = asset

        reports = await self._reports.get_many(list(candidates))
        features = (
            await self._reports.get_similarity_features(list(candidates))
            if self._include_similarity
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
                    self._include_similarity
                    and asset.asset_type == "IMAGE"
                    and similarity_feature_freshness(features.get(asset.id), asset) != "current"
                )
            )
        ]
        unavailable = 0
        await context.checkpoint(
            checkpoint={"phase": "fingerprinting"},
            counters={"files_attempted": 0, "files_unavailable": 0},
            progress={
                "phase": "duplicate_fingerprints",
                "completed": 0,
                "total": len(pending),
                "percent": 0.0,
                "detail": (
                    f"Preparing to verify {len(pending)} duplicate candidate files…"
                    if pending
                    else "All duplicate candidate evidence is current."
                ),
            },
        )
        for index, asset in enumerate(pending, start=1):
            await context.ensure_active()
            await self._assets.refresh_asset(asset)
            try:
                await self._integrity.analyze(
                    context,
                    asset.id,
                    publish_progress=False,
                )
            except (PermanentTaskError, RetryableTaskError, ImmichApiError):
                unavailable += 1
            await context.checkpoint(
                checkpoint={"phase": "fingerprinting", "asset_id": str(asset.id)},
                counters={"files_attempted": index, "files_unavailable": unavailable},
                progress={
                    "phase": "duplicate_fingerprints",
                    "completed": index,
                    "total": len(pending),
                    "percent": round(index / len(pending) * 100, 1),
                    "detail": (f"Verified {index} of {len(pending)} duplicate candidate files"),
                },
            )
        await context.checkpoint(
            checkpoint={"phase": "complete"},
            counters={"files_attempted": len(pending), "files_unavailable": unavailable},
            progress={
                "phase": "complete",
                "completed": len(pending),
                "total": len(pending),
                "percent": 100.0,
                "detail": "Duplicate candidate verification is ready.",
            },
        )
        return TaskResult(
            summary={"duplicate_group_count": len(groups)},
            counters={
                "duplicate_groups": len(groups),
                "candidate_files": len(candidates),
                "files_attempted": len(pending),
                "files_unavailable": unavailable,
            },
        )


class DuplicateResolutionTaskHandler:
    """Execute one reviewed duplicate plan in the serialized action lane."""

    task_type = DUPLICATE_RESOLUTION_TASK_TYPE
    lane_key = "asset_action"
    max_concurrency = 1

    def __init__(self, service: CrossSourceDuplicateService) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        return await self._service.execute_plan(context, UUID(str(payload["plan_id"])))

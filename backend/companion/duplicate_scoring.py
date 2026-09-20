"""Duplicate scoring and group-construction mixin."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from companion.discovery import (
    DiscoveredGroup,
)
from companion.duplicate_contracts import member_fingerprint as _member_fingerprint
from companion.duplicate_identity import member_set_key, stable_group_key
from companion.duplicate_schema import (
    COMPLETED_DUPLICATE_REVIEW_STATUSES,
    CrossSourceDuplicateResult,
    DuplicateAnalysisOptions,
    DuplicateMember,
    DuplicateMemberEvidence,
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
    ImmichAsset,
)
from companion.integrity import decode_immich_sha1
from companion.integrity_repository import (
    preservation_feature_freshness,
    report_freshness,
)
from companion.models import (
    AssetImagePreservationFeatureRecord,
    AssetIntegrityReportRecord,
)

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"

logger = logging.getLogger(__name__)

class DuplicateScoringMixin:
    """Apply evidence, validation, scoring, and group recommendations."""

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

    @classmethod
    def assemble(
        cls,
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
                    evidence=cls._member_evidence(
                        asset,
                        reports.get(asset.id),
                    ),
                    recommended_disposition=(
                        disposition := cls._recommended_disposition(
                            decision.recommended_action.value,
                            asset.id,
                            decision.recommended_primary_asset_id,
                            auto_resolvable=decision.auto_resolvable,
                        )
                    ),
                    recommendation_reason_codes=(
                        cls._member_recommendation_reasons(
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

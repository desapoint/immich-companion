"""Pure duplicate-group decision contracts shared by discovery providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID


class DiscoverySource(StrEnum):
    IMMICH_DUPLICATE = "immich_duplicate"
    COMPANION_SIMILARITY = "companion_similarity"


class GroupClassification(StrEnum):
    EXACT_FILE = "exact_file"
    EXACT_PIXELS = "exact_pixels"
    LIKELY_SAME = "likely_same"
    SIMILAR = "similar"
    MISMATCH = "mismatch"
    UNVERIFIED = "unverified"
    UNAVAILABLE = "unavailable"
    INELIGIBLE = "ineligible"


class GroupAction(StrEnum):
    RESOLVE = "resolve"
    KEEP_ALL = "keep_all"
    DELETE_ALL = "delete_all"
    STACK_ALL = "stack_all"
    NONE = "none"


class DecisionSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    NONE = "none"


class DecisionReason(StrEnum):
    EXACT_CONTENT_SHA1 = "exact_content_sha1"
    PREFERRED_UPLOAD = "preferred_upload"
    PREFERRED_EXTERNAL = "preferred_external"
    MOST_RECENT_UPLOAD = "most_recent_upload"
    EXPLICIT_FIRST_RESULT = "explicit_first_result"
    UNIQUE_CANDIDATE = "unique_candidate"
    MULTIPLE_EQUAL_CANDIDATES = "multiple_equal_candidates"
    MISSING_UPLOAD_TIMESTAMP = "missing_upload_timestamp"
    MISSING_VERIFICATION = "missing_verification"
    CONTENT_MISMATCH = "content_mismatch"
    NON_EXACT_MATCH = "non_exact_match"
    MEMBER_UNAVAILABLE = "member_unavailable"
    GROUP_INELIGIBLE = "group_ineligible"


@dataclass(frozen=True, slots=True)
class CandidateMember:
    asset_id: UUID
    source_kind: Literal["upload", "external"]
    uploaded_at: datetime | None
    available: bool = True


@dataclass(frozen=True, slots=True)
class CandidateGroup:
    group_id: str
    discovery_source: DiscoverySource
    provider_group_id: str | None
    classification: GroupClassification
    members: tuple[CandidateMember, ...]


@dataclass(frozen=True, slots=True)
class ResolutionPolicy:
    keeper_preference: Literal[
        "most_recent", "prefer_upload", "prefer_external", "first"
    ]
    automatic_handling: bool = True
    preselect_safe_groups: bool = True
    exact_file_action: Literal["resolve", "keep_all", "stack_all", "review"] = "resolve"


@dataclass(frozen=True, slots=True)
class GroupDecision:
    recommended_action: GroupAction
    recommended_primary_asset_id: UUID | None
    recommendation_reason_codes: tuple[DecisionReason, ...]
    auto_resolvable: bool
    auto_selected: bool
    action_source: DecisionSource
    primary_source: DecisionSource


def decide_group(group: CandidateGroup, policy: ResolutionPolicy) -> GroupDecision:
    """Return one explainable recommendation without inventing a tie winner."""

    if group.classification is not GroupClassification.EXACT_FILE:
        reason = (
            DecisionReason.GROUP_INELIGIBLE
            if group.classification is GroupClassification.INELIGIBLE
            else DecisionReason.MEMBER_UNAVAILABLE
            if group.classification is GroupClassification.UNAVAILABLE
            else DecisionReason.CONTENT_MISMATCH
            if group.classification is GroupClassification.MISMATCH
            else DecisionReason.NON_EXACT_MATCH
            if group.classification
            in {
                GroupClassification.EXACT_PIXELS,
                GroupClassification.LIKELY_SAME,
                GroupClassification.SIMILAR,
            }
            else DecisionReason.MISSING_VERIFICATION
        )
        return GroupDecision(
            recommended_action=GroupAction.NONE,
            recommended_primary_asset_id=None,
            recommendation_reason_codes=(reason,),
            auto_resolvable=False,
            auto_selected=False,
            action_source=DecisionSource.NONE,
            primary_source=DecisionSource.NONE,
        )

    reasons: list[DecisionReason] = [DecisionReason.EXACT_CONTENT_SHA1]
    candidates = [member for member in group.members if member.available]
    if not candidates:
        return GroupDecision(
            recommended_action=GroupAction.NONE,
            recommended_primary_asset_id=None,
            recommendation_reason_codes=(*reasons, DecisionReason.MEMBER_UNAVAILABLE),
            auto_resolvable=False,
            auto_selected=False,
            action_source=DecisionSource.NONE,
            primary_source=DecisionSource.NONE,
        )

    if policy.keeper_preference == "prefer_upload":
        preferred = [member for member in candidates if member.source_kind == "upload"]
        if preferred:
            candidates = preferred
            reasons.append(DecisionReason.PREFERRED_UPLOAD)
    elif policy.keeper_preference == "prefer_external":
        preferred = [member for member in candidates if member.source_kind == "external"]
        if preferred:
            candidates = preferred
            reasons.append(DecisionReason.PREFERRED_EXTERNAL)

    winner: CandidateMember | None = None
    if len(candidates) == 1:
        winner = candidates[0]
        reasons.append(DecisionReason.UNIQUE_CANDIDATE)
    elif policy.keeper_preference == "first":
        winner = candidates[0]
        reasons.append(DecisionReason.EXPLICIT_FIRST_RESULT)
    elif any(member.uploaded_at is None for member in candidates):
        reasons.extend(
            (
                DecisionReason.MISSING_UPLOAD_TIMESTAMP,
                DecisionReason.MULTIPLE_EQUAL_CANDIDATES,
            )
        )
    else:
        newest = max(member.uploaded_at for member in candidates if member.uploaded_at)
        latest = [member for member in candidates if member.uploaded_at == newest]
        if len(latest) == 1:
            winner = latest[0]
            reasons.append(DecisionReason.MOST_RECENT_UPLOAD)
        else:
            reasons.append(DecisionReason.MULTIPLE_EQUAL_CANDIDATES)

    recommended_action = (
        GroupAction.NONE
        if policy.exact_file_action == "review"
        else GroupAction(policy.exact_file_action)
    )
    primary_required = recommended_action in {GroupAction.RESOLVE, GroupAction.STACK_ALL}
    auto_resolvable = (
        recommended_action is not GroupAction.NONE
        and policy.automatic_handling
        and (winner is not None or not primary_required)
        and (
            recommended_action is not GroupAction.STACK_ALL
            or all(member.available for member in group.members)
        )
    )
    auto_selected = auto_resolvable and policy.preselect_safe_groups
    return GroupDecision(
        recommended_action=recommended_action,
        recommended_primary_asset_id=winner.asset_id if winner else None,
        recommendation_reason_codes=tuple(reasons),
        auto_resolvable=auto_resolvable,
        auto_selected=auto_selected,
        action_source=(
            DecisionSource.AUTOMATIC
            if recommended_action is not GroupAction.NONE
            else DecisionSource.NONE
        ),
        primary_source=(DecisionSource.AUTOMATIC if winner else DecisionSource.NONE),
    )

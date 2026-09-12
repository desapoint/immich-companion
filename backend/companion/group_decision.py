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
    SOURCE_PRIORITY = "source_priority"
    PREFERRED_FAVORITE = "preferred_favorite"
    LARGEST_RESOLUTION = "largest_resolution"
    RICHEST_METADATA = "richest_metadata"
    LARGEST_FILE = "largest_file"
    OLDEST_CAPTURE = "oldest_capture"


@dataclass(frozen=True, slots=True)
class CandidateMember:
    asset_id: UUID
    source_kind: Literal["upload", "external"]
    uploaded_at: datetime | None
    available: bool = True
    library_id: UUID | None = None
    is_favorite: bool = False
    width: int | None = None
    height: int | None = None
    file_size_bytes: int | None = None
    metadata_richness: int | None = None
    captured_at: datetime | None = None


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
    source_priority: tuple[str, ...] = ()
    keeper_tiebreakers: tuple[
        Literal[
            "favorite",
            "resolution",
            "metadata_richness",
            "file_size",
            "oldest_capture",
            "uploaded_at",
        ],
        ...,
    ] = ()


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

    if policy.source_priority:
        ranks = {source: rank for rank, source in enumerate(policy.source_priority)}

        def source_rank(member: CandidateMember) -> int:
            source = str(member.library_id) if member.library_id is not None else "immich_uploads"
            return ranks.get(source, ranks.get("unlisted", len(ranks)))

        best_rank = min(source_rank(member) for member in candidates)
        preferred = [member for member in candidates if source_rank(member) == best_rank]
        if len(preferred) < len(candidates):
            candidates = preferred
            reasons.append(DecisionReason.SOURCE_PRIORITY)
    elif policy.keeper_preference == "prefer_upload":
        preferred = [member for member in candidates if member.source_kind == "upload"]
        if preferred:
            candidates = preferred
            reasons.append(DecisionReason.PREFERRED_UPLOAD)
    elif policy.keeper_preference == "prefer_external":
        preferred = [member for member in candidates if member.source_kind == "external"]
        if preferred:
            candidates = preferred
            reasons.append(DecisionReason.PREFERRED_EXTERNAL)

    tiebreakers = {
        "favorite": (
            lambda member: int(member.is_favorite),
            DecisionReason.PREFERRED_FAVORITE,
        ),
        "resolution": (
            lambda member: (
                member.width * member.height
                if member.width is not None and member.height is not None
                else None
            ),
            DecisionReason.LARGEST_RESOLUTION,
        ),
        "metadata_richness": (
            lambda member: member.metadata_richness,
            DecisionReason.RICHEST_METADATA,
        ),
        "file_size": (
            lambda member: member.file_size_bytes,
            DecisionReason.LARGEST_FILE,
        ),
        "oldest_capture": (
            lambda member: (
                -member.captured_at.timestamp() if member.captured_at is not None else None
            ),
            DecisionReason.OLDEST_CAPTURE,
        ),
        "uploaded_at": (
            lambda member: (
                member.uploaded_at.timestamp() if member.uploaded_at is not None else None
            ),
            DecisionReason.MOST_RECENT_UPLOAD,
        ),
    }
    for name in policy.keeper_tiebreakers:
        if len(candidates) == 1:
            break
        value_for, reason = tiebreakers[name]
        known = [(member, value_for(member)) for member in candidates]
        values = [value for _, value in known if value is not None]
        if not values:
            continue
        best = max(values)
        preferred = [member for member, value in known if value == best]
        if len(preferred) < len(candidates):
            candidates = preferred
            reasons.append(reason)

    winner: CandidateMember | None = None
    if len(candidates) == 1:
        winner = candidates[0]
        reasons.append(DecisionReason.UNIQUE_CANDIDATE)
    elif policy.keeper_tiebreakers:
        reasons.append(DecisionReason.MULTIPLE_EQUAL_CANDIDATES)
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

"""Pure unique-winner behavior for Immich duplicate candidates."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from companion.group_decision import (
    CandidateGroup,
    CandidateMember,
    DecisionReason,
    DiscoverySource,
    GroupAction,
    GroupClassification,
    ResolutionPolicy,
    decide_group,
)

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 8, 29, tzinfo=UTC)


def candidate(
    identifier: UUID,
    source: str,
    uploaded_at: datetime | None = NOW,
) -> CandidateMember:
    return CandidateMember(
        asset_id=identifier,
        source_kind=source,  # type: ignore[arg-type]
        uploaded_at=uploaded_at,
    )


def exact(*members: CandidateMember) -> CandidateGroup:
    return CandidateGroup(
        group_id="immich:test",
        discovery_source=DiscoverySource.IMMICH_DUPLICATE,
        provider_group_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        classification=GroupClassification.EXACT_FILE,
        members=members,
    )


def test_one_preferred_source_is_the_unique_winner() -> None:
    decision = decide_group(
        exact(candidate(A, "upload"), candidate(B, "external")),
        ResolutionPolicy(keeper_preference="prefer_upload"),
    )

    assert decision.recommended_action is GroupAction.RESOLVE
    assert decision.recommended_primary_asset_id == A
    assert decision.auto_selected is True
    assert DecisionReason.PREFERRED_UPLOAD in decision.recommendation_reason_codes


def test_uniquely_newest_preferred_candidate_wins() -> None:
    decision = decide_group(
        exact(candidate(A, "upload", NOW), candidate(B, "upload", NOW + timedelta(seconds=1))),
        ResolutionPolicy(keeper_preference="prefer_upload"),
    )

    assert decision.recommended_primary_asset_id == B
    assert DecisionReason.MOST_RECENT_UPLOAD in decision.recommendation_reason_codes


def test_default_recency_policy_compares_across_sources() -> None:
    decision = decide_group(
        exact(
            candidate(A, "upload", NOW),
            candidate(B, "external", NOW + timedelta(seconds=1)),
        ),
        ResolutionPolicy(keeper_preference="most_recent"),
    )

    assert decision.recommended_primary_asset_id == B


def test_equal_candidates_do_not_fall_back_to_list_order() -> None:
    decision = decide_group(
        exact(candidate(A, "upload"), candidate(B, "upload")),
        ResolutionPolicy(keeper_preference="prefer_upload"),
    )

    assert decision.recommended_primary_asset_id is None
    assert decision.auto_resolvable is False
    assert decision.auto_selected is False
    assert DecisionReason.MULTIPLE_EQUAL_CANDIDATES in decision.recommendation_reason_codes


def test_missing_recency_is_ambiguous() -> None:
    decision = decide_group(
        exact(candidate(A, "external", None), candidate(B, "external", NOW)),
        ResolutionPolicy(keeper_preference="prefer_upload"),
    )

    assert decision.recommended_primary_asset_id is None
    assert DecisionReason.MISSING_UPLOAD_TIMESTAMP in decision.recommendation_reason_codes


def test_explicit_first_policy_is_the_only_list_order_tiebreaker() -> None:
    decision = decide_group(
        exact(candidate(A, "upload"), candidate(B, "upload")),
        ResolutionPolicy(keeper_preference="first"),
    )

    assert decision.recommended_primary_asset_id == A
    assert DecisionReason.EXPLICIT_FIRST_RESULT in decision.recommendation_reason_codes


def test_non_exact_group_never_auto_selects() -> None:
    group = exact(candidate(A, "upload"), candidate(B, "external"))
    decision = decide_group(
        CandidateGroup(
            group_id=group.group_id,
            discovery_source=group.discovery_source,
            provider_group_id=group.provider_group_id,
            classification=GroupClassification.SIMILAR,
            members=group.members,
        ),
        ResolutionPolicy(keeper_preference="prefer_upload"),
    )

    assert decision.recommended_action is GroupAction.NONE
    assert decision.recommended_primary_asset_id is None
    assert decision.auto_selected is False
    assert DecisionReason.NON_EXACT_MATCH in decision.recommendation_reason_codes


def test_content_mismatch_has_an_accurate_reason() -> None:
    base = exact(candidate(A, "upload"), candidate(B, "external"))
    decision = decide_group(
        CandidateGroup(
            group_id=base.group_id,
            discovery_source=base.discovery_source,
            provider_group_id=base.provider_group_id,
            classification=GroupClassification.MISMATCH,
            members=base.members,
        ),
        ResolutionPolicy(keeper_preference="most_recent"),
    )

    assert decision.recommendation_reason_codes == (DecisionReason.CONTENT_MISMATCH,)

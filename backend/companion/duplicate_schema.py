"""Typed contracts for exact duplicate review and resolution."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from companion.integrity import DetectedFormat, IntegrityClassification
from companion.integrity_schema import IntegrityFreshness

DuplicateKeeperPolicy = Literal["most_recent", "prefer_upload", "prefer_external", "first"]
DuplicateExactFilePolicyAction = Literal["resolve", "keep_all", "stack_all", "review"]
DuplicateGroupStatus = Literal["exact", "unverified", "mismatch", "ineligible"]
DuplicateMemberStatus = Literal["matching", "mismatch", "unverified"]
DuplicateDiscoverySource = Literal["immich_duplicate", "companion_similarity"]
DuplicateClassification = Literal[
    "exact_file",
    "exact_pixels",
    "likely_same",
    "similar",
    "mismatch",
    "unverified",
    "unavailable",
    "ineligible",
]
DuplicateGroupAction = Literal["resolve", "keep_all", "delete_all", "stack_all", "none"]
DuplicateDecisionSource = Literal["automatic", "manual", "none"]
DuplicateReviewStatus = Literal[
    "pending",
    "manually_configured",
    "reviewed_keep_all",
    "reviewed_resolve",
    "reviewed_delete_all",
    "reviewed_stack_all",
    "review_later",
    "drifted",
]
DuplicateMemberDisposition = Literal["keep", "delete", "stack", "no_change"]
DuplicateDraftDisposition = Literal["keep", "delete", "stack"]
DuplicateDraftDecisionSource = Literal["manual", "automatic"]
DuplicateDraftDecisionStatus = Literal["pending", "completed"]
DuplicateDraftStatus = Literal["pending", "completed"]
DuplicateGroupExecutionState = Literal[
    "pending",
    "duplicate_resolved",
    "follow_up_pending",
    "completed",
    "failed",
    "drifted",
]


class DuplicateAnalysisOptions(BaseModel):
    """Filters and keeper rule shared by analysis, review, and planning."""

    keeper_policy: DuplicateKeeperPolicy = "most_recent"
    external_library_ids: list[UUID] = Field(default_factory=list, max_length=10_000)
    verify_upload_streams: bool = False
    automatic_handling_enabled: bool = True
    preselect_safe_groups: bool = True
    exact_file_action: DuplicateExactFilePolicyAction = "resolve"
    analyze_automatically: bool = True

    @model_validator(mode="after")
    def unique_libraries(self) -> DuplicateAnalysisOptions:
        self.external_library_ids = list(dict.fromkeys(self.external_library_ids))
        return self


class DuplicateMemberEvidence(BaseModel):
    analysis_freshness: IntegrityFreshness
    integrity_status: IntegrityClassification | None = None
    issue_codes: list[str] = Field(default_factory=list)
    detected_format: DetectedFormat | None = None
    format_matches_declared: bool | None = None
    decode_supported: bool | None = None
    decode_valid: bool | None = None
    decoded_width: int | None = None
    decoded_height: int | None = None
    dimensions_match_immich: bool | None = None


class DuplicateSimilarityEvidence(BaseModel):
    state: Literal["reference", "current", "pending", "unavailable"]
    reference_asset_id: UUID
    similarity_percent: float | None = None
    structural_percent: float | None = None
    perceptual_percent: float | None = None
    color_percent: float | None = None
    normalized_luminance_mae: float | None = None
    normalized_luminance_rmse: float | None = None
    normalized_luminance_ssim: float | None = None
    aspect_ratio_difference: float | None = None
    dimensions_equal: bool | None = None
    exact_thumbnail_match: bool | None = None
    exact_pixel_match: bool | None = None
    model_version: str | None = None
    feature_version: int | None = None
    comparison_version: int | None = None


class DuplicatePreservationEvidence(BaseModel):
    pixel_normalization_version: int
    pixel_sha256: str
    decoded_width: int
    decoded_height: int
    bit_depth: int
    channel_count: int
    has_alpha: bool
    color_space: str
    orientation: int | None
    icc_profile_present: bool
    has_exif: bool
    has_capture_time: bool
    has_camera_info: bool
    has_gps: bool
    has_orientation_metadata: bool
    metadata_richness: int


class DuplicateMember(BaseModel):
    id: UUID
    source_kind: Literal["upload", "external"]
    library_id: UUID | None
    original_file_name: str
    original_mime_type: str | None
    file_size_bytes: int | None
    file_modified_at: datetime
    uploaded_at: datetime | None = None
    is_offline: bool
    is_stacked: bool
    immich_url: str | None = None
    verification: DuplicateMemberStatus
    content_checksum: str | None = None
    evidence: DuplicateMemberEvidence
    similarity: DuplicateSimilarityEvidence | None = None
    preservation: DuplicatePreservationEvidence | None = None


class ExactDuplicateGroup(BaseModel):
    group_id: str
    discovery_source: DuplicateDiscoverySource
    provider_group_id: str | None = None
    discovery_metadata: dict[str, str] = Field(default_factory=dict)
    classification: DuplicateClassification
    status: DuplicateGroupStatus
    reason: str | None = None
    keeper_asset_id: UUID | None = None
    recommended_action: DuplicateGroupAction
    recommended_primary_asset_id: UUID | None = None
    recommendation_reason_codes: list[str] = Field(default_factory=list)
    auto_resolvable: bool = False
    auto_selected: bool = False
    action_source: DuplicateDecisionSource = "none"
    primary_source: DuplicateDecisionSource = "none"
    manual_action: DuplicateGroupAction | None = None
    manual_primary_asset_id: UUID | None = None
    effective_action: DuplicateGroupAction = "none"
    effective_primary_asset_id: UUID | None = None
    review_status: DuplicateReviewStatus = "pending"
    member_fingerprint: str
    members: list[DuplicateMember]
    eligible: bool


class CrossSourceDuplicateResult(BaseModel):
    generated_at: datetime
    analysis_task_id: UUID | None = None
    analysis_pending_count: int = 0
    analysis_candidate_count: int = 0
    analysis_cached_count: int = 0
    group_count: int
    exact_group_count: int
    unverified_group_count: int
    mismatch_group_count: int
    ineligible_group_count: int
    groups: list[ExactDuplicateGroup]


class CrossSourceDuplicateTaskStart(BaseModel):
    task_id: UUID


class SimilarityScanRequest(BaseModel):
    similarity_threshold: float = Field(default=95.0, ge=50, le=100)
    scope: Literal["all_eligible_assets"] = "all_eligible_assets"
    maximum_perceptual_distance: int = Field(default=12, ge=0, le=64)
    maximum_aspect_difference: float = Field(default=0.05, ge=0, le=1)
    maximum_neighbors_per_asset: int = Field(default=8, ge=1, le=64)
    maximum_matches: int = Field(default=5000, ge=1, le=50_000)


class SimilarityScanTaskStart(BaseModel):
    task_id: UUID


class SimilarityScanSummary(BaseModel):
    scan_id: UUID
    similarity_threshold: float
    scope: Literal["all_eligible_assets"]
    model_version: str
    feature_version: int
    comparison_version: int
    asset_count: int
    candidate_count: int
    match_count: int
    completed_at: datetime


class DuplicateResolutionPlanRequest(BaseModel):
    options: DuplicateAnalysisOptions = Field(default_factory=DuplicateAnalysisOptions)
    group_ids: list[str] = Field(default_factory=list, max_length=10_000)
    all_eligible: bool = False
    keeper_overrides: dict[str, UUID] = Field(default_factory=dict)
    action_overrides: dict[
        str,
        Literal["resolve", "keep_all", "delete_all", "stack_all"],
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_selection(self) -> DuplicateResolutionPlanRequest:
        self.group_ids = list(dict.fromkeys(self.group_ids))
        if self.all_eligible == bool(self.group_ids):
            raise ValueError("Choose explicit duplicate groups or all eligible groups")
        return self


class DuplicatePlanMember(BaseModel):
    asset_id: UUID
    disposition: DuplicateMemberDisposition
    primary: bool = False


class DuplicatePlanFollowUp(BaseModel):
    type: Literal["stack"]
    primary_asset_id: UUID
    member_asset_ids: list[UUID]


class DuplicateResolutionPlanGroup(BaseModel):
    group_id: str
    discovery_source: DuplicateDiscoverySource
    provider_group_id: str | None = None
    action: Literal["resolve", "keep_all", "delete_all", "stack_all"] = "resolve"
    keeper_asset_id: UUID | None = None
    member_asset_ids: list[UUID] = Field(default_factory=list)
    keep_asset_ids: list[UUID] = Field(default_factory=list)
    trash_asset_ids: list[UUID]
    follow_up: DuplicatePlanFollowUp | None = None
    execution_state: DuplicateGroupExecutionState = "pending"
    member_fingerprint: str
    members: list[DuplicatePlanMember]

    @model_validator(mode="after")
    def validate_resolution_partition(self) -> DuplicateResolutionPlanGroup:
        members = set(self.member_asset_ids)
        keep = set(self.keep_asset_ids)
        trash = set(self.trash_asset_ids)
        if keep & trash or keep | trash != members:
            raise ValueError("Duplicate resolution must classify every frozen member exactly once")
        if len(keep) != len(self.keep_asset_ids) or len(trash) != len(self.trash_asset_ids):
            raise ValueError("Duplicate resolution member lists must not contain duplicates")
        if self.action == "stack_all" and self.follow_up is None:
            raise ValueError("Stack all requires an explicit stack follow-up")
        if self.action != "stack_all" and self.follow_up is not None:
            raise ValueError("Only Stack all may include a stack follow-up")
        return self


class DuplicateResolutionPlan(BaseModel):
    id: UUID
    status: Literal["planned", "running", "completed", "failed", "drifted", "expired"]
    groups: list[DuplicateResolutionPlanGroup]
    group_count: int
    resolve_group_count: int = 0
    keep_all_group_count: int = 0
    delete_all_group_count: int = 0
    stack_group_count: int = 0
    trash_asset_count: int
    retained_asset_count: int = 0
    zero_survivor_group_count: int = 0
    expires_at: datetime
    destructive: bool = True


class DuplicateResolutionExecuteRequest(BaseModel):
    plan_id: UUID


class DuplicateReviewUpdate(BaseModel):
    group_id: str
    options: DuplicateAnalysisOptions = Field(default_factory=DuplicateAnalysisOptions)
    manual_action: DuplicateGroupAction | None
    manual_primary_asset_id: UUID | None = None


class DuplicateMemberDraftDecision(BaseModel):
    asset_id: UUID
    disposition: DuplicateDraftDisposition
    source: DuplicateDraftDecisionSource = "manual"
    status: DuplicateDraftDecisionStatus = "pending"


class DuplicateGroupDraftUpdate(BaseModel):
    group_id: str
    member_fingerprint: str
    options: DuplicateAnalysisOptions = Field(default_factory=DuplicateAnalysisOptions)
    decisions: list[DuplicateMemberDraftDecision] = Field(default_factory=list)
    stack_primary_asset_id: UUID | None = None
    metadata_keeper_asset_id: UUID | None = None
    status: DuplicateDraftStatus = "pending"

    @model_validator(mode="after")
    def unique_members(self) -> DuplicateGroupDraftUpdate:
        ids = [decision.asset_id for decision in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("A duplicate member can have only one draft decision")
        return self


class DuplicateWorkspaceGroupReference(BaseModel):
    group_id: str
    discovery_source: DuplicateDiscoverySource
    member_fingerprint: str


class DuplicateWorkspaceSelectionUpdate(BaseModel):
    options: DuplicateAnalysisOptions = Field(default_factory=DuplicateAnalysisOptions)
    selected_group_ids: list[str] = Field(default_factory=list, max_length=10_000)
    active_group_id: str | None = None

    @model_validator(mode="after")
    def unique_groups(self) -> DuplicateWorkspaceSelectionUpdate:
        self.selected_group_ids = list(dict.fromkeys(self.selected_group_ids))
        return self


class DuplicateGroupDraft(BaseModel):
    group_id: str
    discovery_source: DuplicateDiscoverySource
    member_fingerprint: str
    decisions: list[DuplicateMemberDraftDecision]
    stack_primary_asset_id: UUID | None = None
    metadata_keeper_asset_id: UUID | None = None
    status: DuplicateDraftStatus
    stale: bool = False


class DuplicateWorkspaceState(BaseModel):
    initialized: bool = False
    selected_group_ids: list[str] = Field(default_factory=list)
    active_group_id: str | None = None
    stale_selected_groups: list[DuplicateWorkspaceGroupReference] = Field(default_factory=list)
    drafts: list[DuplicateGroupDraft] = Field(default_factory=list)


class DuplicateSimilarityReferenceRequest(BaseModel):
    reference_asset_id: UUID

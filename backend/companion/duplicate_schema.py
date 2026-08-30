"""Typed contracts for exact duplicate review and resolution."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

DuplicateKeeperPolicy = Literal["most_recent", "prefer_upload", "prefer_external", "first"]
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


class DuplicateAnalysisOptions(BaseModel):
    """Filters and keeper rule shared by analysis, review, and planning."""

    keeper_policy: DuplicateKeeperPolicy = "most_recent"
    external_library_ids: list[UUID] = Field(default_factory=list, max_length=10_000)
    verify_upload_streams: bool = False

    @model_validator(mode="after")
    def unique_libraries(self) -> DuplicateAnalysisOptions:
        self.external_library_ids = list(dict.fromkeys(self.external_library_ids))
        return self


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
    immich_url: str | None = None
    verification: DuplicateMemberStatus
    content_checksum: str | None = None


class ExactDuplicateGroup(BaseModel):
    duplicate_id: UUID
    group_id: str
    discovery_source: DuplicateDiscoverySource
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
    members: list[DuplicateMember]
    eligible: bool


class CrossSourceDuplicateResult(BaseModel):
    generated_at: datetime
    group_count: int
    exact_group_count: int
    unverified_group_count: int
    mismatch_group_count: int
    ineligible_group_count: int
    groups: list[ExactDuplicateGroup]


class CrossSourceDuplicateTaskStart(BaseModel):
    task_id: UUID


class DuplicateResolutionPlanRequest(BaseModel):
    options: DuplicateAnalysisOptions = Field(default_factory=DuplicateAnalysisOptions)
    duplicate_ids: list[UUID] = Field(default_factory=list, max_length=10_000)
    all_eligible: bool = False
    keeper_overrides: dict[UUID, UUID] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_selection(self) -> DuplicateResolutionPlanRequest:
        self.duplicate_ids = list(dict.fromkeys(self.duplicate_ids))
        if self.all_eligible == bool(self.duplicate_ids):
            raise ValueError("Choose explicit duplicate groups or all eligible groups")
        return self


class DuplicateResolutionPlanGroup(BaseModel):
    duplicate_id: UUID
    keeper_asset_id: UUID
    trash_asset_ids: list[UUID]


class DuplicateResolutionPlan(BaseModel):
    id: UUID
    status: Literal["planned", "running", "completed", "failed", "drifted", "expired"]
    groups: list[DuplicateResolutionPlanGroup]
    group_count: int
    trash_asset_count: int
    expires_at: datetime
    destructive: bool = True


class DuplicateResolutionExecuteRequest(BaseModel):
    plan_id: UUID

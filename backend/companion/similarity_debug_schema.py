"""Typed contracts for read-only arbitrary similarity diagnostics."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SimilarityDebugRequest(BaseModel):
    """Compare a small explicit asset set without candidate/group discovery restrictions."""

    asset_ids: list[UUID] = Field(min_length=2, max_length=12)
    similarity_threshold: float = Field(default=95.0, ge=50, le=100)
    validation_mode: Literal["reference", "linked", "strict"] = "strict"
    max_link_depth: int = Field(default=2, ge=0, le=64)
    anchor_asset_id: UUID | None = None
    maximum_perceptual_distance: int = Field(default=12, ge=0, le=64)
    maximum_aspect_difference: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def normalize_assets(self) -> "SimilarityDebugRequest":
        self.asset_ids = list(dict.fromkeys(self.asset_ids))
        if len(self.asset_ids) < 2:
            raise ValueError("Choose at least two distinct assets to compare")
        if self.anchor_asset_id is not None and self.anchor_asset_id not in self.asset_ids:
            raise ValueError("The debug anchor must be one of the selected assets")
        return self


class SimilarityDebugAsset(BaseModel):
    asset_id: UUID
    evidence_state: Literal["current", "unavailable", "missing_or_stale"]
    reason: str | None = None
    width: int | None = None
    height: int | None = None
    fingerprint_origin: str | None = None
    model_version: str | None = None
    feature_version: int | None = None
    config_fingerprint: str | None = None


class SimilarityDebugLocalDiagnostics(BaseModel):
    changed_percent: float
    localized_changed_percent: float
    coherent_changed_percent: float
    largest_changed_region_percent: float
    substantial_region_count: int
    aligned_changed_percent: float
    raw_similarity_percent: float
    aligned_similarity_percent: float
    alignment_applied: bool
    alignment_shift_percent: float
    alignment_overlap_percent: float
    rows: int
    columns: int
    cells: list[list[float]]
    source: Literal["original", "transcoded", "preview"]


class SimilarityDebugPair(BaseModel):
    asset_id_left: UUID
    asset_id_right: UUID
    evidence_available: bool
    perceptual_distance: int | None = Field(default=None, ge=0, le=64)
    maximum_perceptual_distance: int = Field(ge=0, le=64)
    perceptual_gate_pass: bool
    aspect_ratio_difference: float | None = Field(default=None, ge=0)
    maximum_aspect_difference: float = Field(ge=0, le=1)
    aspect_gate_pass: bool
    candidate_pair_pass: bool
    neighbor_allocation_simulated: bool = False
    similarity_percent: float | None = Field(default=None, ge=0, le=100)
    structural_percent: float | None = Field(default=None, ge=0, le=100)
    perceptual_percent: float | None = Field(default=None, ge=0, le=100)
    color_percent: float | None = Field(default=None, ge=0, le=100)
    normalized_luminance_mae: float | None = None
    normalized_luminance_rmse: float | None = None
    normalized_luminance_ssim: float | None = None
    dimensions_equal: bool | None = None
    exact_thumbnail_match: bool | None = None
    detail_changed_percent: float | None = Field(default=None, ge=0, le=100)
    detail_source: Literal["original", "transcoded", "preview"] | None = None
    similarity_threshold: float = Field(ge=50, le=100)
    similarity_threshold_pass: bool
    would_pass_pair_pipeline: bool
    exclusion_reason: str | None = None
    local_diagnostics: SimilarityDebugLocalDiagnostics | None = None
    model_version: str | None = None
    feature_version: int | None = None
    comparison_version: int | None = None


class SimilarityDebugAdmission(BaseModel):
    asset_id: UUID
    admitted_by_asset_id: UUID | None = None
    admission_similarity_percent: float | None = None
    best_group_match_asset_id: UUID | None = None
    best_group_match_similarity_percent: float | None = None
    link_depth: int = Field(ge=0)


class SimilarityDebugGroup(BaseModel):
    asset_ids: list[UUID]
    anchor_asset_id: UUID
    validation_mode: Literal["reference", "linked", "strict"]
    minimum_similarity_percent: float
    maximum_similarity_percent: float
    pair_count: int = Field(ge=0)
    admission_evidence: list[SimilarityDebugAdmission]


class SimilarityDebugResponse(BaseModel):
    assets: list[SimilarityDebugAsset]
    pairs: list[SimilarityDebugPair]
    groups: list[SimilarityDebugGroup]
    neighbor_allocation_simulated: bool = False
    note: str

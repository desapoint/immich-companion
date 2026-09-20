"""API schemas for read-only similarity detail diagnostics and evidence generation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SimilarityLocalDiagnosticsResponse(BaseModel):
    """Explain localized detail evidence for one selected/reference pair."""

    available: bool
    selected_asset_id: UUID
    reference_asset_id: UUID
    changed_percent: float | None = Field(default=None, ge=0, le=100)
    localized_changed_percent: float | None = Field(default=None, ge=0, le=100)
    coherent_changed_percent: float | None = Field(default=None, ge=0, le=100)
    largest_changed_region_percent: float | None = Field(default=None, ge=0, le=100)
    substantial_region_count: int | None = Field(default=None, ge=0)
    aligned_changed_percent: float | None = Field(default=None, ge=0, le=100)
    raw_similarity_percent: float | None = Field(default=None, ge=0, le=100)
    aligned_similarity_percent: float | None = Field(default=None, ge=0, le=100)
    alignment_applied: bool = False
    alignment_shift_percent: float | None = Field(default=None, ge=0, le=100)
    alignment_overlap_percent: float | None = Field(default=None, ge=0, le=100)
    rows: int = Field(default=0, ge=0)
    columns: int = Field(default=0, ge=0)
    cells: list[list[float]] = Field(default_factory=list)
    source: Literal["original", "transcoded", "preview"] | None = None


class SimilarityEvidenceGenerationResponse(BaseModel):
    """Current persisted runtime epoch and code-generation compatibility state."""

    epoch: int = Field(ge=1)
    code_generation: int = Field(ge=1)
    recorded_descriptor_fingerprint: str
    current_descriptor_fingerprint: str
    descriptor_current: bool
    rebuilt_at: datetime | None = None


class SimilarityEvidenceDestroyResponse(BaseModel):
    """Destructive generation invalidation without replacement scan submission."""

    task_id: UUID | None = None
    generation: SimilarityEvidenceGenerationResponse | None = None
    cancelled_task_count: int = Field(default=0, ge=0)
    removed_counts: dict[str, int] = Field(default_factory=dict)


class SimilarityEvidenceRebuildResponse(SimilarityEvidenceDestroyResponse):
    """Atomic invalidation plus the durable replacement similarity-scan task."""

    task_id: UUID

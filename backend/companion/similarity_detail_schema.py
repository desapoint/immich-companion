"""API schemas for read-only similarity detail diagnostics."""

from __future__ import annotations

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
    rows: int = Field(default=0, ge=0)
    columns: int = Field(default=0, ge=0)
    cells: list[list[float]] = Field(default_factory=list)
    source: Literal["original", "transcoded", "preview"] | None = None

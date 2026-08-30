"""Typed API contracts for current file-integrity analysis."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from companion.integrity import DetectedFormat, IntegrityClassification

IntegrityFreshness = Literal["current", "stale", "missing"]
IntegrityAnalysisState = Literal["ready", "pending"]


class AssetIntegrityReport(BaseModel):
    asset_id: UUID
    analyzer_version: int
    byte_size: int
    sha1_hex: str
    sha256_hex: str
    detected_format: DetectedFormat
    format_matches_declared: bool | None
    classification: IntegrityClassification
    structurally_valid: bool | None
    container_valid: bool | None
    decode_supported: bool
    decode_valid: bool | None
    jpeg_eoi_offset: int | None
    trailing_byte_count: int
    immich_checksum_match: bool | None
    issues: list[str]
    analyzed_at: datetime


class AssetIntegrityState(BaseModel):
    freshness: IntegrityFreshness
    report: AssetIntegrityReport | None = None
    active_task_id: UUID | None = None


class AssetIntegrityAnalyzeRequest(BaseModel):
    force: bool = False


class AssetIntegrityAnalyzeResponse(BaseModel):
    state: IntegrityAnalysisState
    freshness: IntegrityFreshness
    report: AssetIntegrityReport | None = None
    task_id: UUID | None = None

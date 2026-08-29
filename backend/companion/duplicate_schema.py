"""Typed contracts for upload/external exact-content comparison."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

CrossSourceUnverifiedReason = Literal[
    "content_hash_missing",
    "content_hash_stale",
    "external_file_unavailable",
    "upload_checksum_unavailable",
]


class CrossSourceDuplicateGroup(BaseModel):
    content_checksum: str
    checksum_algorithm: Literal["sha1"] = "sha1"
    upload_asset_ids: list[UUID]
    external_asset_ids: list[UUID]


class CrossSourceUnverifiedCandidate(BaseModel):
    external_asset_id: UUID
    upload_asset_ids: list[UUID]
    reason: CrossSourceUnverifiedReason


class CrossSourceDuplicateResult(BaseModel):
    generated_at: datetime
    candidate_asset_count: int
    candidate_external_count: int
    verified_external_count: int
    verified_non_match_count: int
    confirmed_groups: list[CrossSourceDuplicateGroup]
    unverified_candidates: list[CrossSourceUnverifiedCandidate]


class CrossSourceDuplicateTaskStart(BaseModel):
    task_id: UUID

"""Durable provenance and unavailable state for bounded similarity evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from companion.evidence_logging import install_pending_evidence_logging_policy
from companion.image_decode import MAX_DECODED_PIXELS
from companion.immich import ImmichAsset
from companion.models import Base
from companion.similarity_search_features import (
    MAX_SEARCH_PREVIEW_BYTES,
    SEARCH_CONFIG_FINGERPRINT,
    SEARCH_FEATURE_VERSION,
    SEARCH_MODEL_VERSION,
)

SourceAlphaState = Literal["confirmed_opaque", "confirmed_alpha", "unknown_alpha"]
SearchAvailability = Literal["available", "unavailable"]
DetailAvailability = Literal["unavailable"]

# Freshness gaps are expected while evidence is being generated. Install the
# narrow logging policy before any similarity/integrity freshness checks run.
install_pending_evidence_logging_policy()

# Bump this whenever decoder/rendition/transparency handling changes in a way
# that could make previously unavailable bounded evidence usable.
BOUNDED_CAPABILITY_VERSION = 2
BOUNDED_POLICY_FINGERPRINT = hashlib.sha256(
    (
        f"bounded-v{BOUNDED_CAPABILITY_VERSION}:"
        f"search={SEARCH_CONFIG_FINGERPRINT}:"
        f"pixels={MAX_DECODED_PIXELS}:preview-bytes={MAX_SEARCH_PREVIEW_BYTES}"
    ).encode(),
    usedforsecurity=False,
).hexdigest()


class AssetSimilarityBoundedStateRecord(Base):
    """Source-scoped bounded evidence state, including deterministic failures."""

    __tablename__ = "asset_similarity_bounded_state"

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_version: Mapped[int] = mapped_column(Integer, nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    alpha_state: Mapped[str] = mapped_column(String(24), nullable=False)
    search_status: Mapped[str] = mapped_column(String(16), nullable=False)
    search_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    detail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_source_identity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail_feature_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def synchronized_source_identity(asset: ImmichAsset) -> str:
    """Identify the synchronized source without reading or decoding original bytes."""

    payload = json.dumps(
        {
            "asset_id": str(asset.id),
            "modified_at": asset.file_modified_at.isoformat(),
            "file_size": asset.file_size_bytes,
            "checksum": asset.checksum,
            "width": asset.width,
            "height": asset.height,
            "mime": asset.original_mime_type,
            "name": asset.original_file_name,
            "model": SEARCH_MODEL_VERSION,
            "feature": SEARCH_FEATURE_VERSION,
            "config": SEARCH_CONFIG_FINGERPRINT,
            "policy": BOUNDED_POLICY_FINGERPRINT,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()

"""Preview-derived, non-verifying search fingerprints for the whole library."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO

from companion.immich import ImmichAsset
from companion.similarity_features import (
    SIMILARITY_CONFIG_FINGERPRINT,
    VisualFeatureResult,
    extract_visual_features,
)

SEARCH_MODEL_VERSION = "appearance-preview-v1"
SEARCH_FEATURE_VERSION = 1
MAX_SEARCH_PREVIEW_BYTES = 16 * 1024 * 1024
SEARCH_CONFIG_FINGERPRINT = hashlib.sha256(
    f"preview-search-v1:{SIMILARITY_CONFIG_FINGERPRINT}".encode(),
    usedforsecurity=False,
).hexdigest()


def extract_search_feature(preview: bytes) -> VisualFeatureResult | None:
    """Decode a bounded Immich-generated preview without normalized-pixel hashing."""

    if not preview or len(preview) > MAX_SEARCH_PREVIEW_BYTES:
        return None
    # Pillow recognizes the encoded preview format; the JPEG hint only disables
    # the original-only TIFF/RAW fallback for generated media.
    return extract_visual_features(BytesIO(preview), "jpeg", include_pixel_hash=False)


def search_source_identity(asset: ImmichAsset, preview_sha256: str) -> str:
    """Versioned cache identity, explicitly not a SHA of the original file."""

    payload = json.dumps(
        {
            "asset_id": str(asset.id),
            "modified_at": asset.file_modified_at.isoformat(),
            "file_size": asset.file_size_bytes,
            "checksum": asset.checksum,
            "preview_sha256": preview_sha256,
            "config": SEARCH_CONFIG_FINGERPRINT,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()

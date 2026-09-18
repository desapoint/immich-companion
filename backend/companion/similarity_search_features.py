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
from companion.similarity_generation import SIMILARITY_EVIDENCE_CODE_GENERATION
from companion.similarity_visual_normalization import VISUAL_NORMALIZATION_FINGERPRINT

SEARCH_MODEL_VERSION = "appearance-normalized-v1"
SEARCH_FEATURE_VERSION = 4
SEARCH_CONFIG_FINGERPRINT = hashlib.sha256(
    (
        f"normalized-search-v4:generation={SIMILARITY_EVIDENCE_CODE_GENERATION}:"
        f"visual={VISUAL_NORMALIZATION_FINGERPRINT}:"
        f"{SIMILARITY_CONFIG_FINGERPRINT}"
    ).encode(),
    usedforsecurity=False,
).hexdigest()


def extract_search_feature(
    preview: bytes, *, timings: dict[str, int] | None = None
) -> VisualFeatureResult | None:
    """Decode the canonical normalized visual image without exact-pixel hashing."""

    if not preview:
        return None
    # Pillow recognizes the encoded preview format; the JPEG hint only disables
    # the original-only TIFF/RAW fallback for generated media.
    return extract_visual_features(
        BytesIO(preview), "jpeg", include_pixel_hash=False, timings=timings
    )


def search_source_identity(
    asset: ImmichAsset, media_sha256: str, *, origin: str = "preview"
) -> str:
    """Versioned cache identity, explicitly not original-file or pixel proof."""

    payload = json.dumps(
        {
            "asset_id": str(asset.id),
            "modified_at": asset.file_modified_at.isoformat(),
            "file_size": asset.file_size_bytes,
            "checksum": asset.checksum,
            "media_sha256": media_sha256,
            "origin": origin,
            "config": SEARCH_CONFIG_FINGERPRINT,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()

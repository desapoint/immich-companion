"""Version boundary for original-image preservation and integrity evidence."""

from __future__ import annotations

import hashlib

PRESERVATION_MODEL_VERSION = "image-preservation-v1"
PRESERVATION_FEATURE_VERSION = 1
PIXEL_NORMALIZATION_VERSION = 1
PRESERVATION_CONFIG_FINGERPRINT = hashlib.sha256(
    (
        f"{PRESERVATION_MODEL_VERSION}:"
        f"feature={PRESERVATION_FEATURE_VERSION}:"
        f"pixel-normalization={PIXEL_NORMALIZATION_VERSION}:"
        "metadata=exif-capture-camera-gps-orientation-icc-v1"
    ).encode(),
    usedforsecurity=False,
).hexdigest()

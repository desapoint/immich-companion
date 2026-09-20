"""Pure helpers used while discovering and fingerprinting duplicate groups.

This module intentionally has no service or repository dependencies.  Keeping
these deterministic operations separate makes discovery changes reviewable
without pulling in the resolution and review state machinery.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
from uuid import UUID

from companion.duplicate_identity import member_set_key
from companion.duplicate_schema import DuplicateAnalysisOptions


def options_key(options: DuplicateAnalysisOptions) -> str:
    raw = json.dumps(options.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def stable_fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def source_fingerprint(assets: list[Any]) -> str:
    return stable_fingerprint(
        [
            {
                "asset_id": str(asset.id),
                "file_modified_at": asset.file_modified_at.isoformat(),
                "file_size_bytes": asset.file_size_bytes,
            }
            for asset in sorted(assets, key=lambda item: str(item.id))
        ]
    )


def member_fingerprint(asset_ids: list[UUID]) -> str:
    return member_set_key(asset_ids)

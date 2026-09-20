"""Small, side-effect-free asset persistence helpers.

The repository remains the compatibility facade, while payload conversion and
change detection live here so SQL query/write code does not own them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from companion.immich import ImmichAsset
from companion.models import AssetRecord


def similarity_upsert_changes(
    assets: Sequence[ImmichAsset],
    existing: dict[UUID, tuple[str | None, int, int | None, datetime]],
) -> list[tuple[UUID, str, str | None]]:
    """Return image changes that can invalidate content-derived evidence."""

    return [
        (
            asset.id,
            "upsert",
            hashlib.sha256(
                f"{asset.file_size_bytes}:{asset.file_modified_at.isoformat()}".encode()
            ).hexdigest(),
        )
        for asset in assets
        if asset.asset_type == "IMAGE"
        and (
            asset.id not in existing
            or existing[asset.id][2] != asset.file_size_bytes
            or existing[asset.id][3] != asset.file_modified_at
        )
    ]


def immich_asset(record: AssetRecord) -> ImmichAsset:
    """Rebuild the compact Immich contract from synchronized metadata."""

    return ImmichAsset(
        id=record.id,
        owner_id=record.owner_id,
        library_id=record.library_id,
        asset_type=record.asset_type,
        original_file_name=record.original_file_name,
        original_path=record.original_path,
        original_mime_type=record.original_mime_type,
        checksum=record.checksum,
        width=record.width,
        height=record.height,
        duration=record.duration,
        thumbhash=record.thumbhash,
        file_created_at=record.file_created_at,
        file_modified_at=record.file_modified_at,
        local_date_time=record.local_date_time,
        created_at=record.immich_created_at,
        updated_at=record.immich_updated_at,
        is_favorite=record.is_favorite,
        is_archived=record.is_archived,
        is_trashed=record.is_trashed,
        is_offline=record.is_offline,
        is_edited=record.is_edited,
        has_metadata=record.has_metadata,
        visibility=record.visibility,
        live_photo_video_id=record.live_photo_video_id,
        exif_info=(
            {"fileSizeInByte": record.file_size_bytes}
            if record.file_size_bytes is not None
            else None
        ),
        people=list(record.people or []),
        tags=list(record.tags or []),
        stack=record.stack,
    )


def asset_fingerprint(asset: ImmichAsset) -> str:
    payload = asset.model_dump(mode="json", by_alias=True, exclude_none=False)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()

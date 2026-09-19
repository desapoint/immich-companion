"""Stable identity helpers for duplicate groups."""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from uuid import UUID


def member_set_key(asset_ids: Iterable[UUID]) -> str:
    """Return an order-independent identity for one exact member set."""

    members = sorted({str(asset_id) for asset_id in asset_ids})
    return sha256(",".join(members).encode()).hexdigest()


def stable_group_key(discovery_source: str, members_key: str) -> str:
    """Scope a stable member-set identity to its discovery provider."""

    return f"{discovery_source}:{members_key}"

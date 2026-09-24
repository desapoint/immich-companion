"""Neutral duplicate-domain contracts and pure resolution helpers.

These helpers are shared by the facade and extracted domain mixins.  Keeping
them here prevents the mixins from importing one another or the application
facade.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
from uuid import UUID

from companion.contained_duplicate_resolution import _is_contained_resolution_step
from companion.duplicate_identity import member_set_key, stable_group_key
from companion.duplicate_schema import (
    DuplicateResolutionPlan,
    DuplicateResolutionPlanGroup,
    ExactDuplicateGroup,
)
from companion.group_decision import DiscoverySource
from companion.immich import ImmichDuplicateResolution
from companion.models import ActionPlanRecord


def plan_digest(groups: list[dict[str, Any]]) -> str:
    raw = json.dumps(groups, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def options_key(options: Any) -> str:
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


def metadata_int(metadata: dict[str, str], name: str) -> int | None:
    value = metadata.get(name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def metadata_float(metadata: dict[str, str], name: str) -> float | None:
    value = metadata.get(name)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def member_dispositions(
    action: str,
    member_ids: list[UUID],
    primary_id: UUID | None,
) -> list[dict[str, Any]]:
    return [
        {
            "asset_id": str(asset_id),
            "disposition": (
                "keep" if action == "resolve" and asset_id == primary_id
                else "delete" if action == "resolve"
                else "stack" if action == "stack_all"
                else "keep" if action == "keep_all"
                else "no_change"
            ),
            "primary": asset_id == primary_id,
        }
        for asset_id in member_ids
    ]


def action_for_dispositions(dispositions: list[str]) -> str:
    values = set(dispositions)
    if values == {"keep"}:
        return "keep_all"
    if values == {"stack"}:
        return "stack_all"
    if dispositions.count("keep") == 1 and dispositions.count("delete") == len(dispositions) - 1:
        return "resolve"
    return "mixed"


def reviewed_delete_supported(group: ExactDuplicateGroup) -> bool:
    return group.status != "ineligible" and len(group.members) >= 2


def metadata_keeper_for_plan(keep_ids: list[UUID], trash_ids: list[UUID]) -> UUID | None:
    return keep_ids[0] if trash_ids and len(keep_ids) == 1 else None


def contained_native_resolution(planned: dict[str, Any]) -> ImmichDuplicateResolution | None:
    if (
        not _is_contained_resolution_step(planned)
        or planned.get("discovery_source") != DiscoverySource.IMMICH_DUPLICATE.value
    ):
        return None
    keep_ids = [UUID(value) for value in planned.get("keep_asset_ids", [])]
    trash_ids = [UUID(value) for value in planned.get("trash_asset_ids", [])]
    if len(keep_ids) != 1 or not trash_ids:
        return None
    provider_group_id = planned.get("provider_group_id")
    if provider_group_id is None:
        raise ValueError("Contained Immich duplicate group has no provider identifier")
    return ImmichDuplicateResolution(
        duplicate_id=UUID(str(provider_group_id)),
        keep_asset_ids=keep_ids,
        trash_asset_ids=trash_ids,
    )


def normalize_plan_group(group: dict[str, Any]) -> dict[str, Any]:
    """Normalize persisted plans to the current member-partition contract."""

    normalized = dict(group)
    legacy_id = normalized.get("duplicate_id")
    if "group_id" not in normalized and legacy_id is not None:
        normalized["group_id"] = f"immich:{legacy_id}"
    normalized.setdefault("discovery_source", DiscoverySource.IMMICH_DUPLICATE.value)
    if "provider_group_id" not in normalized:
        normalized["provider_group_id"] = legacy_id
    normalized.setdefault("action", "resolve")
    normalized.setdefault(
        "member_asset_ids",
        [
            *([normalized["keeper_asset_id"]] if normalized.get("keeper_asset_id") else []),
            *normalized.get("trash_asset_ids", []),
        ],
    )
    member_ids = [UUID(value) for value in normalized["member_asset_ids"]]
    normalized.setdefault("member_set_key", member_set_key(member_ids))
    normalized.setdefault(
        "stable_group_key",
        stable_group_key(normalized["discovery_source"], normalized["member_set_key"]),
    )
    primary_id = (
        UUID(normalized["keeper_asset_id"])
        if normalized.get("keeper_asset_id") is not None
        else None
    )
    action = normalized["action"]
    if action not in {"resolve", "keep_all", "stack_all", "mixed"}:
        action = "mixed"
        normalized["action"] = action
    normalized.setdefault(
        "keep_asset_ids",
        (
            [str(primary_id)]
            if action == "resolve" and primary_id is not None
            else [str(asset_id) for asset_id in member_ids]
            if action in {"keep_all", "stack_all"}
            else []
        ),
    )
    normalized.setdefault(
        "follow_up",
        {
            "type": "stack",
            "primary_asset_id": str(primary_id),
            "member_asset_ids": [str(asset_id) for asset_id in member_ids],
        }
        if action == "stack_all" and primary_id is not None
        else None,
    )
    normalized.setdefault(
        "follow_ups",
        [normalized["follow_up"]] if normalized["follow_up"] is not None else [],
    )
    if normalized["follow_up"] is None and normalized["follow_ups"]:
        normalized["follow_up"] = normalized["follow_ups"][0]
    for follow_up in normalized["follow_ups"]:
        follow_up.setdefault("resolution", "move_selected")
    normalized.setdefault("execution_state", "pending")
    normalized.setdefault("metadata_work", None)
    normalized.setdefault("member_fingerprint", member_set_key(member_ids))
    if "members" not in normalized:
        keep_ids = {UUID(value) for value in normalized.get("keep_asset_ids", [])}
        trash_ids = {UUID(value) for value in normalized.get("trash_asset_ids", [])}
        stack_ids = {
            UUID(value)
            for follow_up in normalized.get("follow_ups", [])
            for value in follow_up.get("member_asset_ids", [])
        }
        normalized["members"] = [
            {
                "asset_id": str(asset_id),
                "disposition": (
                    "delete"
                    if asset_id in trash_ids
                    else "stack"
                    if asset_id in stack_ids
                    else "keep"
                    if asset_id in keep_ids
                    else "no_change"
                ),
                "primary": asset_id == primary_id,
            }
            for asset_id in member_ids
        ]
    return normalized


def public_plan(record: ActionPlanRecord) -> DuplicateResolutionPlan:
    groups = [
        DuplicateResolutionPlanGroup.model_validate(normalize_plan_group(item))
        for item in record.relation_work.get("groups", [])
    ]
    return DuplicateResolutionPlan(
        id=record.id,
        status=record.status,
        groups=groups,
        group_count=len(groups),
        resolve_group_count=sum(group.action == "resolve" for group in groups),
        keep_all_group_count=sum(group.action == "keep_all" for group in groups),
        stack_group_count=sum(bool(group.follow_ups) for group in groups),
        mixed_group_count=sum(group.action == "mixed" for group in groups),
        trash_asset_count=sum(len(group.trash_asset_ids) for group in groups),
        retained_asset_count=sum(
            member.disposition in {"keep", "stack"} for group in groups for member in group.members
        ),
        zero_survivor_group_count=sum(not group.keep_asset_ids for group in groups),
        expires_at=record.expires_at,
        destructive=getattr(record, "destructive", True),
    )


def same_normalized_pixels(left: Any, right: Any) -> bool:
    """Compare exact decoded pixels from current original preservation evidence."""

    from companion.similarity_features import PIXEL_NORMALIZATION_VERSION

    return bool(
        left is not None
        and right is not None
        and left.origin == "original"
        and right.origin == "original"
        and left.pixel_normalization_version == PIXEL_NORMALIZATION_VERSION
        and right.pixel_normalization_version == PIXEL_NORMALIZATION_VERSION
        and left.pixel_sha256
        and left.pixel_sha256 == right.pixel_sha256
    )

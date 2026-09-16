"""Plan and enforce child-first execution for contained duplicate groups."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select

from companion.database import DatabaseManager
from companion.duplicate_schema import COMPLETED_DUPLICATE_REVIEW_STATUSES
from companion.models import DuplicateGroupReviewRecord

IMMICH_DUPLICATE_SOURCE = "immich_duplicate"
COMPANION_SIMILARITY_SOURCE = "companion_similarity"
CONTAINED_BY_GROUP_IDS = "contained_by_group_ids"
EXECUTION_TRASH_ASSET_IDS = "execution_trash_asset_ids"


class ContainedDuplicateResolutionFailed(RuntimeError):
    """Stop a hierarchy plan when one required contained group cannot complete."""

    def __init__(
        self,
        group_id: str,
        state: str,
        error: str | None = None,
    ) -> None:
        super().__init__(f"Contained duplicate group {group_id} failed with state {state}")
        self.group_id = group_id
        self.state = state
        self.error = error


def _duplicate_plan_digest(groups: list[dict[str, Any]]) -> str:
    raw = json.dumps(groups, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _uuid_list(values: Any) -> list[UUID]:
    if not isinstance(values, list):
        return []
    result: list[UUID] = []
    for value in values:
        try:
            result.append(UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return result


def _source_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _is_contained_resolution_step(group: dict[str, Any]) -> bool:
    return bool(group.get(CONTAINED_BY_GROUP_IDS))


def _has_contained_resolution_steps(groups: Any) -> bool:
    return isinstance(groups, list) and any(
        isinstance(group, dict) and _is_contained_resolution_step(group) for group in groups
    )


def _execution_duplicate_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the internal execution view without changing the reviewed partition."""

    execution_groups: list[dict[str, Any]] = []
    for group in groups:
        execution = dict(group)
        execution_trash = execution.get(EXECUTION_TRASH_ASSET_IDS)
        if isinstance(execution_trash, list):
            execution["trash_asset_ids"] = list(execution_trash)
        execution_groups.append(execution)
    return execution_groups


def _contained_candidate_statement(
    group_record: Any,
    member_record: Any,
    parent_union: set[UUID],
    max_parent_size: int,
) -> Any:
    """Select candidate groups once without DISTINCT over JSON-bearing group rows."""

    matching_member = (
        select(member_record.group_id)
        .where(
            member_record.group_id == group_record.group_id,
            member_record.asset_id.in_(list(parent_union)),
        )
        .exists()
    )
    return select(group_record).where(
        group_record.discovery_source == IMMICH_DUPLICATE_SOURCE,
        group_record.member_count >= 2,
        group_record.member_count <= max_parent_size,
        matching_member,
    )


def _expand_contained_duplicate_groups(
    groups: list[dict[str, Any]],
    candidates: list[Any],
    members_by_group: dict[str, list[UUID]],
) -> list[dict[str, Any]]:
    """Add fully-contained Immich groups as child resolution steps.

    The reviewed parent partition remains intact for audit/public preview. Each parent receives
    a separate execution-only trash list with child-deleted members removed. That allows the
    executor to validate the original similarity membership first, resolve every complete
    Immich child, then delete only the assets still left for the parent.
    """

    original = [dict(group) for group in groups]
    parent_contexts: list[dict[str, Any]] = []
    for group in original:
        if (
            _source_value(group.get("discovery_source")) != COMPANION_SIMILARITY_SOURCE
            or group.get("action") != "resolve"
            or not group.get("keeper_asset_id")
        ):
            continue
        member_ids = set(_uuid_list(group.get("member_asset_ids")))
        trash_ids = set(_uuid_list(group.get("trash_asset_ids")))
        if len(member_ids) < 2:
            continue
        try:
            keeper_id = UUID(str(group["keeper_asset_id"]))
        except (TypeError, ValueError):
            continue
        parent_contexts.append(
            {
                "group_id": str(group["group_id"]),
                "member_ids": member_ids,
                "trash_ids": trash_ids,
                "keeper_id": keeper_id,
            }
        )

    if not parent_contexts:
        return original

    originals_by_id = {str(group.get("group_id")): group for group in original}
    dependency_parents: dict[str, set[str]] = {}
    dependency_trash: dict[str, set[UUID]] = {}
    annotated_originals: dict[str, dict[str, Any]] = {}

    # An explicitly-selected Immich resolve can satisfy the same dependency as a synthesized
    # child, but only when its destructive partition is compatible with every containing parent.
    for group_id, group in originals_by_id.items():
        if (
            _source_value(group.get("discovery_source")) != IMMICH_DUPLICATE_SOURCE
            or group.get("action") != "resolve"
        ):
            continue
        child_members = set(_uuid_list(group.get("member_asset_ids")))
        child_trash = set(_uuid_list(group.get("trash_asset_ids")))
        if len(child_members) < 2:
            continue
        containing = [
            parent for parent in parent_contexts if child_members.issubset(parent["member_ids"])
        ]
        safe = [
            parent
            for parent in containing
            if child_trash.issubset(parent["trash_ids"])
            and parent["keeper_id"] not in child_trash
        ]
        if not containing or len(safe) != len(containing):
            continue
        dependency_parents[group_id] = {parent["group_id"] for parent in safe}
        dependency_trash[group_id] = child_trash
        annotated = dict(group)
        annotated[CONTAINED_BY_GROUP_IDS] = sorted(dependency_parents[group_id])
        annotated_originals[group_id] = annotated

    synthesized: list[dict[str, Any]] = []
    for candidate in candidates:
        group_id = str(candidate.group_id)
        if group_id in originals_by_id:
            continue
        ordered_ids = list(members_by_group.get(group_id, []))
        child_members = set(ordered_ids)
        if len(child_members) < 2:
            continue
        containing = [
            parent for parent in parent_contexts if child_members.issubset(parent["member_ids"])
        ]
        if not containing:
            continue

        parent_keepers_inside = {
            parent["keeper_id"] for parent in containing if parent["keeper_id"] in child_members
        }
        if len(parent_keepers_inside) > 1:
            raise ValueError(
                "Overlapping similarity resolutions choose incompatible keepers inside one "
                "contained Immich duplicate group"
            )
        child_keeper = (
            next(iter(parent_keepers_inside)) if parent_keepers_inside else ordered_ids[0]
        )
        child_trash = {asset_id for asset_id in child_members if asset_id != child_keeper}
        if any(
            not child_trash.issubset(parent["trash_ids"])
            or parent["keeper_id"] in child_trash
            for parent in containing
        ):
            raise ValueError(
                "A contained Immich duplicate resolution conflicts with its similarity parent"
            )

        ordered_members = [
            child_keeper,
            *(asset_id for asset_id in ordered_ids if asset_id != child_keeper),
        ]
        parent_ids = sorted(parent["group_id"] for parent in containing)
        dependency_parents[group_id] = set(parent_ids)
        dependency_trash[group_id] = child_trash
        fingerprint = str(candidate.member_fingerprint)
        synthesized.append(
            {
                "group_id": group_id,
                "stable_group_key": str(candidate.stable_group_key),
                "member_set_key": fingerprint,
                "discovery_source": IMMICH_DUPLICATE_SOURCE,
                "provider_group_id": str(candidate.provider_group_id or candidate.group_id),
                "action": "resolve",
                "keeper_asset_id": str(child_keeper),
                "member_asset_ids": [str(asset_id) for asset_id in ordered_members],
                "keep_asset_ids": [str(child_keeper)],
                "trash_asset_ids": [
                    str(asset_id) for asset_id in ordered_members if asset_id != child_keeper
                ],
                "metadata_work": None,
                "follow_up": None,
                "execution_state": "pending",
                "member_fingerprint": fingerprint,
                "members": [
                    {
                        "asset_id": str(asset_id),
                        "disposition": "keep" if asset_id == child_keeper else "delete",
                        "primary": asset_id == child_keeper,
                    }
                    for asset_id in ordered_members
                ],
                CONTAINED_BY_GROUP_IDS: parent_ids,
            }
        )

    projected_originals: list[dict[str, Any]] = []
    for group in original:
        group_id = str(group.get("group_id"))
        projected = dict(annotated_originals.get(group_id, group))
        parent = next(
            (context for context in parent_contexts if context["group_id"] == group_id),
            None,
        )
        if parent is not None:
            handled: set[UUID] = set()
            for child_id, parent_ids in dependency_parents.items():
                if group_id in parent_ids:
                    handled.update(dependency_trash[child_id])
            projected[EXECUTION_TRASH_ASSET_IDS] = [
                str(asset_id)
                for asset_id in _uuid_list(group.get("trash_asset_ids"))
                if asset_id not in handled
            ]
        projected_originals.append(projected)

    synthesized.sort(key=lambda group: str(group["group_id"]))
    dependency_originals = [
        group for group in projected_originals if _is_contained_resolution_step(group)
    ]
    remaining_originals = [
        group for group in projected_originals if not _is_contained_resolution_step(group)
    ]
    return [*synthesized, *dependency_originals, *remaining_originals]


async def expand_contained_duplicate_plan(
    database: DatabaseManager,
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expand a similarity plan with current, unresolved contained Immich groups."""

    parent_sets = [
        set(_uuid_list(group.get("member_asset_ids")))
        for group in groups
        if _source_value(group.get("discovery_source")) == COMPANION_SIMILARITY_SOURCE
        and group.get("action") == "resolve"
        and group.get("keeper_asset_id")
    ]
    parent_sets = [member_ids for member_ids in parent_sets if len(member_ids) >= 2]
    if not parent_sets:
        return groups

    from companion.composite_duplicate_repository import (
        CompositeDuplicateGroupMemberRecord,
        CompositeDuplicateGroupRecord,
    )

    parent_union = set().union(*parent_sets)
    max_parent_size = max(len(member_ids) for member_ids in parent_sets)
    async with database.sessions() as session:
        group_statement = _contained_candidate_statement(
            CompositeDuplicateGroupRecord,
            CompositeDuplicateGroupMemberRecord,
            parent_union,
            max_parent_size,
        )
        candidates = list((await session.scalars(group_statement)).all())
        if not candidates:
            return groups

        completed_statement = select(DuplicateGroupReviewRecord.stable_group_key).where(
            DuplicateGroupReviewRecord.discovery_source == IMMICH_DUPLICATE_SOURCE,
            DuplicateGroupReviewRecord.stable_group_key.in_(
                [str(candidate.stable_group_key) for candidate in candidates]
            ),
            DuplicateGroupReviewRecord.review_status.in_(COMPLETED_DUPLICATE_REVIEW_STATUSES),
        )
        completed_keys = set((await session.scalars(completed_statement)).all())
        candidates = [
            candidate
            for candidate in candidates
            if str(candidate.stable_group_key) not in completed_keys
        ]
        if not candidates:
            return groups

        group_ids = [str(candidate.group_id) for candidate in candidates]
        member_statement = (
            select(CompositeDuplicateGroupMemberRecord)
            .where(CompositeDuplicateGroupMemberRecord.group_id.in_(group_ids))
            .order_by(
                CompositeDuplicateGroupMemberRecord.group_id,
                CompositeDuplicateGroupMemberRecord.position,
            )
        )
        members = list((await session.scalars(member_statement)).all())

    members_by_group: dict[str, list[UUID]] = {}
    for member in members:
        members_by_group.setdefault(str(member.group_id), []).append(member.asset_id)
    return _expand_contained_duplicate_groups(groups, candidates, members_by_group)

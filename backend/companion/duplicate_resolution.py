"""Duplicate resolution and action orchestration mixin."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import UUID

from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
    DestructiveActionsDisabledError,
)
from companion.duplicate_contracts import (
    action_for_dispositions as _action_for_dispositions,
)
from companion.duplicate_contracts import (
    contained_native_resolution as _contained_native_resolution,
)
from companion.duplicate_contracts import (
    member_dispositions as _member_dispositions,
)
from companion.duplicate_contracts import (
    metadata_keeper_for_plan as _metadata_keeper_for_plan,
)
from companion.duplicate_contracts import (
    normalize_plan_group as _normalize_plan_group,
)
from companion.duplicate_contracts import (
    plan_digest as _plan_digest,
)
from companion.duplicate_contracts import (
    public_plan as _public_plan,
)
from companion.duplicate_contracts import (
    reviewed_delete_supported as _reviewed_delete_supported,
)
from companion.duplicate_contracts import (
    source_fingerprint as _source_fingerprint,
)
from companion.duplicate_contracts import (
    stable_fingerprint as _stable_fingerprint,
)
from companion.duplicate_schema import (
    CrossSourceDuplicateTaskStart,
    DuplicateAnalysisOptions,
    DuplicateResolutionExecuteRequest,
    DuplicateResolutionPlan,
    DuplicateResolutionPlanRequest,
    DuplicateStackDestinationOverride,
    DuplicateStackPlanOverride,
)
from companion.immich import (
    ImmichApiError,
    ImmichAsset,
)
from companion.stack_service import StackSelectionError
from companion.task_coordinator import (
    PermanentTaskError,
    TaskContext,
)
from companion.task_schema import TaskResult

logger = logging.getLogger(__name__)

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"


def _stack_follow_ups(planned: dict[str, Any]) -> list[dict[str, Any]]:
    follow_ups = planned.get("follow_ups")
    if isinstance(follow_ups, list):
        return follow_ups
    follow_up = planned.get("follow_up")
    return [follow_up] if isinstance(follow_up, dict) else []


def _destination_id(planned: dict[str, Any], follow_up: dict[str, Any], index: int) -> str:
    value = follow_up.get("destination_id")
    if isinstance(value, str) and value:
        return value
    return f"{planned['group_id']}:stack:{index + 1}"


def _unique_stack_destinations(
    groups: list[dict[str, Any]],
) -> dict[str, tuple[dict[str, Any], set[str]]]:
    destinations: dict[str, tuple[dict[str, Any], set[str]]] = {}
    for planned in groups:
        for index, follow_up in enumerate(_stack_follow_ups(planned)):
            destination_id = _destination_id(planned, follow_up, index)
            source_groups = {
                str(value)
                for value in follow_up.get("source_group_ids", [])
                if value
            } or {str(planned["group_id"])}
            existing = destinations.get(destination_id)
            if existing is None:
                destinations[destination_id] = (follow_up, set(source_groups))
                continue
            previous, participants = existing
            comparable = (
                "primary_asset_id",
                "member_asset_ids",
                "resolution",
                "source_fingerprint",
                "conflict_fingerprint",
            )
            if any(previous.get(key) != follow_up.get(key) for key in comparable):
                raise ActionPlanConflictError(
                    "A shared proposed stack changed between duplicate groups"
                )
            participants.update(source_groups)
    return destinations


def _validate_stack_destination_topology(groups: list[dict[str, Any]]) -> None:
    """Reject impossible final stack intent before any Immich mutation."""

    destinations = _unique_stack_destinations(groups)
    destination_by_asset: dict[str, str] = {}
    for destination_id, (follow_up, _) in destinations.items():
        for asset_id in follow_up.get("member_asset_ids", []):
            previous = destination_by_asset.get(str(asset_id))
            if previous is not None and previous != destination_id:
                raise ActionPlanConflictError(
                    "One asset is assigned to multiple proposed duplicate stacks"
                )
            destination_by_asset[str(asset_id)] = destination_id

    deleted_assets = {
        str(member.get("asset_id"))
        for planned in groups
        for member in planned.get("members", [])
        if isinstance(member, dict) and member.get("disposition") == "delete"
    }
    conflicting = deleted_assets.intersection(destination_by_asset)
    if conflicting:
        raise ActionPlanConflictError(
            "An asset cannot be deleted by one duplicate group and stacked by another"
        )


def _apply_stack_destination_overrides(
    plan_groups: list[dict[str, Any]],
    destinations: list[DuplicateStackDestinationOverride],
    member_assets: dict[UUID, Any],
) -> None:
    """Replace group-local stack partitions with reviewed plan-wide destinations."""

    if not destinations:
        return
    groups_by_id = {str(planned["group_id"]): planned for planned in plan_groups}
    member_ids_by_group = {
        group_id: {str(value) for value in planned.get("member_asset_ids", [])}
        for group_id, planned in groups_by_id.items()
    }
    stack_ids_by_group = {
        group_id: {
            str(member["asset_id"])
            for member in planned.get("members", [])
            if isinstance(member, dict) and member.get("disposition") == "stack"
        }
        for group_id, planned in groups_by_id.items()
    }
    covered_by_group: dict[str, set[str]] = {
        group_id: set() for group_id in groups_by_id
    }
    follow_ups_by_group: dict[str, list[dict[str, Any]]] = {
        group_id: [] for group_id in groups_by_id
    }
    seen_destination_ids: set[str] = set()
    destination_by_asset: dict[str, str] = {}

    for destination in destinations:
        if destination.destination_id in seen_destination_ids:
            raise ActionPlanConflictError("Stack destination identifiers must be unique")
        seen_destination_ids.add(destination.destination_id)
        source_group_ids = list(dict.fromkeys(destination.source_group_ids))
        missing_groups = [group_id for group_id in source_group_ids if group_id not in groups_by_id]
        if missing_groups:
            raise ActionPlanConflictError(
                "A proposed stack destination references an unselected duplicate group"
            )
        allowed_assets = set().union(
            *(member_ids_by_group[group_id] for group_id in source_group_ids)
        )
        requested_ids = [str(value) for value in destination.member_asset_ids]
        if not set(requested_ids).issubset(allowed_assets):
            raise ActionPlanConflictError(
                "A proposed stack destination references an asset outside its source groups"
            )
        for asset_id in requested_ids:
            previous = destination_by_asset.get(asset_id)
            if previous is not None and previous != destination.destination_id:
                raise ActionPlanConflictError(
                    "One asset is assigned to multiple proposed duplicate stacks"
                )
            destination_by_asset[asset_id] = destination.destination_id

        assets = [
            member_assets[UUID(asset_id)]
            for asset_id in requested_ids
            if UUID(asset_id) in member_assets
        ]
        if len(assets) != len(requested_ids):
            raise ActionPlanConflictError(
                "A proposed stack destination contains an unavailable duplicate asset"
            )
        follow_up = {
            "type": "stack",
            "destination_id": destination.destination_id,
            "source_group_ids": source_group_ids,
            "primary_asset_id": str(destination.primary_asset_id),
            "resolution": destination.resolution,
            "member_asset_ids": [
                str(destination.primary_asset_id),
                *(
                    asset_id
                    for asset_id in requested_ids
                    if asset_id != str(destination.primary_asset_id)
                ),
            ],
            "source_fingerprint": _source_fingerprint(assets),
            "conflict_fingerprint": None,
        }
        for group_id in source_group_ids:
            relevant = set(requested_ids).intersection(stack_ids_by_group[group_id])
            if not relevant:
                continue
            covered_by_group[group_id].update(relevant)
            follow_ups_by_group[group_id].append(dict(follow_up))

    for group_id, stack_ids in stack_ids_by_group.items():
        if covered_by_group[group_id] != stack_ids:
            raise ActionPlanConflictError(
                "Reviewed stack destinations must cover every Stack decision exactly once"
            )
        planned = groups_by_id[group_id]
        planned["follow_ups"] = follow_ups_by_group[group_id]
        planned["follow_up"] = (
            follow_ups_by_group[group_id][0]
            if follow_ups_by_group[group_id]
            else None
        )
        primary_ids = {
            follow_up["primary_asset_id"]
            for follow_up in follow_ups_by_group[group_id]
        }
        for member in planned.get("members", []):
            if isinstance(member, dict) and member.get("disposition") == "stack":
                member["primary"] = str(member.get("asset_id")) in primary_ids


def _saved_stack_overrides(record: Any) -> list[DuplicateStackPlanOverride] | None:
    """Restore durable pending-stack partitions from member-level draft metadata."""

    if record is None:
        return None
    decisions = [
        item
        for item in list(getattr(record, "member_decisions", []) or [])
        if isinstance(item, dict) and item.get("disposition") == "stack"
    ]
    if not decisions or not any(item.get("stack_id") for item in decisions):
        return None
    if any(not item.get("stack_id") for item in decisions):
        raise ActionPlanConflictError(
            "Saved duplicate stack assignments are incomplete; review this group again"
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in decisions:
        grouped.setdefault(str(item["stack_id"]), []).append(item)

    overrides: list[DuplicateStackPlanOverride] = []
    for members in grouped.values():
        if len(members) < 2:
            raise ActionPlanConflictError(
                "A saved pending stack has fewer than two images; complete it before review"
            )
        primary_members = [item for item in members if item.get("stack_primary") is True]
        if len(primary_members) != 1:
            raise ActionPlanConflictError(
                "A saved pending stack needs exactly one primary image"
            )
        primary = primary_members[0]
        resolution = primary.get("stack_resolution") or next(
            (
                item.get("stack_resolution")
                for item in members
                if item.get("stack_resolution")
            ),
            getattr(record, "stack_resolution", "move_selected"),
        )
        overrides.append(
            DuplicateStackPlanOverride(
                primary_asset_id=UUID(str(primary["asset_id"])),
                member_asset_ids=[UUID(str(item["asset_id"])) for item in members],
                resolution=resolution,
            )
        )
    return overrides


class DuplicateResolutionMixin:
    """Planning, review-state persistence, and resolution execution."""

    async def plan(self, request: DuplicateResolutionPlanRequest) -> DuplicateResolutionPlan:
        options = await self._options(request.options)
        requested_group_ids = list(dict.fromkeys(request.group_ids))
        if request.workspace_selected:
            requested_group_ids = (await self.workspace(options)).selected_group_ids
            if request.group_ids and set(request.group_ids) != set(requested_group_ids):
                raise ActionPlanConflictError(
                    "The duplicate workspace selection changed before planning"
                )

        if request.all_eligible:
            limit = getattr(self._settings, "action_max_targets", 5000)
            target_ids = await self._matching_group_ids(
                source="both",
                state="actionable",
                limit=limit + 1,
            )
            if len(target_ids) > limit:
                raise ValueError(
                    f"Eligible duplicate planning exceeds the configured {limit} group limit"
                )
        else:
            target_ids = requested_group_ids

        if not target_ids:
            raise ValueError("No duplicate groups were selected")

        batch_size = max(
            1,
            min(250, getattr(self._settings, "sync_batch_size", 250)),
        )
        found_ids: set[str] = set()
        plan_groups: list[dict[str, Any]] = []
        planned_member_assets: dict[UUID, Any] = {}
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            _, _, _, result = await self._snapshot_groups(discovered, options)
            selected = [
                group
                for group in result.groups
                if (
                    group.auto_resolvable
                    if request.all_eligible
                    else group.group_id in batch_ids
                )
            ]
            found_ids.update(group.group_id for group in selected)
            for group in selected:
                for member in group.members:
                    planned_member_assets.setdefault(member.id, member)

            review_records: dict[tuple[str, str], object] = {}
            if self._reviews is not None:
                for discovery_source in {
                    group.discovery_source for group in selected
                }:
                    source_groups = [
                        group
                        for group in selected
                        if group.discovery_source == discovery_source
                    ]
                    records = await self._reviews.get_many(
                        discovery_source,
                        [group.stable_group_key for group in source_groups],
                    )
                    review_records.update(
                        (
                            (discovery_source, group_key),
                            record,
                        )
                        for group_key, record in records.items()
                    )

            for group in selected:
                member_ids = {member.id for member in group.members}
                record = review_records.get(
                    (group.discovery_source, group.stable_group_key)
                )
                raw_decisions = list(getattr(record, "member_decisions", []) or [])
                draft_dispositions = {
                    UUID(decision["asset_id"]): decision["disposition"]
                    for decision in raw_decisions
                    if isinstance(decision, dict)
                    and decision.get("asset_id")
                    and decision.get("disposition") in {"keep", "delete", "stack"}
                }
                draft_is_current = (
                    record is not None
                    and getattr(record, "member_fingerprint", None)
                    == group.member_fingerprint
                    and set(draft_dispositions) == member_ids
                    and len(draft_dispositions) == len(group.members)
                )
                if raw_decisions and not draft_is_current:
                    raise ActionPlanConflictError(
                        "Every selected duplicate needs a complete current saved draft"
                    )
                if draft_is_current:
                    dispositions = [
                        draft_dispositions[member.id] for member in group.members
                    ]
                    action = _action_for_dispositions(dispositions)
                else:
                    action = request.action_overrides.get(
                        group.group_id,
                        "resolve"
                        if request.all_eligible
                        or group.group_id in request.keeper_overrides
                        else group.effective_action,
                    )
                    if action == "mixed":
                        raise ActionPlanConflictError(
                            "Mixed duplicate choices require a complete current saved draft"
                        )
                    legacy_primary = request.keeper_overrides.get(
                        group.group_id,
                        group.effective_primary_asset_id or group.keeper_asset_id,
                    )
                    dispositions = [
                        item["disposition"]
                        for item in _member_dispositions(
                            action,
                            [member.id for member in group.members],
                            legacy_primary,
                        )
                    ]
                if action == "none":
                    raise ActionPlanConflictError(
                        "Every selected group needs an action"
                    )
                has_deletions = "delete" in dispositions
                if has_deletions and not _reviewed_delete_supported(group):
                    raise ActionPlanConflictError(
                        "Deleting duplicate members requires a current "
                        "multi-member duplicate group"
                    )
                stack_ids = [
                    member.id
                    for member, disposition in zip(
                        group.members,
                        dispositions,
                        strict=True,
                    )
                    if disposition == "stack"
                ]
                if stack_ids and any(
                    member.is_offline
                    for member in group.members
                    if member.id in stack_ids
                ):
                    raise ActionPlanConflictError(
                        "Offline members cannot form a reviewed stack"
                    )
                if len(stack_ids) == 1:
                    raise ActionPlanConflictError(
                        "A stack needs at least two surviving members"
                    )
                keep_ids = [
                    member.id
                    for member, disposition in zip(
                        group.members,
                        dispositions,
                        strict=True,
                    )
                    if disposition in {"keep", "stack"}
                ]
                trash_ids = [
                    member.id
                    for member, disposition in zip(
                        group.members,
                        dispositions,
                        strict=True,
                    )
                    if disposition == "delete"
                ]
                stack_primary_id = (
                    getattr(record, "stack_primary_asset_id", None)
                    if record
                    else None
                )
                stack_resolution = getattr(
                    record,
                    "stack_resolution",
                    "move_selected",
                )
                requested_stacks = request.stack_overrides.get(group.group_id)
                if requested_stacks is None:
                    requested_stacks = _saved_stack_overrides(record)
                if requested_stacks is not None:
                    assigned_stack_ids: list[UUID] = []
                    for requested_stack in requested_stacks:
                        requested_ids = list(requested_stack.member_asset_ids)
                        if not set(requested_ids).issubset(member_ids):
                            raise ActionPlanConflictError(
                                "A requested stack references a non-member asset"
                            )
                        if set(assigned_stack_ids).intersection(requested_ids):
                            raise ActionPlanConflictError(
                                "An asset cannot belong to multiple resulting stacks"
                            )
                        assigned_stack_ids.extend(requested_ids)
                    if set(assigned_stack_ids) != set(stack_ids):
                        raise ActionPlanConflictError(
                            "Requested stacks must contain every Stack disposition exactly once"
                        )
                    stack_primary_id = (
                        requested_stacks[0].primary_asset_id
                        if requested_stacks
                        else None
                    )
                elif stack_ids:
                    if stack_primary_id not in stack_ids:
                        preferred = (
                            group.effective_primary_asset_id
                            or group.keeper_asset_id
                        )
                        stack_primary_id = (
                            preferred if preferred in stack_ids else stack_ids[0]
                        )
                else:
                    stack_primary_id = None
                stack_follow_ups = (
                    [
                        {
                            "type": "stack",
                            "primary_asset_id": str(requested_stack.primary_asset_id),
                            "resolution": requested_stack.resolution,
                            "member_asset_ids": [
                                str(requested_stack.primary_asset_id),
                                *(
                                    str(asset_id)
                                    for asset_id in requested_stack.member_asset_ids
                                    if asset_id != requested_stack.primary_asset_id
                                ),
                            ],
                            "source_fingerprint": _source_fingerprint(
                                [
                                    member
                                    for member in group.members
                                    if member.id in requested_stack.member_asset_ids
                                ]
                            ),
                            "conflict_fingerprint": None,
                        }
                        for requested_stack in requested_stacks
                    ]
                    if requested_stacks is not None
                    else [
                        {
                            "type": "stack",
                            "primary_asset_id": str(stack_primary_id),
                            "resolution": stack_resolution,
                            "member_asset_ids": [
                                str(stack_primary_id),
                                *(
                                    str(asset_id)
                                    for asset_id in stack_ids
                                    if asset_id != stack_primary_id
                                ),
                            ],
                            "source_fingerprint": _source_fingerprint(
                                [
                                    member
                                    for member in group.members
                                    if member.id in stack_ids
                                ]
                            ),
                            "conflict_fingerprint": None,
                        }
                    ]
                    if stack_primary_id is not None
                    else []
                )
                stack_primary_ids = {
                    UUID(follow_up["primary_asset_id"])
                    for follow_up in stack_follow_ups
                }
                metadata_keeper_id = _metadata_keeper_for_plan(
                    keep_ids,
                    trash_ids,
                )
                keeper_id = metadata_keeper_id or stack_primary_id
                if action == "resolve" and keeper_id is None:
                    raise ActionPlanConflictError(
                        "A primary asset must be chosen from the group"
                    )
                ordered_keep_ids = (
                    [
                        metadata_keeper_id,
                        *(
                            asset_id
                            for asset_id in keep_ids
                            if asset_id != metadata_keeper_id
                        ),
                    ]
                    if metadata_keeper_id is not None
                    else keep_ids
                )
                ordered_members = (
                    [
                        keeper_id,
                        *(
                            member.id
                            for member in group.members
                            if member.id != keeper_id
                        ),
                    ]
                    if keeper_id is not None
                    else [member.id for member in group.members]
                )
                metadata_work: dict[str, Any] | None = None
                if metadata_keeper_id is not None and trash_ids:
                    keeper_albums: set[UUID] = set()
                    keeper_tags: set[UUID] = set()
                    trash_albums: set[UUID] = set()
                    trash_tags: set[UUID] = set()
                    relation_snapshot, relation_fingerprint = (
                        await self._relation_snapshot(member_ids)
                    )
                    for member_id, (albums, tags) in relation_snapshot.items():
                        if member_id == metadata_keeper_id:
                            keeper_albums.update(albums)
                            keeper_tags.update(tags)
                        if member_id in trash_ids:
                            trash_albums.update(albums)
                            trash_tags.update(tags)
                    metadata_work = {
                        "keeper_asset_id": str(metadata_keeper_id),
                        "album_ids": [
                            str(identifier)
                            for identifier in sorted(
                                trash_albums - keeper_albums
                            )
                        ],
                        "tag_ids": [
                            str(identifier)
                            for identifier in sorted(
                                trash_tags - keeper_tags
                            )
                        ],
                        "source_fingerprint": relation_fingerprint,
                    }
                plan_groups.append(
                    {
                        "group_id": group.group_id,
                        "stable_group_key": group.stable_group_key,
                        "member_set_key": group.member_set_key,
                        "discovery_source": group.discovery_source,
                        "provider_group_id": group.provider_group_id,
                        "action": action,
                        "keeper_asset_id": (
                            str(keeper_id) if keeper_id is not None else None
                        ),
                        "member_asset_ids": [
                            str(asset_id) for asset_id in ordered_members
                        ],
                        "keep_asset_ids": [
                            str(asset_id) for asset_id in ordered_keep_ids
                        ],
                        "trash_asset_ids": [
                            str(asset_id) for asset_id in trash_ids
                        ],
                        "metadata_work": metadata_work,
                        "follow_up": stack_follow_ups[0] if stack_follow_ups else None,
                        "follow_ups": stack_follow_ups,
                        "execution_state": "pending",
                        "member_fingerprint": group.member_fingerprint,
                        "members": [
                            {
                                "asset_id": str(member.id),
                                "disposition": (
                                    draft_dispositions[member.id]
                                    if draft_is_current
                                    else dispositions[index]
                                ),
                                "primary": member.id
                                in stack_primary_ids | {metadata_keeper_id},
                            }
                            for index, member in enumerate(group.members)
                        ],
                    }
                )

        if not plan_groups:
            raise ValueError("No duplicate groups were selected")

        for planned in plan_groups:
            for index, follow_up in enumerate(_stack_follow_ups(planned)):
                follow_up.setdefault(
                    "destination_id",
                    f"{planned['group_id']}:stack:{index + 1}",
                )
                follow_up.setdefault("source_group_ids", [planned["group_id"]])

        _apply_stack_destination_overrides(
            plan_groups,
            request.stack_destinations,
            planned_member_assets,
        )
        if (
            not request.all_eligible
            and found_ids != set(requested_group_ids)
        ):
            raise ActionPlanConflictError(
                "A selected duplicate group is no longer available"
            )

        stack_plan_groups = [
            planned
            for planned in plan_groups
            if _stack_follow_ups(planned)
        ]
        if stack_plan_groups and self._stacks is not None:
            stack_snapshot = await self._stacks.stack_snapshot()
            for planned in stack_plan_groups:
                for follow_up in _stack_follow_ups(planned):
                    member_ids = [
                        UUID(value) for value in follow_up["member_asset_ids"]
                    ]
                    follow_up["conflict_fingerprint"] = _stable_fingerprint(
                        self._stacks.select_conflict_snapshot(
                            member_ids,
                            stack_snapshot,
                        )
                    )
        plan_groups.sort(key=lambda item: item["group_id"])
        record = await self._actions.create_duplicate_plan(
            groups=plan_groups,
            options=request.options.model_dump(mode="json"),
            target_digest=_plan_digest(plan_groups),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=self._settings.action_plan_ttl_seconds),
        )
        return _public_plan(record)

    async def start_resolution(
        self,
        request: DuplicateResolutionExecuteRequest,
    ) -> CrossSourceDuplicateTaskStart:
        record = await self._actions.get_plan(request.plan_id)
        if record is None or record.action != "resolve_duplicates":
            raise ActionPlanNotFoundError("Duplicate resolution plan was not found")
        resuming_follow_up = record.status == "failed"
        if record.status == "failed":
            record = await self._actions.reopen_duplicate_follow_up(record.id)
            if record is None:
                raise ActionPlanConflictError(
                    "This failed plan has no compatible incomplete work to resume"
                )
        if record.status != "planned":
            raise ActionPlanConflictError("Duplicate resolution plan has already been used")
        if not resuming_follow_up and record.expires_at <= datetime.now(UTC):
            await self._actions.finish_plan(record.id, "expired", {"error": "expired"})
            raise ActionPlanConflictError("Duplicate resolution plan has expired")
        if record.destructive and not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError("Duplicate resolution is disabled in safe mode")
        task = await self._tasks.submit(
            DUPLICATE_RESOLUTION_TASK_TYPE,
            {"plan_id": str(record.id)},
            priority=90,
            lane_key="asset_action",
            deduplication_key=f"duplicate-plan:{record.id}",
        )
        await self._tasks.start()
        return CrossSourceDuplicateTaskStart(task_id=task.id)

    async def execute_plan(self, context: TaskContext, plan_id: UUID) -> TaskResult:
        action_started = perf_counter()
        existing = await self._actions.get_plan(plan_id)
        if existing is None or existing.action != "resolve_duplicates":
            raise PermanentTaskError("Duplicate resolution plan was not found")
        if existing.status not in {"planned", "running"}:
            raise PermanentTaskError("Duplicate resolution plan has already been used")
        if existing.destructive and not self._settings.allow_destructive_actions:
            raise PermanentTaskError("Duplicate resolution is disabled in safe mode")

        persisted_groups = existing.relation_work.get("groups", [])
        target_digest = getattr(existing, "target_digest", None)
        if target_digest is not None and (
            not isinstance(persisted_groups, list)
            or _plan_digest(persisted_groups) != target_digest
        ):
            result = {
                "error": "plan_fingerprint_mismatch",
                "group_count": 0,
                "processed_group_count": 0,
                "resolved_group_count": 0,
                "kept_all_group_count": 0,
                "zero_survivor_group_count": 0,
                "stacked_group_count": 0,
                "failed_group_ids": [],
                "drifted_group_ids": [],
                "follow_up_pending_group_ids": [],
                "trashed_asset_count": 0,
                "verified": False,
            }
            await self._actions.finish_plan(plan_id, "drifted", result)
            return TaskResult(
                status="failed",
                summary=result,
                counters={
                    "groups_processed": 0,
                    "groups_resolved": 0,
                    "groups_kept_all": 0,
                    "groups_zero_survivor": 0,
                    "groups_stacked": 0,
                    "groups_failed": 0,
                    "assets_trashed": 0,
                },
            )
        raw_groups = [_normalize_plan_group(item) for item in persisted_groups]
        try:
            _validate_stack_destination_topology(raw_groups)
        except ActionPlanConflictError:
            result = {
                "error": "stack_destination_conflict",
                "group_count": len(raw_groups),
                "processed_group_count": 0,
                "resolved_group_count": 0,
                "kept_all_group_count": 0,
                "zero_survivor_group_count": 0,
                "stacked_group_count": 0,
                "failed_group_ids": [planned["group_id"] for planned in raw_groups],
                "drifted_group_ids": [planned["group_id"] for planned in raw_groups],
                "follow_up_pending_group_ids": [],
                "trashed_asset_count": 0,
                "verified": False,
            }
            await self._actions.finish_plan(plan_id, "drifted", result)
            return TaskResult(
                status="failed",
                summary=result,
                counters={
                    "groups_processed": 0,
                    "groups_resolved": 0,
                    "groups_kept_all": 0,
                    "groups_zero_survivor": 0,
                    "groups_stacked": 0,
                    "groups_failed": len(raw_groups),
                    "assets_trashed": 0,
                },
            )
        options = DuplicateAnalysisOptions.model_validate(existing.relation_work.get("options", {}))
        stored_execution = dict(
            (getattr(existing, "result", None) or {}).get("group_execution") or {}
        )
        def execution_state(planned: dict[str, Any]) -> str:
            stored = stored_execution.get(planned["group_id"])
            if isinstance(stored, dict) and isinstance(stored.get("state"), str):
                return stored["state"]
            return planned.get("execution_state", "pending")

        failed_ids: list[str] = []
        drifted_ids: list[str] = []
        trashed_ids: list[UUID] = []
        pending_resolution = [
            planned for planned in raw_groups if execution_state(planned) == "pending"
        ]
        if pending_resolution:
            stable_keys = [planned["stable_group_key"] for planned in pending_resolution]
            identities = await self._group_identities(stable_group_keys=stable_keys)
            discovered = await self._groups_by_ids(
                [identity.group_id for identity in identities]
            )
            _, _, _, live_result = await self._snapshot_groups(discovered, options)
            reviewed = {group.stable_group_key: group for group in live_result.groups}
        else:
            reviewed = {}
        preflight_ready: list[dict[str, Any]] = []
        for planned in pending_resolution:
            live_group = reviewed.get(planned["stable_group_key"])
            planned_members = {UUID(value) for value in planned["member_asset_ids"]}
            has_deletions = bool(planned.get("trash_asset_ids"))
            if (
                live_group is None
                or {asset.id for asset in live_group.members} != planned_members
                or live_group.member_fingerprint != planned["member_fingerprint"]
                or (
                    has_deletions
                    and not _reviewed_delete_supported(live_group)
                )
                or (
                    bool(_stack_follow_ups(planned))
                    and any(
                        member.is_offline
                        for member in live_group.members
                        if any(
                            str(member.id) in follow_up["member_asset_ids"]
                            for follow_up in _stack_follow_ups(planned)
                        )
                    )
                )
            ):
                identifier = planned["group_id"]
                failed_ids.append(identifier)
                drifted_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "drifted",
                    "error": "group_drift",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "drifted",
                    error="group_drift",
                )
            else:
                planned["provider_group_id"] = live_group.provider_group_id
                preflight_ready.append(planned)
        pending_resolution = preflight_ready
        preflight_done = perf_counter()

        if existing.status == "planned":
            claimed = await self._actions.claim_plan(plan_id)
            if claimed is None:
                raise PermanentTaskError("Duplicate resolution plan has already been used")

        pacing = await self._runtime_sync_settings.get()
        batch_size = pacing.full_batch_size
        total_steps = len(raw_groups) + sum(
            len(_stack_follow_ups(planned)) for planned in raw_groups
        )
        completed_steps = sum(
            1 + len(_stack_follow_ups(planned))
            if execution_state(planned) == "completed"
            else 1
            if execution_state(planned) in {"follow_up_pending", "completed"}
            else 0
            for planned in raw_groups
        )
        resolved_ids: set[str] = {
            planned["group_id"]
            for planned in raw_groups
            if execution_state(planned) in {"duplicate_resolved", "follow_up_pending", "completed"}
        }

        async def checkpoint(detail: str) -> None:
            successful = sum(execution_state(planned) == "completed" for planned in raw_groups)
            await context.checkpoint(
                checkpoint={"phase": "processing", "steps_completed": completed_steps},
                counters={
                    "groups_completed": successful,
                    "groups_failed": len(failed_ids),
                },
                progress={
                    "phase": "duplicate_resolution",
                    "completed": completed_steps,
                    "total": total_steps,
                    "percent": round(completed_steps / total_steps * 100, 1),
                    "detail": detail,
                },
            )

        metadata_ready: list[dict[str, Any]] = []
        for planned in pending_resolution:
            metadata_work = planned.get("metadata_work")
            if metadata_work is None:
                metadata_ready.append(planned)
                continue
            identifier = planned["group_id"]
            keeper_asset_id = UUID(metadata_work["keeper_asset_id"])
            try:
                expected_fingerprint = metadata_work.get("source_fingerprint")
                if expected_fingerprint is not None:
                    _, current_fingerprint = await self._relation_snapshot(
                        {UUID(value) for value in planned["member_asset_ids"]}
                    )
                    if current_fingerprint != expected_fingerprint:
                        raise ActionPlanConflictError(
                            "Duplicate metadata inputs changed after review"
                        )
                for album_id in metadata_work.get("album_ids", []):
                    await self._immich.add_assets_to_album(
                        UUID(album_id),
                        [keeper_asset_id],
                    )
                for tag_id in metadata_work.get("tag_ids", []):
                    await self._immich.add_assets_to_tag(
                        UUID(tag_id),
                        [keeper_asset_id],
                    )
            except ActionPlanConflictError:
                failed_ids.append(identifier)
                drifted_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "drifted",
                    "error": "metadata_input_drift",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "drifted",
                    error="metadata_input_drift",
                )
            except ImmichApiError:
                failed_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "failed",
                    "error": "metadata_reconciliation_failed",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "failed",
                    error="metadata_reconciliation_failed",
                )
            else:
                metadata_ready.append(planned)
        pending_resolution = metadata_ready
        metadata_done = perf_counter()

        action_batches = [
            pending_resolution[offset : offset + batch_size]
            for offset in range(0, len(pending_resolution), batch_size)
        ]
        for batch_index, batch in enumerate(action_batches):
            await context.ensure_active()
            for planned in batch:
                identifier = planned["group_id"]
                group_trash_ids = [
                    UUID(value) for value in planned.get("trash_asset_ids", [])
                ]
                try:
                    if group_trash_ids:
                        try:
                            native_resolution = _contained_native_resolution(planned)
                        except (TypeError, ValueError) as error:
                            raise ImmichApiError("resolve contained duplicate group") from error
                        if native_resolution is not None:
                            await self._immich.resolve_duplicate_groups([native_resolution])
                        else:
                            await self._immich.trash_assets(group_trash_ids)
                        refreshed = [
                            await self._immich.get_asset(asset_id)
                            for asset_id in group_trash_ids
                        ]
                        if any(not asset.is_trashed for asset in refreshed):
                            raise ImmichApiError("verify trashed duplicate members")
                except ImmichApiError:
                    if identifier not in failed_ids:
                        failed_ids.append(identifier)
                    stored_execution[identifier] = {
                        "state": "failed",
                        "error": "duplicate_member_trash_failed",
                    }
                    await self._actions.record_duplicate_group_execution(
                        plan_id,
                        identifier,
                        "failed",
                        error="duplicate_member_trash_failed",
                    )
                    continue

                resolved_ids.add(identifier)
                trashed_ids.extend(group_trash_ids)
                state = (
                    "follow_up_pending"
                    if _stack_follow_ups(planned)
                    else "completed"
                )
                stored_execution[identifier] = {"state": state, "error": None}
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    state,
                )
                completed_steps += 1

            await checkpoint("Applied reviewed duplicate member actions.")
            if batch_index + 1 < len(action_batches):
                await asyncio.sleep(pacing.full_min_batch_delay_seconds)

        if trashed_ids:
            await self._assets.remove_assets(trashed_ids)

        resolution_done = perf_counter()

        stack_groups = [item for item in raw_groups if execution_state(item) == "follow_up_pending"]
        for planned in stack_groups:
            await context.ensure_active()
            identifier = planned["group_id"]
            try:
                for follow_up in _stack_follow_ups(planned):
                    member_ids = [
                        UUID(value) for value in follow_up["member_asset_ids"]
                    ]
                    refreshed_assets: list[ImmichAsset] = []
                    for asset_id in member_ids:
                        asset = await self._immich.get_asset(asset_id)
                        refreshed_assets.append(asset)
                    expected_source = follow_up.get("source_fingerprint")
                    if (
                        expected_source is not None
                        and _source_fingerprint(refreshed_assets) != expected_source
                    ):
                        raise ActionPlanConflictError(
                            "Stack member files changed after review"
                        )
                    expected_conflicts = follow_up.get("conflict_fingerprint")
                    if expected_conflicts is not None and (
                        self._stacks is None
                        or _stable_fingerprint(
                            await self._stacks.conflict_snapshot(member_ids)
                        )
                        != expected_conflicts
                    ):
                        raise ActionPlanConflictError(
                            "Existing stack memberships changed after review"
                        )
                    stack_ids = {
                        str(asset.stack.get("id"))
                        for asset in refreshed_assets
                        if asset.stack is not None and asset.stack.get("id") is not None
                    }
                    existing_stack_complete = (
                        bool(stack_ids)
                        and len(stack_ids) == 1
                        and all(asset.stack is not None for asset in refreshed_assets)
                    )
                    if not existing_stack_complete:
                        if self._stacks is None:
                            raise StackSelectionError(
                                "Shared stack execution is unavailable"
                            )
                        preparation = await self._stacks.prepare(
                            member_ids,
                            follow_up.get("resolution", "move_selected"),
                            UUID(follow_up["primary_asset_id"]),
                        )
                        if not await self._stacks.execute(preparation):
                            raise ImmichApiError("verify created stack")
                        refreshed_assets = [
                            await self._immich.get_asset(asset_id)
                            for asset_id in member_ids
                        ]
                    if (
                        any(asset.stack is None for asset in refreshed_assets)
                        or len(
                            {
                                str(asset.stack.get("id"))
                                for asset in refreshed_assets
                                if asset.stack is not None
                            }
                        )
                        != 1
                    ):
                        raise ImmichApiError("verify created stack")
                    for asset in refreshed_assets:
                        await self._assets.refresh_asset(asset)
            except ActionPlanConflictError:
                if identifier not in failed_ids:
                    failed_ids.append(identifier)
                if identifier not in drifted_ids:
                    drifted_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "drifted",
                    "error": "stack_input_drift",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "drifted",
                    error="stack_input_drift",
                )
            except (ImmichApiError, StackSelectionError):
                if identifier not in failed_ids:
                    failed_ids.append(identifier)
                stored_execution[identifier] = {
                    "state": "follow_up_pending",
                    "error": "stack_follow_up_failed",
                }
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "follow_up_pending",
                    error="stack_follow_up_failed",
                )
            else:
                stored_execution[identifier] = {"state": "completed", "error": None}
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    "completed",
                )
                completed_steps += len(_stack_follow_ups(planned))
            await checkpoint("Completing post-resolution Immich stacks…")

        successful_ids = {
            planned["group_id"] for planned in raw_groups if execution_state(planned) == "completed"
        }
        kept_ids = {
            planned["group_id"]
            for planned in raw_groups
            if planned["action"] == "keep_all" and planned["group_id"] in successful_ids
        }
        zero_survivor_ids = {
            planned["group_id"]
            for planned in raw_groups
            if not planned.get("keep_asset_ids") and planned["group_id"] in successful_ids
        }
        stacked_ids = {
            planned["group_id"]
            for planned in raw_groups
            if _stack_follow_ups(planned) and planned["group_id"] in successful_ids
        }

        if self._reviews is not None:
            review_statuses = {
                "resolve": "reviewed_resolve",
                "keep_all": "reviewed_keep_all",
                "stack_all": "reviewed_stack_all",
                "mixed": "reviewed_mixed",
            }
            for planned in raw_groups:
                if planned["group_id"] not in successful_ids:
                    continue
                await self._reviews.save(
                    discovery_source=planned["discovery_source"],
                    provider_group_id=planned.get("provider_group_id") or planned["group_id"],
                    stable_group_key=planned["stable_group_key"],
                    member_set_key=planned["member_set_key"],
                    member_fingerprint=planned["member_fingerprint"],
                    manual_action=planned["action"],
                    manual_primary_asset_id=(
                        UUID(planned["keeper_asset_id"])
                        if planned.get("keeper_asset_id") is not None
                        else None
                    ),
                    review_status=review_statuses[planned["action"]],
                )
                await self._reviews.complete_draft(
                    planned["discovery_source"],
                    planned["stable_group_key"],
                    planned["member_fingerprint"],
                )
            await self._reviews.consume_workspace_groups(
                [
                    planned["stable_group_key"]
                    for planned in raw_groups
                    if planned["group_id"] in successful_ids
                ],
                list(successful_ids),
            )

        status = "completed" if not failed_ids else "failed"
        follow_up_pending_ids = [
            planned["group_id"]
            for planned in raw_groups
            if execution_state(planned) == "follow_up_pending"
        ]
        result = {
            "group_count": len(raw_groups),
            "processed_group_count": len(successful_ids),
            "resolved_group_count": len(resolved_ids),
            "kept_all_group_count": len(kept_ids),
            "zero_survivor_group_count": len(zero_survivor_ids),
            "stacked_group_count": len(stacked_ids),
            "failed_group_ids": failed_ids,
            "drifted_group_ids": drifted_ids,
            "follow_up_pending_group_ids": follow_up_pending_ids,
            "trashed_asset_count": len(trashed_ids),
            "verified": not failed_ids,
        }
        await self._actions.finish_plan(plan_id, status, result)
        logger.info(
            "Duplicate action timing: groups=%s resolved=%s failed=%s "
            "preflight_seconds=%.3f metadata_seconds=%.3f "
            "immich_resolution_seconds=%.3f follow_up_seconds=%.3f total_seconds=%.3f",
            len(raw_groups),
            len(resolved_ids),
            len(failed_ids),
            preflight_done - action_started,
            metadata_done - preflight_done,
            resolution_done - metadata_done,
            perf_counter() - resolution_done,
            perf_counter() - action_started,
        )
        return TaskResult(
            status=status,
            summary=result,
            counters={
                "groups_processed": len(successful_ids),
                "groups_resolved": len(resolved_ids),
                "groups_kept_all": len(kept_ids),
                "groups_zero_survivor": len(zero_survivor_ids),
                "groups_stacked": len(stacked_ids),
                "groups_failed": len(failed_ids),
                "assets_trashed": len(trashed_ids),
            },
        )

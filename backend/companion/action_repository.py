"""Persistence boundary for reviewed action plans and execution audits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from companion.action_schema import (
    ActionPlanStatus,
    AssetActionOperation,
    AssetActionPlanRequest,
    AssetSelectionResolution,
)
from companion.contained_duplicate_resolution import (
    ContainedDuplicateResolutionFailed,
    _duplicate_plan_digest,
    _execution_duplicate_groups,
    _has_contained_resolution_steps,
    _is_contained_resolution_step,
    expand_contained_duplicate_plan,
)
from companion.database import DatabaseManager
from companion.models import ActionPlanRecord


class ActionRepository:
    """Persist immutable previews and mutable execution outcomes."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def create_plan(
        self,
        request: AssetActionPlanRequest,
        resolution: AssetSelectionResolution,
        operation: AssetActionOperation,
        applicable_ids: list[UUID],
        skipped_ids: list[UUID],
        relation_work: dict[str, Any],
        target_digest: str,
        expires_at: datetime,
    ) -> ActionPlanRecord:
        """Persist one reviewed target snapshot."""

        record = ActionPlanRecord(
            action=request.action,
            operation=operation,
            relation_id=request.relation_ids[0] if len(request.relation_ids) == 1 else None,
            relation_ids=[str(identifier) for identifier in request.relation_ids],
            relation_work=relation_work,
            selection=request.selection.model_dump(mode="json"),
            target_ids=[str(identifier) for identifier in resolution.ids],
            target_digest=target_digest,
            applicable_ids=[str(identifier) for identifier in applicable_ids],
            skipped_ids=[str(identifier) for identifier in skipped_ids],
            missing_ids=[str(identifier) for identifier in resolution.missing_ids],
            destructive=operation == "trash",
            status="planned",
            expires_at=expires_at,
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)
        return record

    async def create_duplicate_plan(
        self,
        *,
        groups: list[dict[str, Any]],
        options: dict[str, Any],
        target_digest: str,
        expires_at: datetime,
    ) -> ActionPlanRecord:
        """Persist an immutable reviewed duplicate resolution."""

        public_groups = [dict(group) for group in groups]
        public_target_digest = target_digest
        persisted_groups = await expand_contained_duplicate_plan(self._database, public_groups)
        persisted_target_digest = _duplicate_plan_digest(persisted_groups)
        execution_groups = _execution_duplicate_groups(persisted_groups)
        target_ids = list(
            dict.fromkeys(
                asset_id
                for group in persisted_groups
                for asset_id in group["member_asset_ids"]
            )
        )
        trash_ids = list(
            dict.fromkeys(
                asset_id
                for group in execution_groups
                for asset_id in group.get("trash_asset_ids", [])
            )
        )
        record = ActionPlanRecord(
            action="resolve_duplicates",
            operation="resolve_duplicates",
            relation_ids=[],
            relation_work={"groups": persisted_groups, "options": options},
            selection={"mode": "duplicate_groups"},
            target_ids=target_ids,
            target_digest=persisted_target_digest,
            applicable_ids=trash_ids,
            skipped_ids=[],
            missing_ids=[],
            destructive=bool(trash_ids),
            status="planned",
            expires_at=expires_at,
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)

        # The API preview remains exactly the reviewed selection. Contained groups are internal
        # execution steps and appear later as their own resolution-history entries.
        record.relation_work = {"groups": public_groups, "options": options}
        record.target_digest = public_target_digest
        return record

    async def create_collection_delete_plan(
        self,
        *,
        entity_kind: str,
        selection_id: UUID,
        target_ids: list[UUID],
        applicable_ids: list[UUID],
        skipped_ids: list[UUID],
        target_digest: str,
        expires_at: datetime,
    ) -> ActionPlanRecord:
        """Freeze one album/tag deletion preview independently of later selection edits."""

        record = ActionPlanRecord(
            action=f"delete_{entity_kind}s",
            operation="delete_relation",
            relation_ids=[],
            relation_work={"entity_kind": entity_kind, "selection_id": str(selection_id)},
            selection={"mode": "selection", "selection_id": str(selection_id)},
            target_ids=[str(identifier) for identifier in target_ids],
            target_digest=target_digest,
            applicable_ids=[str(identifier) for identifier in applicable_ids],
            skipped_ids=[str(identifier) for identifier in skipped_ids],
            missing_ids=[],
            destructive=True,
            status="planned",
            result={
                "items": [
                    {
                        "id": str(identifier),
                        "status": "skipped",
                        "reason": "Not applicable when the plan was created.",
                    }
                    for identifier in skipped_ids
                ]
            },
            expires_at=expires_at,
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)
            await session.flush()
        return record

    async def create_trash_purge_plan(
        self,
        *,
        selection: dict[str, Any],
        target_ids: list[UUID],
        target_count: int,
        target_digest: str,
        mode: str,
        expires_at: datetime,
    ) -> ActionPlanRecord:
        """Persist an immutable review of permanent trash deletion targets."""

        record = ActionPlanRecord(
            action="empty_trash" if mode == "empty_all" else "delete_trash_assets",
            operation="purge_trash",
            relation_ids=[],
            relation_work={"mode": mode, "target_count": target_count},
            selection=selection,
            target_ids=[str(identifier) for identifier in target_ids],
            target_digest=target_digest,
            applicable_ids=[str(identifier) for identifier in target_ids],
            skipped_ids=[],
            missing_ids=[],
            destructive=True,
            status="planned",
            expires_at=expires_at,
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)
            await session.flush()
        return record

    async def claim_trash_purge_plan(
        self, plan_id: UUID, *, stale_after: timedelta = timedelta(minutes=5)
    ) -> ActionPlanRecord | None:
        """Atomically claim a new or safely abandoned trash deletion plan."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if (
                record is None
                or record.operation != "purge_trash"
                or record.status not in {"planned", "running"}
            ):
                return None
            if record.status == "running" and (
                record.executed_at is None or record.executed_at > now - stale_after
            ):
                return None
            if record.status == "planned" and record.expires_at <= now:
                return None
            record.status = "running"
            record.executed_at = now
            record.result = {
                **(record.result or {}),
                "purge_lease_token": str(uuid4()),
            }
        return record

    async def checkpoint_trash_purge_plan(
        self, plan_id: UUID, result: dict[str, Any], *, lease_token: str
    ) -> None:
        """Durably checkpoint one bounded trash purge pass."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if (
                record is None
                or record.operation != "purge_trash"
                or record.status != "running"
                or (record.result or {}).get("purge_lease_token") != lease_token
            ):
                raise ValueError("Trash purge plan is no longer owned")
            record.result = {**(record.result or {}), **result}
            record.executed_at = datetime.now(UTC)

    async def finish_trash_purge_plan(
        self,
        plan_id: UUID,
        status: ActionPlanStatus,
        result: dict[str, Any],
        *,
        lease_token: str,
    ) -> bool:
        """Finalize a purge only if this executor still owns its lease."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if (
                record is None
                or record.operation != "purge_trash"
                or record.status != "running"
                or (record.result or {}).get("purge_lease_token") != lease_token
            ):
                return False
            record.status = status
            record.result = {**(record.result or {}), **result}
            record.executed_at = datetime.now(UTC)
        return True

    async def get_plan(self, plan_id: UUID) -> ActionPlanRecord | None:
        """Load one action plan without changing its persistent state."""

        async with self._database.sessions() as session:
            record = await session.get(ActionPlanRecord, plan_id)
        if record is None or record.action != "resolve_duplicates":
            return record

        groups = record.relation_work.get("groups", [])
        if not isinstance(groups, list):
            return record
        persisted_groups = [dict(group) for group in groups if isinstance(group, dict)]
        persisted_digest = _duplicate_plan_digest(persisted_groups)
        if record.target_digest is not None and record.target_digest != persisted_digest:
            # Keep the original view so the service's normal fingerprint check reports drift.
            return record
        execution_groups = _execution_duplicate_groups(persisted_groups)
        if execution_groups != persisted_groups:
            record.relation_work = {
                **record.relation_work,
                "groups": execution_groups,
            }
            record.target_digest = _duplicate_plan_digest(execution_groups)
        return record

    async def claim_plan(self, plan_id: UUID) -> ActionPlanRecord | None:
        """Atomically move a planned record to running."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if record is None or record.status != "planned":
                return None
            record.status = "running"
        return record

    async def claim_collection_delete_plan(
        self, plan_id: UUID, *, stale_after: timedelta = timedelta(minutes=5)
    ) -> ActionPlanRecord | None:
        """Claim a new, failed, or abandoned collection plan for resumption."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if record is None or record.operation != "delete_relation":
                return None
            if record.status == "running" and record.executed_at is not None:
                if record.executed_at > now - stale_after:
                    return None
            elif record.status not in {"planned", "failed", "partial", "running"}:
                return None
            if (
                record.status == "planned"
                and record.expires_at <= now
                and not (record.result or {}).get("work_ids")
            ):
                return None
            record.status = "running"
            record.executed_at = now
        return record

    async def start_collection_delete_pass(
        self, plan_id: UUID, work_ids: list[str]
    ) -> None:
        """Freeze the next bounded execution pass over unresolved target IDs."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if record is None or record.operation != "delete_relation":
                raise ValueError("Delete plan was not found")
            result = dict(record.result or {})
            result["work_ids"] = work_ids
            result["work_index"] = 0
            record.result = result
            record.executed_at = datetime.now(UTC)

    async def record_collection_delete_item_result(
        self, plan_id: UUID, item: dict[str, str | None], *, next_index: int | None = None
    ) -> None:
        """Checkpoint one API outcome before moving to the next target."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if record is None or record.operation != "delete_relation":
                raise ValueError("Delete plan was not found")
            result = dict(record.result or {})
            items = [
                existing
                for existing in result.get("items", [])
                if existing["id"] != item["id"]
            ]
            items.append(item)
            result["items"] = items
            if next_index is not None:
                result["work_index"] = next_index
            record.result = result
            record.executed_at = datetime.now(UTC)

    async def finish_collection_delete_plan(
        self, plan_id: UUID, status: ActionPlanStatus
    ) -> None:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if record is None or record.operation != "delete_relation":
                raise ValueError("Delete plan was not found")
            record.status = status
            record.executed_at = datetime.now(UTC)

    async def reopen_duplicate_follow_up(self, plan_id: UUID) -> ActionPlanRecord | None:
        """Reopen a failed plan when durable asset or stack work remains."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            states = (record.result or {}).get("group_execution", {}) if record else {}
            groups = (record.relation_work or {}).get("groups", []) if record else []
            if (
                record is None
                or record.action != "resolve_duplicates"
                or record.status != "failed"
                or _has_contained_resolution_steps(groups)
                or not any(
                    item.get("state") in {"failed", "follow_up_pending"}
                    for item in states.values()
                    if isinstance(item, dict)
                )
            ):
                return None
            record.result = {
                **(record.result or {}),
                "group_execution": {
                    group_id: (
                        {**item, "state": "pending", "error": None}
                        if isinstance(item, dict) and item.get("state") == "failed"
                        else item
                    )
                    for group_id, item in states.items()
                },
            }
            record.status = "planned"
            record.executed_at = None
        return record

    async def record_duplicate_group_execution(
        self,
        plan_id: UUID,
        group_id: str,
        state: str,
        *,
        error: str | None = None,
    ) -> None:
        """Durably checkpoint one duplicate group's mutation phase."""

        abort_contained = False
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            if record is None:
                return
            result = dict(record.result or {})
            group_execution = dict(result.get("group_execution") or {})
            group_execution[group_id] = {
                "state": state,
                "error": error,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            result["group_execution"] = group_execution
            record.result = result
            if state in {"failed", "drifted"}:
                planned_group = next(
                    (
                        group
                        for group in (record.relation_work or {}).get("groups", [])
                        if isinstance(group, dict) and str(group.get("group_id")) == group_id
                    ),
                    None,
                )
                abort_contained = bool(
                    planned_group is not None and _is_contained_resolution_step(planned_group)
                )

        if abort_contained:
            raise ContainedDuplicateResolutionFailed(group_id, state, error)

    async def finish_plan(
        self,
        plan_id: UUID,
        status: ActionPlanStatus,
        result: dict[str, Any],
    ) -> None:
        """Persist a final plan state and safe result payload."""

        async with self._database.sessions() as session, session.begin():
            record = await session.get(ActionPlanRecord, plan_id)
            if record is None:
                return
            record.status = status
            previous = record.result or {}
            group_execution = previous.get(
                "group_execution",
                result.get("group_execution", {}),
            )
            if group_execution:
                result["group_execution"] = group_execution
            record.result = {
                **result,
                "group_execution": group_execution,
            }
            record.executed_at = datetime.now(UTC)

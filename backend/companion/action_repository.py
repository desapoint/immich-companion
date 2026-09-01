"""Persistence boundary for reviewed action plans and execution audits."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from companion.action_schema import (
    ActionPlanStatus,
    AssetActionOperation,
    AssetActionPlanRequest,
    AssetSelectionResolution,
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
        """Persist an immutable reviewed Immich duplicate resolution."""

        target_ids = [asset_id for group in groups for asset_id in group["member_asset_ids"]]
        trash_ids = [asset_id for group in groups for asset_id in group["trash_asset_ids"]]
        record = ActionPlanRecord(
            action="resolve_duplicates",
            operation="resolve_duplicates",
            relation_ids=[],
            relation_work={"groups": groups, "options": options},
            selection={"mode": "duplicate_groups"},
            target_ids=target_ids,
            target_digest=target_digest,
            applicable_ids=trash_ids,
            skipped_ids=[],
            missing_ids=[],
            destructive=bool(trash_ids),
            status="planned",
            expires_at=expires_at,
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)
        return record

    async def get_plan(self, plan_id: UUID) -> ActionPlanRecord | None:
        """Load one action plan without changing its state."""

        async with self._database.sessions() as session:
            return await session.get(ActionPlanRecord, plan_id)

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

    async def reopen_duplicate_follow_up(self, plan_id: UUID) -> ActionPlanRecord | None:
        """Reopen a failed plan only when durable stack follow-up work remains."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(ActionPlanRecord).where(ActionPlanRecord.id == plan_id).with_for_update()
            )
            states = (record.result or {}).get("group_execution", {}) if record else {}
            if (
                record is None
                or record.action != "resolve_duplicates"
                or record.status != "failed"
                or not any(
                    item.get("state") == "follow_up_pending"
                    for item in states.values()
                    if isinstance(item, dict)
                )
            ):
                return None
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
            record.result = {
                **result,
                "group_execution": previous.get(
                    "group_execution",
                    result.get("group_execution", {}),
                ),
            }
            record.executed_at = datetime.now(UTC)

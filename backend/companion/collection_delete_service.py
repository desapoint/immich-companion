"""Restartable, API-only album and tag deletion plans."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from companion.action_repository import ActionRepository
from companion.immich import ImmichApiClient, ImmichApiError, ImmichTag
from companion.models import ActionPlanRecord
from companion.selection_repository import RelationEntityKind, RelationSelectionRepository


class CollectionDeletePlanError(ValueError):
    """A collection delete plan cannot be executed in its current state."""


class CollectionDeletePlanBusyError(CollectionDeletePlanError):
    """Another request currently owns the plan."""


def tag_delete_targets(
    target_ids: list[UUID], catalog: list[ImmichTag]
) -> tuple[list[UUID], list[UUID]]:
    """Only delete parents when every child is targeted; process children first."""

    by_id = {tag.id: tag for tag in catalog}
    children: dict[UUID, list[UUID]] = {}
    for tag in catalog:
        if tag.parent_id is not None:
            children.setdefault(tag.parent_id, []).append(tag.id)
    target_set = set(target_ids)

    def eligible(identifier: UUID, visiting: frozenset[UUID] = frozenset()) -> bool:
        if identifier in visiting or identifier not in by_id:
            return False
        next_visiting = visiting | {identifier}
        return all(
            child in target_set and eligible(child, next_visiting)
            for child in children.get(identifier, [])
        )

    def depth(identifier: UUID) -> int:
        level = 0
        visited = {identifier}
        parent_id = by_id[identifier].parent_id
        while parent_id is not None and parent_id in by_id and parent_id not in visited:
            level += 1
            visited.add(parent_id)
            parent_id = by_id[parent_id].parent_id
        return level

    applicable = [identifier for identifier in target_ids if eligible(identifier)]
    applicable.sort(key=depth, reverse=True)
    applicable_set = set(applicable)
    skipped = [identifier for identifier in target_ids if identifier not in applicable_set]
    return applicable, skipped


class CollectionDeleteService:
    MAX_ITEMS_PER_REQUEST = 100

    def __init__(
        self,
        actions: ActionRepository,
        selections: RelationSelectionRepository,
        immich: ImmichApiClient,
        *,
        allow_destructive_actions: bool,
    ) -> None:
        self._actions = actions
        self._selections = selections
        self._immich = immich
        self._allow_destructive_actions = allow_destructive_actions

    async def execute(self, kind: RelationEntityKind, plan_id: UUID) -> ActionPlanRecord:
        existing = await self._actions.get_plan(plan_id)
        if existing is None or existing.action != f"delete_{kind}s":
            raise CollectionDeletePlanError("Delete plan was not found.")
        if existing.status == "completed":
            return existing
        if (
            existing.status == "planned"
            and existing.expires_at <= datetime.now(UTC)
            and not (existing.result or {}).get("work_ids")
        ):
            raise CollectionDeletePlanError("Delete plan has expired.")
        if not self._allow_destructive_actions:
            raise CollectionDeletePlanError("Relation deletion is disabled in safe mode.")
        previous_status = existing.status
        record = await self._actions.claim_collection_delete_plan(plan_id)
        if record is None:
            raise CollectionDeletePlanBusyError("Delete plan is already executing.")

        selection_id = UUID(record.relation_work["selection_id"])
        results = {item["id"]: item for item in (record.result or {}).get("items", [])}
        try:
            for raw_id in record.skipped_ids:
                if raw_id not in results:
                    item = {
                        "id": raw_id,
                        "status": "skipped",
                        "reason": "Not applicable when the plan was created.",
                    }
                    await self._actions.record_collection_delete_item_result(plan_id, item)
                    results[raw_id] = item

            work_ids = list((record.result or {}).get("work_ids") or [])
            work_index = int((record.result or {}).get("work_index") or 0)
            if not work_ids or (work_index >= len(work_ids) and previous_status == "failed"):
                work_ids = (
                    [
                        raw_id
                        for raw_id in record.applicable_ids
                        if results.get(raw_id, {}).get("status") == "failed"
                    ]
                    if previous_status == "failed"
                    else list(record.applicable_ids)
                )
                work_index = 0
                await self._actions.start_collection_delete_pass(plan_id, work_ids)

            stop = min(len(work_ids), work_index + self.MAX_ITEMS_PER_REQUEST)
            for index in range(work_index, stop):
                raw_id = work_ids[index]
                identifier = UUID(raw_id)
                try:
                    if kind == "album":
                        await self._immich.delete_album(identifier)
                    else:
                        await self._immich.delete_tag(identifier)
                except ImmichApiError as error:
                    item = (
                        {"id": raw_id, "status": "skipped", "reason": "Already missing."}
                        if error.status_code == 404
                        else {
                            "id": raw_id,
                            "status": "failed",
                            "reason": "Immich could not delete this relation.",
                        }
                    )
                else:
                    item = {"id": raw_id, "status": "completed", "reason": None}
                await self._actions.record_collection_delete_item_result(
                    plan_id, item, next_index=index + 1
                )
                results[raw_id] = item

            if stop < len(work_ids):
                await self._actions.finish_collection_delete_plan(plan_id, "partial")
                refreshed = await self._actions.get_plan(plan_id)
                assert refreshed is not None
                return refreshed

            catalog = (
                await self._immich.list_album_catalog()
                if kind == "album"
                else await self._immich.list_tag_catalog()
            )
            still_present = {item.id for item in catalog}
            for raw_id in record.applicable_ids:
                item = results[raw_id]
                if item["status"] in {"completed", "skipped"} and UUID(raw_id) in still_present:
                    failed = {
                        "id": raw_id,
                        "status": "failed",
                        "reason": "Still present in Immich after deletion.",
                    }
                    await self._actions.record_collection_delete_item_result(plan_id, failed)
                    results[raw_id] = failed

            # Reconcile the workspace only after API verification. Replayed calls
            # can safely repeat this removal after a checkpointed crash.
            confirmed_removed = [
                UUID(raw_id)
                for raw_id in record.applicable_ids
                if results[raw_id]["status"] in {"completed", "skipped"}
            ]
            await self._selections.remove(selection_id, confirmed_removed)

            status = "failed" if any(
                results[raw_id]["status"] == "failed" for raw_id in record.applicable_ids
            ) else "completed"
            await self._actions.finish_collection_delete_plan(plan_id, status)
        except Exception:
            await self._actions.finish_collection_delete_plan(plan_id, "failed")
            raise
        refreshed = await self._actions.get_plan(plan_id)
        assert refreshed is not None
        return refreshed

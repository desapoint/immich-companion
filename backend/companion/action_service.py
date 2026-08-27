"""Reviewable, idempotent asset action orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import monotonic, perf_counter
from uuid import UUID

from companion.action_repository import ActionRepository
from companion.action_schema import (
    AssetActionExecuteRequest,
    AssetActionOperation,
    AssetActionPlan,
    AssetActionPlanRequest,
    AssetActionRelationPlan,
    AssetActionRelationResult,
    AssetActionResult,
    AssetSelectionRequest,
    AssetSelectionResolution,
    StackConflict,
)
from companion.asset_repository import AssetRepository
from companion.asset_service import AssetSyncService
from companion.config import Settings
from companion.immich import ImmichApiClient, ImmichApiError
from companion.models import ActionPlanRecord
from companion.sync_settings import DefaultSyncRuntimeSettingsRepository
from companion.task_coordinator import PermanentTaskError, RetryableTaskError, TaskContext
from companion.task_schema import TaskResult


class ActionPlanNotFoundError(RuntimeError):
    """Raised when a requested plan does not exist."""


class ActionPlanConflictError(RuntimeError):
    """Raised when a plan is stale, already used, or its targets drifted."""


class DestructiveActionsDisabledError(RuntimeError):
    """Raised when trash is disabled by safe runtime configuration."""


class EmptySelectionError(RuntimeError):
    """Raised when none of the requested assets exist in the synchronized index."""


def selection_digest(ids: list[UUID]) -> str:
    """Return a stable digest for a resolved target set."""

    value = "\n".join(sorted(str(identifier) for identifier in ids))
    return sha256(value.encode()).hexdigest()


class AssetActionService:
    """Plan, execute, synchronize, and verify supported Immich mutations."""

    def __init__(
        self,
        settings: Settings,
        immich: ImmichApiClient,
        assets: AssetRepository,
        actions: ActionRepository,
        sync: AssetSyncService,
        runtime_sync_settings: object | None = None,
    ) -> None:
        self._settings = settings
        self._immich = immich
        self._assets = assets
        self._actions = actions
        self._sync = sync
        self._runtime_sync_settings = (
            runtime_sync_settings
            if runtime_sync_settings is not None
            else DefaultSyncRuntimeSettingsRepository(settings)
        )

    async def _pace_large_action_batch(self, started: float, *, enabled: bool) -> None:
        """Rest between large-action batches without delaying small actions."""

        if not enabled:
            return
        pacing = await self._runtime_sync_settings.get()
        await asyncio.sleep(
            max(pacing.full_min_batch_delay_seconds, perf_counter() - started)
        )

    async def _repair_targets(
        self,
        asset_ids: list[UUID],
        relations: list[tuple[str, UUID]] | None = None,
        include_stacks: bool = False,
    ) -> None:
        """Use targeted repair while retaining compatibility with sync adapters."""

        repair = getattr(self._sync, "reconcile_targets", None)
        if repair is not None:
            await repair(asset_ids, relations=relations, include_stacks=include_stacks)
        else:
            await self._sync.synchronize()

    async def _stack_repair_ids(self, asset_ids: list[UUID]) -> list[UUID]:
        """Snapshot every member whose stack metadata can change after an action."""

        repair_ids: list[UUID] = []
        for asset_id in asset_ids:
            members = await self._assets.stack_asset_ids(asset_id)
            for member_id in members or [asset_id]:
                if member_id not in repair_ids:
                    repair_ids.append(member_id)
        return repair_ids

    async def _remaining_stack_members(self, asset_ids: list[UUID]) -> set[UUID]:
        """Verify stack creation after Immich has indexed the mutation."""

        remaining = set(asset_ids)
        for attempt in range(3):
            stacked_ids = {
                member.id for stack in await self._immich.list_stacks() for member in stack.assets
            }
            remaining = {identifier for identifier in asset_ids if identifier not in stacked_ids}
            if not remaining:
                return remaining
            if attempt < 2:
                await asyncio.sleep(0.2)
        return remaining

    async def resolve_selection(self, selection: AssetSelectionRequest) -> AssetSelectionResolution:
        """Expose exact backend selection resolution and mixed-state summary."""

        return await self._assets.resolve_selection(
            selection,
            max_targets=self._settings.action_max_targets,
        )

    @staticmethod
    def _operation_for_request(
        request: AssetActionPlanRequest,
        resolution: AssetSelectionResolution,
    ) -> AssetActionOperation:
        if request.action == "archive_toggle":
            action = resolution.summary.archive_action
            assert action is not None
            return action
        if request.action == "favorite_toggle":
            action = resolution.summary.favorite_action
            assert action is not None
            return action
        return request.action

    @staticmethod
    def _public_plan(record: ActionPlanRecord) -> AssetActionPlan:
        relation_ids = [UUID(identifier) for identifier in record.relation_ids]
        relations = [
            AssetActionRelationPlan(
                relation_id=relation_id,
                applicable_count=len(
                    record.relation_work.get(str(relation_id), {}).get("applicable_ids", [])
                ),
                skipped_count=len(
                    record.relation_work.get(str(relation_id), {}).get("skipped_ids", [])
                ),
            )
            for relation_id in relation_ids
        ]
        return AssetActionPlan(
            id=record.id,
            action=record.action,
            operation=record.operation,
            relation_ids=relation_ids,
            relations=relations,
            target_count=len(record.target_ids),
            applicable_count=(
                sum(relation.applicable_count for relation in relations)
                if relations
                else len(record.applicable_ids)
            ),
            skipped_count=(
                sum(relation.skipped_count for relation in relations)
                if relations
                else len(record.skipped_ids)
            ),
            missing_ids=[UUID(identifier) for identifier in record.missing_ids],
            destructive=record.destructive,
            status=record.status,
            expires_at=record.expires_at,
            stack_conflicts=[
                StackConflict.model_validate(item)
                for item in record.relation_work.get("__stack_conflicts", [])
            ],
        )

    async def _stack_conflicts(self, asset_ids: list[UUID]) -> list[StackConflict]:
        selected = set(asset_ids)
        conflicts: list[StackConflict] = []
        for stack in await self._immich.list_stacks():
            selected_count = sum(member.id in selected for member in stack.assets)
            if selected_count:
                conflicts.append(
                    StackConflict(
                        stack_id=stack.id,
                        selected_count=selected_count,
                        member_count=len(stack.assets),
                        includes_unselected=selected_count < len(stack.assets),
                    )
                )
        return conflicts

    async def plan(self, request: AssetActionPlanRequest) -> AssetActionPlan:
        """Resolve current state and persist an immutable action preview."""

        resolution = await self.resolve_selection(request.selection)
        if not resolution.ids:
            raise EmptySelectionError("No synchronized assets matched the selection")
        original_target_digest = selection_digest(resolution.ids)
        operation = self._operation_for_request(request, resolution)
        stack_conflicts: list[StackConflict] = []
        if operation == "stack":
            stack_conflicts = await self._stack_conflicts(resolution.ids)
            if stack_conflicts and request.stack_resolution is None:
                relation_work = {
                    "__stack_conflicts": [item.model_dump(mode="json") for item in stack_conflicts]
                }
                record = await self._actions.create_plan(
                    request,
                    resolution,
                    operation,
                    [],
                    resolution.ids,
                    relation_work,
                    selection_digest(resolution.ids),
                    datetime.now(UTC) + timedelta(seconds=self._settings.action_plan_ttl_seconds),
                )
                return self._public_plan(record)
            if request.stack_resolution == "keep_existing":
                stacked_ids = {
                    member.id
                    for stack in await self._immich.list_stacks()
                    for member in stack.assets
                }
                resolution = resolution.model_copy(
                    update={
                        "ids": [
                            identifier
                            for identifier in resolution.ids
                            if identifier not in stacked_ids
                        ]
                    }
                )
                if len(resolution.ids) < 2:
                    raise EmptySelectionError("Fewer than two unstacked assets remain")
            relation_work = {
                "__stack_conflicts": [] if request.stack_resolution else [
                    item.model_dump(mode="json") for item in stack_conflicts
                ],
                "__stack_resolution": request.stack_resolution or "move_selected",
            }
        else:
            relation_work = {}
        if operation == "remove_stack":
            expanded_ids: list[UUID] = []
            for asset_id in resolution.ids:
                for member_id in await self._assets.stack_asset_ids(asset_id):
                    if member_id not in expanded_ids:
                        expanded_ids.append(member_id)
            resolution = resolution.model_copy(update={"ids": expanded_ids})
            if not resolution.ids:
                raise EmptySelectionError("The selected asset is not in a synchronized stack")
        if operation == "trash" and not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError("Trash actions are disabled")
        applicable_union: set[UUID] = set()
        skipped_union: set[UUID] = set()
        if request.relation_ids:
            for relation_id in request.relation_ids:
                applicable_set = await self._assets.applicable_action_ids(
                    operation,
                    resolution.ids,
                    relation_id,
                )
                applicable = [
                    identifier for identifier in resolution.ids if identifier in applicable_set
                ]
                skipped = [
                    identifier for identifier in resolution.ids if identifier not in applicable_set
                ]
                applicable_union.update(applicable)
                skipped_union.update(skipped)
                relation_work[str(relation_id)] = {
                    "applicable_ids": [str(identifier) for identifier in applicable],
                    "skipped_ids": [str(identifier) for identifier in skipped],
                }
        else:
            applicable_set = await self._assets.applicable_action_ids(
                operation,
                resolution.ids,
            )
            applicable_union = applicable_set
            skipped_union = set(resolution.ids) - applicable_set
        if operation == "stack":
            applicable_union = set(resolution.ids)
            skipped_union = set()
        applicable_ids = [
            identifier for identifier in resolution.ids if identifier in applicable_union
        ]
        skipped_ids = [identifier for identifier in resolution.ids if identifier in skipped_union]
        record = await self._actions.create_plan(
            request,
            resolution,
            operation,
            applicable_ids,
            skipped_ids,
            relation_work,
            original_target_digest
            if operation in {"stack", "remove_stack"}
            else selection_digest(resolution.ids),
            datetime.now(UTC) + timedelta(seconds=self._settings.action_plan_ttl_seconds),
        )
        return self._public_plan(record)

    async def _apply(
        self,
        operation: AssetActionOperation,
        ids: list[UUID],
        relation_id: UUID | None,
    ) -> None:
        if not ids:
            return
        if operation == "stack":
            await self._immich.create_stack(ids)
        elif operation == "set_stack_primary":
            selected = set(ids)
            for stack in await self._immich.list_stacks():
                for asset_id in (member.id for member in stack.assets if member.id in selected):
                    await self._immich.update_stack_primary(stack.id, asset_id)
        elif operation == "remove_from_stack":
            selected = set(ids)
            for stack in await self._immich.list_stacks():
                selected_members = [member.id for member in stack.assets if member.id in selected]
                if not selected_members:
                    continue
                if len(selected_members) == len(stack.assets):
                    await self._immich.delete_stack(stack.id)
                    continue
                if stack.primary_asset_id in selected:
                    replacement = next(
                        member.id for member in stack.assets if member.id not in selected
                    )
                    await self._immich.update_stack_primary(stack.id, replacement)
                for asset_id in selected_members:
                    await self._immich.remove_asset_from_stack(stack.id, asset_id)
        elif operation == "remove_stack":
            selected = set(ids)
            for stack in await self._immich.list_stacks():
                if any(member.id in selected for member in stack.assets):
                    await self._immich.delete_stack(stack.id)
        elif operation == "remove_album":
            assert relation_id is not None
            await self._immich.remove_assets_from_album(relation_id, ids)
        elif operation == "add_album":
            assert relation_id is not None
            await self._immich.add_assets_to_album(relation_id, ids)
        elif operation == "remove_tag":
            assert relation_id is not None
            await self._immich.remove_assets_from_tag(relation_id, ids)
        elif operation == "add_tag":
            assert relation_id is not None
            await self._immich.add_assets_to_tag(relation_id, ids)
        elif operation in {"archive", "unarchive"}:
            await self._immich.set_assets_archived(ids, operation == "archive")
        elif operation in {"favorite", "unfavorite"}:
            await self._immich.set_assets_favorite(ids, operation == "favorite")
        elif operation == "trash":
            await self._immich.trash_assets(ids)
        else:
            await self._immich.restore_assets(ids)

    async def _prepare_stack(
        self, asset_ids: list[UUID], resolution: str | None
    ) -> tuple[list[UUID], list[UUID]]:
        """Resolve existing stack membership before creating the requested stack."""

        resolution = resolution or "move_selected"
        selected = set(asset_ids)
        final_ids = list(asset_ids)
        affected_ids = list(asset_ids)
        for stack in await self._immich.list_stacks():
            member_ids = [member.id for member in stack.assets]
            selected_members = [identifier for identifier in member_ids if identifier in selected]
            if not selected_members:
                continue
            for identifier in member_ids:
                if identifier not in affected_ids:
                    affected_ids.append(identifier)
            if resolution == "keep_existing":
                final_ids = [identifier for identifier in final_ids if identifier not in member_ids]
                continue
            if resolution == "include_existing":
                for identifier in member_ids:
                    if identifier not in final_ids:
                        final_ids.append(identifier)
                await self._immich.delete_stack(stack.id)
                continue
            if len(selected_members) == len(member_ids):
                await self._immich.delete_stack(stack.id)
            else:
                if stack.primary_asset_id in selected:
                    replacement_primary = next(
                        identifier for identifier in member_ids if identifier not in selected
                    )
                    await self._immich.update_stack_primary(stack.id, replacement_primary)
                for identifier in selected_members:
                    await self._immich.remove_asset_from_stack(stack.id, identifier)
        if len(final_ids) < 2:
            raise EmptySelectionError("Fewer than two assets remain for a stack")
        return final_ids, affected_ids

    async def _execute_relations(
        self,
        record: ActionPlanRecord,
        operation: AssetActionOperation,
        target_ids: list[UUID],
        progress: Callable[[int, int, str], Awaitable[None]] | None = None,
        *,
        batch_size: int,
        throttle: bool,
    ) -> AssetActionResult:
        """Apply, refresh once, and verify every relation in a reviewed plan."""

        initial: dict[UUID, tuple[list[UUID], list[UUID]]] = {}
        api_failed: dict[UUID, list[UUID]] = {}
        successful_relations: list[UUID] = []
        relation_total = len(target_ids) * len(record.relation_ids)
        relation_processed = 0
        for relation_text in record.relation_ids:
            relation_id = UUID(relation_text)
            applicable_set = await self._assets.applicable_action_ids(
                operation,
                target_ids,
                relation_id,
            )
            applicable = [identifier for identifier in target_ids if identifier in applicable_set]
            skipped = [identifier for identifier in target_ids if identifier not in applicable_set]
            initial[relation_id] = (applicable, skipped)
            relation_processed += len(skipped)
            try:
                action_batches = self._batches(applicable, operation, batch_size)
                for index, batch in enumerate(action_batches):
                    batch_started = perf_counter()
                    await self._apply(operation, batch, relation_id)
                    relation_processed += len(batch)
                    if progress is not None:
                        await progress(
                            relation_processed,
                            relation_total,
                            f"Updated {relation_processed}/{relation_total} media relationships",
                        )
                    if index + 1 < len(action_batches):
                        await self._pace_large_action_batch(batch_started, enabled=throttle)
                successful_relations.append(relation_id)
            except Exception:
                api_failed[relation_id] = applicable

        has_successful_changes = any(
            initial[relation_id][0] for relation_id in successful_relations
        )
        if successful_relations and has_successful_changes:
            try:
                relation = "album" if operation in {"add_album", "remove_album"} else "tag"
                await self._repair_targets(
                    target_ids,
                    relations=[(relation, relation_id) for relation_id in successful_relations],
                )
            except Exception as error:
                relation_results = [
                    AssetActionRelationResult(
                        relation_id=relation_id,
                        applied_ids=[],
                        skipped_ids=initial[relation_id][1],
                        failed_ids=initial[relation_id][0],
                    )
                    for relation_id in initial
                ]
                result = self._relation_result(record, operation, target_ids, relation_results)
                await self._actions.finish_plan(
                    record.id,
                    "failed",
                    {
                        **result.model_dump(mode="json"),
                        "error": type(error).__name__,
                    },
                )
                raise

        relation_results: list[AssetActionRelationResult] = []
        for relation_id, (applicable, skipped) in initial.items():
            if relation_id in api_failed:
                failed = api_failed[relation_id]
            else:
                remaining = await self._assets.applicable_action_ids(
                    operation,
                    applicable,
                    relation_id,
                )
                failed = [identifier for identifier in applicable if identifier in remaining]
            relation_results.append(
                AssetActionRelationResult(
                    relation_id=relation_id,
                    applied_ids=[
                        identifier for identifier in applicable if identifier not in failed
                    ],
                    skipped_ids=skipped,
                    failed_ids=failed,
                )
            )
        result = self._relation_result(record, operation, target_ids, relation_results)
        await self._actions.finish_plan(
            record.id,
            result.status,
            result.model_dump(mode="json"),
        )
        return result

    @staticmethod
    def _relation_result(
        record: ActionPlanRecord,
        operation: AssetActionOperation,
        target_ids: list[UUID],
        relation_results: list[AssetActionRelationResult],
    ) -> AssetActionResult:
        applied_ids = list(
            dict.fromkeys(
                identifier for outcome in relation_results for identifier in outcome.applied_ids
            )
        )
        skipped_ids = list(
            dict.fromkeys(
                identifier for outcome in relation_results for identifier in outcome.skipped_ids
            )
        )
        failed_ids = list(
            dict.fromkeys(
                identifier for outcome in relation_results for identifier in outcome.failed_ids
            )
        )
        failed_count = sum(len(outcome.failed_ids) for outcome in relation_results)
        return AssetActionResult(
            plan_id=record.id,
            operation=operation,
            target_count=len(target_ids),
            applied_count=sum(len(outcome.applied_ids) for outcome in relation_results),
            skipped_count=sum(len(outcome.skipped_ids) for outcome in relation_results),
            applied_ids=applied_ids,
            skipped_ids=skipped_ids,
            failed_ids=failed_ids,
            relation_results=relation_results,
            verified=failed_count == 0,
            status="completed" if failed_count == 0 else "failed",
        )

    async def execute(
        self,
        request: AssetActionExecuteRequest,
        progress: Callable[[int, int, str], Awaitable[None]] | None = None,
        *,
        resume: bool = False,
    ) -> AssetActionResult:
        """Execute a current reviewed plan once, then synchronize and verify it."""

        existing = await self._actions.get_plan(request.plan_id)
        if existing is None:
            raise ActionPlanNotFoundError("Action plan was not found")
        if existing.status != "planned" and not (resume and existing.status == "running"):
            raise ActionPlanConflictError("Action plan has already been used")
        if existing.expires_at <= datetime.now(UTC):
            await self._actions.finish_plan(existing.id, "expired", {"error": "expired"})
            raise ActionPlanConflictError("Action plan has expired")
        if existing.destructive and not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError("Trash actions are disabled")

        selection = AssetSelectionRequest.model_validate(existing.selection)
        resolution = await self.resolve_selection(selection)
        # Whole-stack removal expands the reviewed selection into immutable
        # stack-member targets during planning. Its execution must use those
        # frozen targets, including for plans created before that expansion
        # stopped being included in target_digest.
        if (
            existing.operation != "remove_stack"
            and selection_digest(resolution.ids) != existing.target_digest
        ):
            await self._actions.finish_plan(existing.id, "drifted", {"error": "target_drift"})
            raise ActionPlanConflictError("The selected assets changed after review")

        claimed = (
            existing
            if existing.status == "running"
            else await self._actions.claim_plan(existing.id)
        )
        if claimed is None:
            raise ActionPlanConflictError("Action plan has already been used")
        target_ids = [UUID(identifier) for identifier in claimed.target_ids]
        operation = claimed.operation
        pacing = await self._runtime_sync_settings.get()
        batch_size = pacing.full_batch_size
        throttle = len(target_ids) > batch_size
        if operation == "stack":
            try:
                target_ids, stack_repair_ids = await self._prepare_stack(
                    target_ids,
                    claimed.relation_work.get("__stack_resolution"),
                )
            except Exception as error:
                await self._actions.finish_plan(
                    claimed.id,
                    "failed",
                    {
                        "operation": operation,
                        "target_count": len(target_ids),
                        "applied_count": 0,
                        "skipped_count": 0,
                        "applied_ids": [],
                        "skipped_ids": [],
                        "failed_ids": [str(identifier) for identifier in target_ids],
                        "verified": False,
                        "error": type(error).__name__,
                    },
                )
                raise
        if claimed.relation_ids:
            return await self._execute_relations(
                claimed,
                operation,
                target_ids,
                progress,
                batch_size=batch_size,
                throttle=throttle,
            )
        relation_id = claimed.relation_id
        applicable_set = await self._assets.applicable_action_ids(
            operation,
            target_ids,
            relation_id,
        )
        applicable_ids = [identifier for identifier in target_ids if identifier in applicable_set]
        skipped_count = len(target_ids) - len(applicable_ids)

        try:
            repair_ids = applicable_ids
            if operation in {"set_stack_primary", "remove_from_stack", "remove_stack"}:
                # Capture the complete old stack before the first member is
                # removed, so remaining and detached members are both repaired.
                repair_ids = await self._stack_repair_ids(target_ids)
            updated = 0
            action_batches = self._batches(applicable_ids, operation, batch_size)
            for index, batch in enumerate(action_batches):
                batch_started = perf_counter()
                await self._apply(operation, batch, relation_id)
                updated += len(batch)
                if progress is not None:
                    await progress(
                        skipped_count + updated,
                        len(target_ids),
                        f"Updated {skipped_count + updated}/{len(target_ids)} assets",
                    )
                if index + 1 < len(action_batches):
                    await self._pace_large_action_batch(batch_started, enabled=throttle)
            if applicable_ids:
                if operation == "stack":
                    repair_ids = stack_repair_ids
                await self._repair_targets(
                    repair_ids,
                    include_stacks=operation in {
                        "stack",
                        "set_stack_primary",
                        "remove_from_stack",
                        "remove_stack",
                    },
                )
            if operation == "stack":
                # Stacking is a positive state change. The generic applicability
                # query intentionally returns every asset for this operation, so
                # it cannot also be used as its post-action verifier. Ask
                # Immich for the authoritative stack membership instead.
                remaining = await self._remaining_stack_members(applicable_ids)
            elif operation == "set_stack_primary":
                current_stacks = await self._immich.list_stacks()
                primary_ids = {stack.primary_asset_id for stack in current_stacks}
                remaining = {
                    identifier for identifier in applicable_ids if identifier not in primary_ids
                }
            else:
                remaining = await self._assets.applicable_action_ids(
                    operation,
                    applicable_ids,
                    relation_id,
                )
        except ImmichApiError as error:
            result_payload = {
                "operation": operation,
                "target_count": len(target_ids),
                "applied_count": 0,
                "skipped_count": skipped_count,
                "applied_ids": [],
                "skipped_ids": [
                    str(identifier) for identifier in target_ids if identifier not in applicable_set
                ],
                "failed_ids": [str(identifier) for identifier in applicable_ids],
                "verified": False,
                "error": error.operation,
            }
            await self._actions.finish_plan(claimed.id, "failed", result_payload)
            raise
        except Exception as error:
            result_payload = {
                "operation": operation,
                "target_count": len(target_ids),
                "applied_count": 0,
                "skipped_count": skipped_count,
                "applied_ids": [],
                "skipped_ids": [
                    str(identifier) for identifier in target_ids if identifier not in applicable_set
                ],
                "failed_ids": [str(identifier) for identifier in applicable_ids],
                "verified": False,
                "error": type(error).__name__,
            }
            await self._actions.finish_plan(claimed.id, "failed", result_payload)
            raise

        failed_ids = [identifier for identifier in applicable_ids if identifier in remaining]
        applied_ids = [identifier for identifier in applicable_ids if identifier not in remaining]
        skipped_ids = [identifier for identifier in target_ids if identifier not in applicable_set]
        status = "completed" if not failed_ids else "failed"
        result = AssetActionResult(
            plan_id=claimed.id,
            operation=operation,
            target_count=len(target_ids),
            applied_count=len(applied_ids),
            skipped_count=skipped_count,
            applied_ids=applied_ids,
            skipped_ids=skipped_ids,
            failed_ids=failed_ids,
            verified=not failed_ids,
            status=status,
        )
        await self._actions.finish_plan(
            claimed.id,
            status,
            result.model_dump(mode="json"),
        )
        return result

    def _batches(
        self, ids: list[UUID], operation: AssetActionOperation, batch_size: int
    ) -> list[list[UUID]]:
        """Bound remote mutations so task progress advances per media batch."""

        if not ids:
            return []
        # A stack must be created as one operation or it would create several
        # independent stacks instead of the reviewed single stack.
        if operation == "stack":
            return [ids]
        return [ids[index : index + batch_size] for index in range(0, len(ids), batch_size)]


class AssetActionTaskHandler:
    """Run reviewed bulk actions as durable coordinator tasks."""

    task_type = "asset_action"
    lane_key = "asset_action"
    max_concurrency = 1

    def __init__(self, service: AssetActionService) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, object]) -> TaskResult:
        plan_id = UUID(str(payload["plan_id"]))
        plan = await self._service._actions.get_plan(plan_id)
        total = len(plan.target_ids) if plan is not None else 0
        pacing = await self._service._runtime_sync_settings.get()
        batch_size = pacing.full_batch_size
        batch_count = (total + batch_size - 1) // batch_size if total else 0
        started = monotonic()

        def telemetry(completed: int) -> dict[str, object]:
            elapsed = max(monotonic() - started, 0.001)
            rate = completed / elapsed
            remaining = max(total - completed, 0)
            return {
                "batch": min((completed + batch_size - 1) // batch_size, batch_count),
                "batches": batch_count,
                "batch_size": batch_size,
                "minimum_delay_seconds": pacing.full_min_batch_delay_seconds,
                "assets_per_second": round(rate, 2),
                "estimated_remaining_seconds": round(remaining / rate, 1) if rate else None,
            }

        await context.checkpoint(
            checkpoint={"phase": "executing", "plan_id": str(plan_id)},
            counters={"requested": total, "processed": 0},
            progress={
                "phase": "action",
                "completed": 0,
                "total": total,
                "percent": 0,
                **telemetry(0),
            },
        )

        async def report(completed: int, progress_total: int, detail: str) -> None:
            percent = (
                round(completed / progress_total * 100, 1) if progress_total else 100.0
            )
            await context.checkpoint(
                checkpoint={
                    "phase": "executing",
                    "plan_id": str(plan_id),
                    "processed": completed,
                },
                counters={"requested": progress_total, "processed": completed},
                progress={
                    "phase": "action",
                    "completed": completed,
                    "total": progress_total,
                    "percent": percent,
                    "detail": detail,
                    **telemetry(completed),
                },
            )

        try:
            result = await self._service.execute(
                AssetActionExecuteRequest(plan_id=plan_id, confirm=True),
                progress=report,
                resume=context.task.status == "recovering",
            )
        except ImmichApiError as error:
            raise RetryableTaskError(str(error)) from error
        except Exception as error:
            raise PermanentTaskError(str(error)) from error
        completed = result.applied_count + result.skipped_count + len(result.failed_ids)
        await context.checkpoint(
            checkpoint={"phase": "complete", "plan_id": str(plan_id)},
            counters={"requested": result.target_count, "processed": completed},
            progress={
                "phase": "action",
                "completed": completed,
                "total": result.target_count,
                "percent": 100,
                **telemetry(completed),
            },
        )
        return TaskResult(
            status="completed" if result.status == "completed" else "failed",
            summary=result.model_dump(mode="json"),
            counters={"requested": result.target_count, "processed": completed},
        )

"""Reviewable, idempotent asset action orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
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
)
from companion.asset_repository import AssetRepository
from companion.asset_service import AssetSyncService
from companion.config import Settings
from companion.immich import ImmichApiClient, ImmichApiError
from companion.models import ActionPlanRecord


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
    ) -> None:
        self._settings = settings
        self._immich = immich
        self._assets = assets
        self._actions = actions
        self._sync = sync

    async def _repair_targets(self, asset_ids: list[UUID]) -> None:
        """Use targeted repair while retaining compatibility with sync adapters."""

        repair = getattr(self._sync, "reconcile_targets", None)
        if repair is not None:
            await repair(asset_ids)
        else:
            await self._sync.synchronize()

    async def _record_relation_change(
        self,
        operation: AssetActionOperation,
        relation_id: UUID,
        asset_ids: list[UUID],
    ) -> None:
        """Mirror a confirmed Immich relation mutation in the local index."""

        apply_delta = getattr(self._assets, "apply_membership_event", None)
        if apply_delta is None:
            return
        relation = "album" if operation in {"add_album", "remove_album"} else "tag"
        present = operation.startswith("add_")
        for asset_id in asset_ids:
            await apply_delta(relation, relation_id, asset_id, present)

    async def resolve_selection(
        self, selection: AssetSelectionRequest
    ) -> AssetSelectionResolution:
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
                    record.relation_work.get(str(relation_id), {}).get(
                        "applicable_ids", []
                    )
                ),
                skipped_count=len(
                    record.relation_work.get(str(relation_id), {}).get(
                        "skipped_ids", []
                    )
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
        )

    async def plan(self, request: AssetActionPlanRequest) -> AssetActionPlan:
        """Resolve current state and persist an immutable action preview."""

        resolution = await self.resolve_selection(request.selection)
        if not resolution.ids:
            raise EmptySelectionError("No synchronized assets matched the selection")
        operation = self._operation_for_request(request, resolution)
        if operation == "trash" and not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError("Trash actions are disabled")
        relation_work: dict[str, dict[str, list[str]]] = {}
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
                    identifier
                    for identifier in resolution.ids
                    if identifier in applicable_set
                ]
                skipped = [
                    identifier
                    for identifier in resolution.ids
                    if identifier not in applicable_set
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
        applicable_ids = [
            identifier for identifier in resolution.ids if identifier in applicable_union
        ]
        skipped_ids = [
            identifier for identifier in resolution.ids if identifier in skipped_union
        ]
        record = await self._actions.create_plan(
            request,
            resolution,
            operation,
            applicable_ids,
            skipped_ids,
            relation_work,
            selection_digest(resolution.ids),
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
        if operation == "remove_album":
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

    async def _execute_relations(
        self,
        record: ActionPlanRecord,
        operation: AssetActionOperation,
        target_ids: list[UUID],
    ) -> AssetActionResult:
        """Apply, refresh once, and verify every relation in a reviewed plan."""

        initial: dict[UUID, tuple[list[UUID], list[UUID]]] = {}
        api_failed: dict[UUID, list[UUID]] = {}
        successful_relations: list[UUID] = []
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
            try:
                await self._apply(operation, applicable, relation_id)
                await self._record_relation_change(operation, relation_id, applicable)
                successful_relations.append(relation_id)
            except Exception:
                api_failed[relation_id] = applicable

        has_successful_changes = any(
            initial[relation_id][0] for relation_id in successful_relations
        )
        if successful_relations and has_successful_changes:
            try:
                await self._repair_targets(target_ids)
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
                        identifier
                        for identifier in applicable
                        if identifier not in failed
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
                identifier
                for outcome in relation_results
                for identifier in outcome.applied_ids
            )
        )
        skipped_ids = list(
            dict.fromkeys(
                identifier
                for outcome in relation_results
                for identifier in outcome.skipped_ids
            )
        )
        failed_ids = list(
            dict.fromkeys(
                identifier
                for outcome in relation_results
                for identifier in outcome.failed_ids
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

    async def execute(self, request: AssetActionExecuteRequest) -> AssetActionResult:
        """Execute a current reviewed plan once, then synchronize and verify it."""

        existing = await self._actions.get_plan(request.plan_id)
        if existing is None:
            raise ActionPlanNotFoundError("Action plan was not found")
        if existing.status != "planned":
            raise ActionPlanConflictError("Action plan has already been used")
        if existing.expires_at <= datetime.now(UTC):
            await self._actions.finish_plan(existing.id, "expired", {"error": "expired"})
            raise ActionPlanConflictError("Action plan has expired")
        if existing.destructive and not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError("Trash actions are disabled")

        selection = AssetSelectionRequest.model_validate(existing.selection)
        resolution = await self.resolve_selection(selection)
        if selection_digest(resolution.ids) != existing.target_digest:
            await self._actions.finish_plan(existing.id, "drifted", {"error": "target_drift"})
            raise ActionPlanConflictError("The selected assets changed after review")

        claimed = await self._actions.claim_plan(existing.id)
        if claimed is None:
            raise ActionPlanConflictError("Action plan has already been used")
        target_ids = [UUID(identifier) for identifier in claimed.target_ids]
        operation = claimed.operation
        if claimed.relation_ids:
            return await self._execute_relations(claimed, operation, target_ids)
        relation_id = claimed.relation_id
        applicable_set = await self._assets.applicable_action_ids(
            operation,
            target_ids,
            relation_id,
        )
        applicable_ids = [identifier for identifier in target_ids if identifier in applicable_set]
        skipped_count = len(target_ids) - len(applicable_ids)

        try:
            await self._apply(operation, applicable_ids, relation_id)
            if applicable_ids:
                await self._repair_targets(applicable_ids)
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
                    str(identifier)
                    for identifier in target_ids
                    if identifier not in applicable_set
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
                    str(identifier)
                    for identifier in target_ids
                    if identifier not in applicable_set
                ],
                "failed_ids": [str(identifier) for identifier in applicable_ids],
                "verified": False,
                "error": type(error).__name__,
            }
            await self._actions.finish_plan(claimed.id, "failed", result_payload)
            raise

        failed_ids = [identifier for identifier in applicable_ids if identifier in remaining]
        applied_ids = [
            identifier for identifier in applicable_ids if identifier not in remaining
        ]
        skipped_ids = [
            identifier for identifier in target_ids if identifier not in applicable_set
        ]
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

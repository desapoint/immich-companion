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
        return AssetActionPlan(
            id=record.id,
            action=record.action,
            operation=record.operation,
            relation_id=record.relation_id,
            target_count=len(record.target_ids),
            applicable_count=len(record.applicable_ids),
            skipped_count=len(record.skipped_ids),
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
        applicable_set = await self._assets.applicable_action_ids(
            operation,
            resolution.ids,
            request.relation_id,
        )
        applicable_ids = [
            identifier for identifier in resolution.ids if identifier in applicable_set
        ]
        skipped_ids = [
            identifier for identifier in resolution.ids if identifier not in applicable_set
        ]
        record = await self._actions.create_plan(
            request,
            resolution,
            operation,
            applicable_ids,
            skipped_ids,
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
        elif operation == "remove_tag":
            assert relation_id is not None
            await self._immich.remove_assets_from_tag(relation_id, ids)
        elif operation in {"archive", "unarchive"}:
            await self._immich.set_assets_archived(ids, operation == "archive")
        elif operation in {"favorite", "unfavorite"}:
            await self._immich.set_assets_favorite(ids, operation == "favorite")
        elif operation == "trash":
            await self._immich.trash_assets(ids)
        else:
            await self._immich.restore_assets(ids)

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
                await self._sync.synchronize()
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

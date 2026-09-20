"""Reviewed, restart-safe boundary for permanent deletion from Immich trash."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from companion.action_repository import ActionRepository
from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
    DestructiveActionsDisabledError,
    selection_digest,
)
from companion.config import Settings
from companion.immich import ImmichApiClient, ImmichApiError


class TrashPurgeSelection(BaseModel):
    """Explicit trash assets or the complete current trash collection."""

    ids: list[UUID] = Field(default_factory=list, max_length=50_000)
    all: bool = False
    excluded_ids: list[UUID] = Field(default_factory=list, max_length=50_000)

    @model_validator(mode="after")
    def validate_target(self) -> TrashPurgeSelection:
        self.ids = list(dict.fromkeys(self.ids))
        self.excluded_ids = list(dict.fromkeys(self.excluded_ids))
        if self.all == bool(self.ids):
            raise ValueError("Specify either one or more ids or all=true.")
        if self.ids and self.excluded_ids:
            raise ValueError("excluded_ids are only valid with all=true.")
        return self


class TrashPurgePlan(BaseModel):
    id: UUID
    mode: str
    target_count: int
    expires_at: datetime
    destructive: bool = True


class TrashPurgeExecuteRequest(BaseModel):
    plan_id: UUID
    confirm: bool


class TrashPurgeResult(BaseModel):
    plan_id: UUID
    requested: int
    deleted: int
    failed_ids: list[UUID]
    deleted_ids: list[UUID]
    verified: bool
    status: str


def _unordered_snapshot_add(accumulator: int, asset_id: UUID) -> int:
    value = int.from_bytes(sha256(asset_id.bytes).digest(), "big")
    return (accumulator + value) % (1 << 256)


class TrashPurgeService:
    """Freeze, execute, and verify permanent trash deletion operations."""

    def __init__(
        self,
        immich: ImmichApiClient,
        actions: ActionRepository,
        settings: Settings,
    ) -> None:
        self._immich = immich
        self._actions = actions
        self._settings = settings

    async def _all_snapshot(self) -> tuple[int, str]:
        count = 0
        accumulator = 0
        async for asset in self._immich.iter_trashed_assets():
            count += 1
            accumulator = _unordered_snapshot_add(accumulator, asset.id)
        return count, f"{count}:{accumulator:064x}"

    async def _resolve_selected(self, selection: TrashPurgeSelection) -> list[UUID]:
        if selection.ids:
            if len(selection.ids) > self._settings.action_max_targets:
                raise ActionPlanConflictError(
                    "Permanent deletion exceeds the configured action target limit"
                )
            resolved = []
            for asset_id in selection.ids:
                try:
                    asset = await self._immich.get_asset(asset_id)
                except ImmichApiError as error:
                    raise ActionPlanConflictError(
                        f"Trash asset {asset_id} is no longer available"
                    ) from error
                if not asset.is_trashed:
                    raise ActionPlanConflictError(
                        f"Asset {asset_id} is no longer in trash"
                    )
                resolved.append(asset_id)
            return resolved

        excluded = set(selection.excluded_ids)
        resolved = []
        async for asset in self._immich.iter_trashed_assets():
            if asset.id in excluded:
                continue
            resolved.append(asset.id)
            if len(resolved) > self._settings.action_max_targets:
                raise ActionPlanConflictError(
                    "Selective permanent deletion exceeds the configured action target limit. "
                    "Empty the complete trash or reduce the selection."
                )
        return resolved

    async def plan(self, selection: TrashPurgeSelection) -> TrashPurgePlan:
        if not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError(
                "Permanent trash deletion is disabled by server configuration"
            )
        mode = "empty_all" if selection.all and not selection.excluded_ids else "selected"
        if mode == "empty_all":
            target_count, target_digest = await self._all_snapshot()
            target_ids: list[UUID] = []
        else:
            target_ids = await self._resolve_selected(selection)
            target_count = len(target_ids)
            target_digest = selection_digest(target_ids)
        if target_count == 0:
            raise ActionPlanConflictError("No matching trashed assets were found")
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.action_plan_ttl_seconds
        )
        record = await self._actions.create_trash_purge_plan(
            selection=selection.model_dump(mode="json"),
            target_ids=target_ids,
            target_count=target_count,
            target_digest=target_digest,
            mode=mode,
            expires_at=expires_at,
        )
        return TrashPurgePlan(
            id=record.id,
            mode=mode,
            target_count=target_count,
            expires_at=expires_at,
        )

    async def _is_deleted(self, asset_id: UUID) -> bool:
        try:
            asset = await self._immich.get_asset(asset_id)
        except ImmichApiError as error:
            return error.status_code == 404
        return not asset.is_trashed

    async def execute(self, request: TrashPurgeExecuteRequest) -> TrashPurgeResult:
        if not request.confirm:
            raise ActionPlanConflictError("Permanent deletion requires explicit confirmation")
        record = await self._actions.get_plan(request.plan_id)
        if record is None or record.operation != "purge_trash":
            raise ActionPlanNotFoundError("Trash deletion plan was not found")
        if record.status != "planned":
            raise ActionPlanConflictError("Trash deletion plan has already been used")
        if record.expires_at <= datetime.now(UTC):
            await self._actions.finish_plan(record.id, "expired", {"error": "expired"})
            raise ActionPlanConflictError("Trash deletion plan has expired")
        if not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError(
                "Permanent trash deletion is disabled by server configuration"
            )

        mode = str(record.relation_work.get("mode", "selected"))
        requested = int(record.relation_work.get("target_count", 0))
        if mode == "empty_all":
            current_count, current_digest = await self._all_snapshot()
            if current_count != requested or current_digest != record.target_digest:
                await self._actions.finish_plan(
                    record.id, "drifted", {"error": "trash_changed_after_review"}
                )
                raise ActionPlanConflictError("Trash changed after review; create a new plan")
            claimed = await self._actions.claim_trash_purge_plan(record.id)
            if claimed is None:
                raise ActionPlanConflictError("Trash deletion plan could not be claimed")
            reported = await self._immich.empty_trash()
            remaining_count, _ = await self._all_snapshot()
            deleted = max(0, requested - remaining_count)
            verified = remaining_count == 0
            result = {
                "requested": requested,
                "deleted": deleted,
                "reported_deleted": reported,
                "remaining": remaining_count,
                "failed_ids": [],
                "verified": verified,
            }
            await self._actions.finish_plan(
                record.id, "completed" if verified else "partial", result
            )
            return TrashPurgeResult(
                plan_id=record.id,
                requested=requested,
                deleted=deleted,
                failed_ids=[],
                deleted_ids=[],
                verified=verified,
                status="completed" if verified else "partial",
            )

        target_ids = [UUID(value) for value in record.target_ids]
        current_ids = await self._resolve_selected(
            TrashPurgeSelection(ids=target_ids)
        )
        if selection_digest(current_ids) != record.target_digest:
            await self._actions.finish_plan(
                record.id, "drifted", {"error": "trash_changed_after_review"}
            )
            raise ActionPlanConflictError("Selected trash assets changed after review")
        claimed = await self._actions.claim_trash_purge_plan(record.id)
        if claimed is None:
            raise ActionPlanConflictError("Trash deletion plan could not be claimed")

        failed_ids: list[UUID] = []
        batch_size = min(self._settings.sync_full_batch_size, 1000)
        for offset in range(0, len(target_ids), batch_size):
            batch = target_ids[offset : offset + batch_size]
            with suppress(ImmichApiError):
                await self._immich.permanently_delete_assets(batch)
            deleted_states = await asyncio.gather(
                *(self._is_deleted(asset_id) for asset_id in batch)
            )
            failed_ids.extend(
                asset_id
                for asset_id, deleted in zip(batch, deleted_states, strict=True)
                if not deleted
            )
        deleted = len(target_ids) - len(failed_ids)
        verified = not failed_ids
        result = {
            "requested": len(target_ids),
            "deleted": deleted,
            "failed_ids": [str(asset_id) for asset_id in failed_ids],
            "verified": verified,
        }
        await self._actions.finish_plan(
            record.id, "completed" if verified else "partial", result
        )
        return TrashPurgeResult(
            plan_id=record.id,
            requested=len(target_ids),
            deleted=deleted,
            failed_ids=failed_ids,
            deleted_ids=[asset_id for asset_id in target_ids if asset_id not in failed_ids],
            verified=verified,
            status="completed" if verified else "partial",
        )

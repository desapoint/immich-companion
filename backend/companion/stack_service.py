"""Shared planning and execution for reviewed Immich stack creation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from companion.action_schema import StackConflict, StackResolution
from companion.asset_repository import AssetRepository
from companion.asset_service import AssetSyncService
from companion.immich import ImmichApiClient


@dataclass(frozen=True, slots=True)
class StackPreparation:
    """Frozen stack creation inputs after resolving existing memberships."""

    asset_ids: list[UUID]
    affected_ids: list[UUID]


class StackSelectionError(RuntimeError):
    """Raised when conflict resolution leaves too few assets to stack."""


class StackService:
    """Discover conflicts and perform one reviewed stack workflow."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        sync: AssetSyncService,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._sync = sync

    async def conflicts(self, asset_ids: list[UUID]) -> list[StackConflict]:
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

    async def without_existing_members(self, asset_ids: list[UUID]) -> list[UUID]:
        stacked_ids = {
            member.id
            for stack in await self._immich.list_stacks()
            for member in stack.assets
        }
        remaining = [identifier for identifier in asset_ids if identifier not in stacked_ids]
        self._require_stackable(remaining)
        return remaining

    async def prepare(
        self,
        asset_ids: list[UUID],
        resolution: StackResolution | None,
    ) -> StackPreparation:
        """Resolve existing memberships using the reviewed conflict mode."""

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
        self._require_stackable(final_ids)
        return StackPreparation(asset_ids=final_ids, affected_ids=affected_ids)

    async def execute(self, preparation: StackPreparation) -> bool:
        """Create, repair, and verify one prepared stack through Immich APIs."""

        await self._immich.create_stack(preparation.asset_ids)
        await self._repair_targets(preparation.affected_ids)
        return await self._creation_visible(preparation.asset_ids[0])

    async def repair_ids(self, asset_ids: list[UUID]) -> list[UUID]:
        """Snapshot every member whose stack metadata can change."""

        repair_ids: list[UUID] = []
        for asset_id in asset_ids:
            members = await self._assets.stack_asset_ids(asset_id)
            for member_id in members or [asset_id]:
                if member_id not in repair_ids:
                    repair_ids.append(member_id)
        return repair_ids

    async def _repair_targets(self, asset_ids: list[UUID]) -> None:
        repair = getattr(self._sync, "reconcile_targets", None)
        if repair is not None:
            await repair(asset_ids, include_stacks=True)
        else:
            await self._sync.synchronize()

    async def _creation_visible(self, primary_asset_id: UUID) -> bool:
        for attempt in range(3):
            stacks = await self._immich.list_stacks()
            if any(stack.primary_asset_id == primary_asset_id for stack in stacks):
                return True
            if attempt < 2:
                await asyncio.sleep(0.2)
        return False

    @staticmethod
    def _require_stackable(asset_ids: list[UUID]) -> None:
        if len(asset_ids) < 2:
            raise StackSelectionError("Fewer than two assets remain for a stack")

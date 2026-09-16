"""Shared planning and execution for reviewed Immich stack creation."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from companion.action_schema import StackConflict, StackResolution
from companion.asset_repository import AssetRepository
from companion.asset_service import AssetSyncService
from companion.immich import ImmichApiClient, ImmichStack

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StackPreparation:
    """Frozen stack creation inputs after resolving existing memberships."""

    asset_ids: list[UUID]
    affected_ids: list[UUID]
    primary_asset_id: UUID


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

    async def conflict_snapshot(self, asset_ids: list[UUID]) -> list[dict[str, object]]:
        """Freeze exact existing-stack inputs for later drift validation."""

        return self.select_conflict_snapshot(asset_ids, await self.stack_snapshot())

    async def stack_snapshot(self) -> list[dict[str, object]]:
        """Read the current stack topology once for one planning operation."""

        return sorted(
            [
                {
                    "stack_id": str(stack.id),
                    "primary_asset_id": str(stack.primary_asset_id),
                    "member_asset_ids": sorted(str(member.id) for member in stack.assets),
                }
                for stack in await self._immich.list_stacks()
            ],
            key=lambda item: str(item["stack_id"]),
        )

    @staticmethod
    def select_conflict_snapshot(
        asset_ids: list[UUID],
        snapshot: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Select relevant topology from an already bounded shared snapshot."""

        selected = set(asset_ids)
        selected_text = {str(identifier) for identifier in selected}
        return [
            item
            for item in snapshot
            if selected_text.intersection(
                str(identifier) for identifier in item["member_asset_ids"]
            )
        ]

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
        primary_asset_id: UUID | None = None,
    ) -> StackPreparation:
        """Resolve existing memberships using the reviewed conflict mode."""

        resolution = resolution or "move_selected"
        primary_asset_id = primary_asset_id or asset_ids[0]
        if primary_asset_id not in asset_ids:
            raise StackSelectionError("The chosen stack primary is not selected")
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
            remaining_members = [
                identifier for identifier in member_ids if identifier not in selected
            ]
            if len(remaining_members) < 2:
                await self._immich.delete_stack(stack.id)
            else:
                if stack.primary_asset_id in selected:
                    replacement_primary = remaining_members[0]
                    await self._immich.update_stack_primary(stack.id, replacement_primary)
                for identifier in selected_members:
                    await self._immich.remove_asset_from_stack(stack.id, identifier)
        if primary_asset_id not in final_ids:
            raise StackSelectionError(
                "The chosen stack primary is unavailable with this conflict resolution"
            )
        self._require_stackable(final_ids)
        ordered_ids = [
            primary_asset_id,
            *(identifier for identifier in final_ids if identifier != primary_asset_id),
        ]
        return StackPreparation(
            asset_ids=ordered_ids,
            affected_ids=affected_ids,
            primary_asset_id=primary_asset_id,
        )

    async def remove_members(self, asset_ids: list[UUID]) -> list[UUID]:
        """Remove members while preserving the invariant that stacks have at least two assets."""

        selected = set(asset_ids)
        affected_ids: list[UUID] = []
        for stack in await self._immich.list_stacks():
            member_ids = [member.id for member in stack.assets]
            selected_members = [identifier for identifier in member_ids if identifier in selected]
            if not selected_members:
                continue
            for identifier in member_ids:
                if identifier not in affected_ids:
                    affected_ids.append(identifier)
            remaining_members = [
                identifier for identifier in member_ids if identifier not in selected
            ]
            if len(remaining_members) < 2:
                await self._immich.delete_stack(stack.id)
                continue
            if stack.primary_asset_id in selected:
                await self._immich.update_stack_primary(stack.id, remaining_members[0])
            for identifier in selected_members:
                await self._immich.remove_asset_from_stack(stack.id, identifier)
        return affected_ids

    async def execute(self, preparation: StackPreparation) -> bool:
        """Create, repair, and verify one prepared stack through Immich APIs."""

        started = perf_counter()
        await self._immich.create_stack(preparation.asset_ids)
        created = perf_counter()
        visible, stacks = await self._verified_stack_snapshot(preparation.primary_asset_id)
        verified = perf_counter()
        await self._repair_targets(preparation.affected_ids, stacks=stacks)
        logger.info(
            "Stack action timing: assets=%s confirmed=%s immich_seconds=%.3f "
            "verification_seconds=%.3f reconciliation_seconds=%.3f total_seconds=%.3f",
            len(preparation.affected_ids), visible, created - started,
            verified - created, perf_counter() - verified, perf_counter() - started,
        )
        return visible

    async def repair_ids(self, asset_ids: list[UUID]) -> list[UUID]:
        """Snapshot every affected member from Immich's authoritative topology."""

        selected = set(asset_ids)
        repair_ids: list[UUID] = []
        for stack in await self._immich.list_stacks():
            member_ids = [member.id for member in stack.assets]
            if not selected.intersection(member_ids):
                continue
            for member_id in member_ids:
                if member_id not in repair_ids:
                    repair_ids.append(member_id)
        for asset_id in asset_ids:
            if asset_id not in repair_ids:
                repair_ids.append(asset_id)
        return repair_ids

    async def _repair_targets(
        self, asset_ids: list[UUID], *, stacks: list[ImmichStack] | None = None
    ) -> None:
        enqueue = getattr(self._sync, "enqueue_asset_repair_during_sync", None)
        snapshot = getattr(self._sync, "apply_stack_snapshot_for_targets", None)
        if (
            enqueue is not None
            and snapshot is not None
            and await enqueue(asset_ids, include_stacks=True)
        ):
            await snapshot(asset_ids, stacks=stacks)
            return
        repair = getattr(self._sync, "reconcile_targets", None)
        if repair is not None:
            await repair(asset_ids, include_stacks=True)
        else:
            await self._sync.synchronize()

    async def _creation_visible(self, primary_asset_id: UUID) -> bool:
        visible, _ = await self._verified_stack_snapshot(primary_asset_id)
        return visible

    async def _verified_stack_snapshot(
        self, primary_asset_id: UUID
    ) -> tuple[bool, list[ImmichStack]]:
        for attempt in range(3):
            stacks = await self._immich.list_stacks()
            if any(stack.primary_asset_id == primary_asset_id for stack in stacks):
                return True, stacks
            if attempt < 2:
                await asyncio.sleep(0.2)
        return False, stacks

    @staticmethod
    def _require_stackable(asset_ids: list[UUID]) -> None:
        if len(asset_ids) < 2:
            raise StackSelectionError("Fewer than two assets remain for a stack")

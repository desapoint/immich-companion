"""Shared planning and execution for reviewed Immich stack creation."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from companion.action_schema import StackConflict, StackResolution, StackResolutionSelection
from companion.asset_repository import AssetRepository
from companion.asset_service import AssetSyncService
from companion.immich import ImmichApiClient, ImmichStack

logger = logging.getLogger(__name__)

_STACK_RESOLUTIONS = {"keep_existing", "move_selected", "include_existing"}


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
            member_ids = [member.id for member in stack.assets]
            selected_ids = [identifier for identifier in member_ids if identifier in selected]
            if not selected_ids:
                continue
            ordered_members = [
                stack.primary_asset_id,
                *(identifier for identifier in member_ids if identifier != stack.primary_asset_id),
            ]
            conflicts.append(
                StackConflict(
                    stack_id=stack.id,
                    primary_asset_id=stack.primary_asset_id,
                    member_asset_ids=ordered_members,
                    selected_asset_ids=[
                        identifier for identifier in ordered_members if identifier in selected
                    ],
                    selected_count=len(selected_ids),
                    member_count=len(member_ids),
                    includes_unselected=len(selected_ids) < len(member_ids),
                )
            )
        return sorted(conflicts, key=lambda item: str(item.stack_id))

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

    @staticmethod
    def _normalize_resolution(
        resolution: StackResolutionSelection | str | None,
    ) -> StackResolutionSelection:
        if resolution is None:
            return "move_selected"
        if isinstance(resolution, dict):
            normalized: dict[str, StackResolution] = {}
            for stack_id, choice in resolution.items():
                try:
                    UUID(str(stack_id))
                except (TypeError, ValueError) as error:
                    raise StackSelectionError("Stack resolution keys must be stack UUIDs") from error
                if choice not in _STACK_RESOLUTIONS:
                    raise StackSelectionError("Unknown stack conflict resolution")
                normalized[str(stack_id)] = choice
            return normalized
        if resolution in _STACK_RESOLUTIONS:
            return resolution  # type: ignore[return-value]
        try:
            decoded = json.loads(resolution)
        except (TypeError, json.JSONDecodeError) as error:
            raise StackSelectionError("Invalid saved stack conflict resolution") from error
        if not isinstance(decoded, dict):
            raise StackSelectionError("Saved stack conflict resolution must be an object")
        return StackService._normalize_resolution(decoded)

    @staticmethod
    def _resolution_for_stack(
        resolution: StackResolutionSelection,
        stack_id: UUID,
    ) -> StackResolution:
        if isinstance(resolution, dict):
            choice = resolution.get(str(stack_id))
            if choice is None:
                raise StackSelectionError(
                    "Every existing stack conflict needs a reviewed resolution"
                )
            return choice
        return resolution

    async def prepare(
        self,
        asset_ids: list[UUID],
        resolution: StackResolutionSelection | str | None,
        primary_asset_id: UUID | None = None,
    ) -> StackPreparation:
        """Validate all reviewed choices, then reconcile each existing membership."""

        reviewed_resolution = self._normalize_resolution(resolution)
        primary_asset_id = primary_asset_id or asset_ids[0]
        if primary_asset_id not in asset_ids:
            raise StackSelectionError("The chosen stack primary is not selected")
        selected = set(asset_ids)
        final_ids = list(asset_ids)
        affected_ids = list(asset_ids)
        reviewed_stacks: list[
            tuple[ImmichStack, list[UUID], list[UUID], StackResolution]
        ] = []

        # Build the complete reconciliation plan first. In particular, resolve every
        # per-stack choice before changing any existing Immich stack so an incomplete
        # map cannot partially mutate an earlier source stack and then fail later.
        for stack in await self._immich.list_stacks():
            member_ids = [member.id for member in stack.assets]
            selected_members = [identifier for identifier in member_ids if identifier in selected]
            if not selected_members:
                continue
            stack_resolution = self._resolution_for_stack(reviewed_resolution, stack.id)
            reviewed_stacks.append((stack, member_ids, selected_members, stack_resolution))
            for identifier in member_ids:
                if identifier not in affected_ids:
                    affected_ids.append(identifier)
            if stack_resolution == "keep_existing":
                final_ids = [identifier for identifier in final_ids if identifier not in member_ids]
            elif stack_resolution == "include_existing":
                for identifier in member_ids:
                    if identifier not in final_ids:
                        final_ids.append(identifier)

        if primary_asset_id not in final_ids:
            raise StackSelectionError(
                "The chosen stack primary is unavailable with this conflict resolution"
            )
        self._require_stackable(final_ids)

        # Only after the complete choice set and resulting destination are valid do we
        # mutate source stacks. Remote API failures can still interrupt reconciliation,
        # but validation failures are guaranteed to be non-mutating.
        for stack, member_ids, selected_members, stack_resolution in reviewed_stacks:
            if stack_resolution == "keep_existing":
                continue
            if stack_resolution == "include_existing":
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

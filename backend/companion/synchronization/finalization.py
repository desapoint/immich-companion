"""Evidence-driven first-class synchronization finalization."""

from __future__ import annotations

from companion.adaptive_tag_sync import finalize_incremental_asset_oriented_tags
from companion.asset_repository import AssetRepository
from companion.synchronization.evidence import SyncAuthority, SyncEvidence
from companion.synchronization.scopes import FinalizationScope
from companion.synchronization.selections import WindowSelection
from companion.synchronization.steps import (
    SyncStep,
    SyncStepContext,
    SyncStepProgress,
    SyncStepResult,
)

_REMOVAL_COUNTERS = (
    "album_memberships_removed",
    "tag_memberships_removed",
    "albums_removed",
    "tags_removed",
    "stacks_cleared",
    "assets_removed",
)
_AUTHORITY_RANK = {
    SyncAuthority.NONE: 0,
    SyncAuthority.SELECTED: 1,
    SyncAuthority.WINDOW: 2,
    SyncAuthority.COMPLETE: 3,
}


class FinalizationSyncStep(SyncStep[FinalizationScope]):
    """Finalize only absence proven safe by prior synchronization evidence."""

    name = "finalization"
    phase = "finalizing"

    def __init__(self, assets: AssetRepository) -> None:
        self._assets = assets

    async def run(
        self,
        context: SyncStepContext,
        scope: FinalizationScope,
    ) -> SyncStepResult:
        if not self.should_run(context):
            return SyncStepResult(
                name=self.name,
                phase=self.phase,
                skipped=True,
                completed=0,
                total=1,
                counters=dict(context.counters),
            )

        completed, outputs = await self._finalize(context, scope)
        return SyncStepResult(
            name=self.name,
            phase=self.phase,
            skipped=False,
            completed=completed,
            total=1,
            counters=dict(context.counters),
            evidence=list(context.evidence),
            outputs=outputs,
        )

    async def execute(
        self,
        context: SyncStepContext,
        scope: FinalizationScope,
    ) -> tuple[int, int]:
        completed, _outputs = await self._finalize(context, scope)
        return completed, 1

    async def _finalize(
        self,
        context: SyncStepContext,
        scope: FinalizationScope,
    ) -> tuple[int, dict[str, object]]:
        if scope.generation != context.generation:
            raise ValueError(
                "Finalization generation does not match the active sync generation"
            )
        if context.manual:
            if scope.validation_task_id is None:
                raise ValueError(
                    "Manual finalization requires a validated task reference"
                )
            if not scope.confirm_destructive:
                raise ValueError(
                    "Manual finalization requires explicit destructive confirmation"
                )

        evidence = [
            item
            for item in context.evidence
            if item.generation == scope.generation
        ]
        authorities = self._strongest_authorities(evidence)
        removed = {name: 0 for name in _REMOVAL_COUNTERS}
        path = "none"

        foundational_complete = all(
            authorities.get(domain) == SyncAuthority.COMPLETE
            for domain in ("albums", "tags", "stacks")
        )
        if foundational_complete:
            asset_evidence = self._strongest_evidence(evidence, "assets")
            album_memberships = authorities.get(
                "album_memberships",
                SyncAuthority.NONE,
            )
            tag_memberships = authorities.get(
                "tag_memberships",
                SyncAuthority.NONE,
            )
            remove_assets = (
                asset_evidence is not None
                and asset_evidence.authority == SyncAuthority.COMPLETE
            )
            window_start = None
            window_end = None
            if (
                asset_evidence is not None
                and asset_evidence.authority == SyncAuthority.WINDOW
                and isinstance(asset_evidence.selection, WindowSelection)
            ):
                window_start = asset_evidence.selection.start
                window_end = asset_evidence.selection.end

            selected_relationship_authority = (
                album_memberships != SyncAuthority.COMPLETE
                or tag_memberships != SyncAuthority.COMPLETE
            )
            if selected_relationship_authority:
                path = "bounded_relationship_authority"
                removed = await finalize_incremental_asset_oriented_tags(
                    self._assets,
                    scope.generation,
                    batch_size=context.config.batch_size or 1,
                    window_start=window_start,
                    window_end=window_end,
                    album_asset_oriented=(
                        album_memberships != SyncAuthority.COMPLETE
                    ),
                    tag_asset_oriented=(
                        tag_memberships != SyncAuthority.COMPLETE
                    ),
                )
            else:
                path = "generation"
                removed = await self._assets.finalize_generation(
                    scope.generation,
                    remove_assets=remove_assets,
                    batch_size=context.config.batch_size or 1,
                    window_start=window_start,
                    window_end=window_end,
                )

        context.counters.update(removed)
        await self._assets.refresh_relation_counts()
        context.cursor = "validated"
        await context.checkpoint_callback(
            context.cursor,
            context.counters,
            SyncStepProgress(
                phase=self.phase,
                completed=1,
                total=1,
                detail="Synchronization complete",
            ),
        )
        return 1, {
            "path": path,
            "authorities": {
                domain: authority.value for domain, authority in authorities.items()
            },
        }

    @staticmethod
    def _strongest_authorities(
        evidence: list[SyncEvidence],
    ) -> dict[str, SyncAuthority]:
        result: dict[str, SyncAuthority] = {}
        for item in evidence:
            previous = result.get(item.domain, SyncAuthority.NONE)
            if _AUTHORITY_RANK[item.authority] > _AUTHORITY_RANK[previous]:
                result[item.domain] = item.authority
        return result

    @staticmethod
    def _strongest_evidence(
        evidence: list[SyncEvidence],
        domain: str,
    ) -> SyncEvidence | None:
        candidates = [item for item in evidence if item.domain == domain]
        if not candidates:
            return None
        return max(candidates, key=lambda item: _AUTHORITY_RANK[item.authority])


__all__ = ["FinalizationSyncStep"]

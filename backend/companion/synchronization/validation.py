"""First-class validation step for staged synchronization evidence."""

from __future__ import annotations

from companion.asset_repository import AssetRepository
from companion.asset_repository_catalog import SyncValidationError
from companion.synchronization.evidence import SyncAuthority
from companion.synchronization.scopes import ValidationScope
from companion.synchronization.steps import (
    SyncStep,
    SyncStepContext,
    SyncStepProgress,
    SyncStepResult,
)


class ValidationSyncStep(SyncStep[ValidationScope]):
    """Validate one staged generation against the domains proven by prior steps."""

    name = "validation"
    phase = "finalizing"

    def __init__(self, assets: AssetRepository) -> None:
        self._assets = assets

    async def run(
        self,
        context: SyncStepContext,
        scope: ValidationScope,
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

        await self._validate_scope(context, scope)
        await context.checkpoint_callback(
            context.cursor,
            context.counters,
            SyncStepProgress(
                phase=self.phase,
                completed=0,
                total=1,
                detail="Validating synchronized state",
            ),
        )

        asset_complete = any(
            item.domain == "assets"
            and item.generation == scope.generation
            and item.authority == SyncAuthority.COMPLETE
            for item in context.evidence
        )
        validated_counts = await self._assets.validate_generation(
            scope.generation,
            context.counters,
            full=asset_complete,
            allow_counter_repair=scope.allow_counter_repair,
        )
        context.counters.update(validated_counts)
        context.cursor = "generation-valid"
        await context.checkpoint_callback(
            context.cursor,
            context.counters,
            SyncStepProgress(
                phase=self.phase,
                completed=1,
                total=1,
                detail="Finalizing synchronized state",
            ),
        )
        return SyncStepResult(
            name=self.name,
            phase=self.phase,
            skipped=False,
            completed=1,
            total=1,
            counters=dict(context.counters),
            evidence=list(context.evidence),
            outputs={
                "validated_domains": sorted(scope.expected_domains),
                "asset_complete": asset_complete,
            },
        )

    async def execute(
        self,
        context: SyncStepContext,
        scope: ValidationScope,
    ) -> tuple[int, int]:
        result = await self.run(context, scope)
        return result.completed, result.total or 1

    @staticmethod
    async def _validate_scope(
        context: SyncStepContext,
        scope: ValidationScope,
    ) -> None:
        if scope.generation != context.generation:
            raise SyncValidationError(
                "Validation generation does not match the active sync generation"
            )
        proven = {
            item.domain
            for item in context.evidence
            if item.generation == scope.generation
            and item.authority != SyncAuthority.NONE
        }
        missing = scope.expected_domains - proven
        if missing:
            raise SyncValidationError(
                "Validation is missing synchronization evidence for: "
                + ", ".join(sorted(missing))
            )


__all__ = ["ValidationSyncStep"]

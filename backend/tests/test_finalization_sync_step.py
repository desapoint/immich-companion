"""Evidence-driven validation and finalization step behavior."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion.asset_repository_catalog import SyncValidationError
from companion.synchronization import finalization as finalization_module
from companion.synchronization.evidence import SyncAuthority, SyncEvidence
from companion.synchronization.finalization import FinalizationSyncStep
from companion.synchronization.scopes import FinalizationScope, ValidationScope
from companion.synchronization.selections import (
    AllSelection,
    GenerationSelection,
    WindowSelection,
)
from companion.synchronization.steps import (
    SyncStepConditionals,
    SyncStepConfig,
    SyncStepContext,
)
from companion.synchronization.validation import ValidationSyncStep

GENERATION = 61
VALIDATION_TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WINDOW_START = datetime(2026, 9, 25, 10, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 25, 11, tzinfo=UTC)


def complete(domain: str) -> SyncEvidence:
    return SyncEvidence(
        domain=domain,  # type: ignore[arg-type]
        authority=SyncAuthority.COMPLETE,
        selection=AllSelection(),
        generation=GENERATION,
    )


def full_evidence() -> list[SyncEvidence]:
    return [
        complete("albums"),
        complete("tags"),
        complete("assets"),
        complete("stacks"),
        complete("album_memberships"),
        complete("tag_memberships"),
    ]


def incremental_evidence(
    *,
    album_authority: SyncAuthority = SyncAuthority.COMPLETE,
    tag_authority: SyncAuthority = SyncAuthority.COMPLETE,
) -> list[SyncEvidence]:
    evidence = [
        complete("albums"),
        complete("tags"),
        SyncEvidence(
            domain="assets",
            authority=SyncAuthority.WINDOW,
            selection=WindowSelection(start=WINDOW_START, end=WINDOW_END),
            generation=GENERATION,
        ),
        complete("stacks"),
    ]
    for domain, authority in (
        ("album_memberships", album_authority),
        ("tag_memberships", tag_authority),
    ):
        if authority == SyncAuthority.COMPLETE:
            evidence.append(complete(domain))
        else:
            evidence.append(
                SyncEvidence(
                    domain=domain,  # type: ignore[arg-type]
                    authority=authority,
                    selection=GenerationSelection(generation=GENERATION),
                    generation=GENERATION,
                )
            )
    return evidence


class FakeAssets:
    def __init__(self) -> None:
        self.validation_calls = []
        self.finalization_calls = []
        self.refresh_calls = 0

    async def validate_generation(
        self,
        generation,
        counters,
        *,
        full,
        allow_counter_repair,
    ):
        self.validation_calls.append(
            (generation, dict(counters), full, allow_counter_repair)
        )
        return {
            "albums_seen": counters.get("albums_seen", 0),
            "tags_seen": counters.get("tags_seen", 0),
            "album_memberships": counters.get("album_memberships", 0),
            "tag_memberships": counters.get("tag_memberships", 0),
            "stack_members": counters.get("stack_members", 0),
            **(
                {"assets_seen": counters.get("assets_seen", 0)}
                if full
                else {}
            ),
        }

    async def finalize_generation(
        self,
        generation,
        *,
        remove_assets,
        batch_size,
        window_start=None,
        window_end=None,
    ):
        self.finalization_calls.append(
            (
                generation,
                remove_assets,
                batch_size,
                window_start,
                window_end,
            )
        )
        return {
            "album_memberships_removed": 1,
            "tag_memberships_removed": 2,
            "albums_removed": 3,
            "tags_removed": 4,
            "stacks_cleared": 5,
            "assets_removed": 6,
        }

    async def refresh_relation_counts(self) -> None:
        self.refresh_calls += 1


def validation_context(evidence: list[SyncEvidence]) -> SyncStepContext:
    return SyncStepContext(
        mode="full",
        generation=GENERATION,
        config=SyncStepConfig(),
        counters={
            "albums_seen": 1,
            "tags_seen": 1,
            "assets_seen": 2,
            "stack_members": 2,
            "album_memberships": 1,
            "tag_memberships": 1,
        },
        evidence=evidence,
    )


@pytest.mark.asyncio
async def test_validation_uses_evidence_for_complete_asset_count_and_retry_repair() -> None:
    assets = FakeAssets()
    result = await ValidationSyncStep(assets).run(  # type: ignore[arg-type]
        validation_context(full_evidence()),
        ValidationScope(
            generation=GENERATION,
            expected_domains={
                "albums",
                "tags",
                "assets",
                "stacks",
                "album_memberships",
                "tag_memberships",
            },
            allow_counter_repair=True,
        ),
    )

    assert result.completed == 1
    assert result.evidence == full_evidence()
    assert result.outputs["asset_complete"] is True
    assert assets.validation_calls[0][2:] == (True, True)


@pytest.mark.asyncio
async def test_validation_window_asset_evidence_preserves_incremental_asset_behavior() -> None:
    assets = FakeAssets()
    evidence = incremental_evidence()
    context = validation_context(evidence)
    context.mode = "incremental"

    result = await ValidationSyncStep(assets).run(  # type: ignore[arg-type]
        context,
        ValidationScope(
            generation=GENERATION,
            expected_domains={
                "albums",
                "tags",
                "assets",
                "stacks",
                "album_memberships",
                "tag_memberships",
            },
        ),
    )

    assert result.outputs["asset_complete"] is False
    assert assets.validation_calls[0][2] is False


@pytest.mark.asyncio
async def test_validation_rejects_missing_authority_before_repository_call() -> None:
    assets = FakeAssets()

    with pytest.raises(SyncValidationError, match="missing synchronization evidence"):
        await ValidationSyncStep(assets).run(  # type: ignore[arg-type]
            validation_context([complete("assets")]),
            ValidationScope(
                generation=GENERATION,
                expected_domains={"assets", "stacks"},
            ),
        )

    assert assets.validation_calls == []


@pytest.mark.asyncio
async def test_validation_respects_conditionals() -> None:
    assets = FakeAssets()
    result = await ValidationSyncStep(assets).run(  # type: ignore[arg-type]
        SyncStepContext(
            mode="full",
            generation=GENERATION,
            config=SyncStepConfig(
                conditionals=SyncStepConditionals(enabled=False)
            ),
            evidence=full_evidence(),
        ),
        ValidationScope(
            generation=GENERATION,
            expected_domains={"assets"},
        ),
    )

    assert result.skipped is True
    assert assets.validation_calls == []


@pytest.mark.asyncio
async def test_full_finalization_uses_complete_evidence_not_strategy_counters() -> None:
    assets = FakeAssets()
    context = SyncStepContext(
        mode="incremental",
        generation=GENERATION,
        config=SyncStepConfig(batch_size=25),
        counters={
            "album_strategy_asset_oriented": 1,
            "tag_strategy_asset_oriented": 1,
            "tag_strategy_asset_fallback": 0,
        },
        evidence=full_evidence(),
    )

    result = await FinalizationSyncStep(assets).run(  # type: ignore[arg-type]
        context,
        FinalizationScope(generation=GENERATION),
    )

    assert assets.finalization_calls == [
        (GENERATION, True, 25, None, None)
    ]
    assert result.outputs["path"] == "generation"
    assert result.counters["assets_removed"] == 6
    assert assets.refresh_calls == 1


@pytest.mark.asyncio
async def test_incremental_selected_relationship_authority_uses_bounded_helper(
    monkeypatch,
) -> None:
    assets = FakeAssets()
    calls = []

    async def finalize_selected(
        repository,
        generation,
        *,
        batch_size,
        window_start,
        window_end,
        album_asset_oriented,
        tag_asset_oriented,
    ):
        calls.append(
            (
                repository,
                generation,
                batch_size,
                window_start,
                window_end,
                album_asset_oriented,
                tag_asset_oriented,
            )
        )
        return {"assets_removed": 2}

    monkeypatch.setattr(
        finalization_module,
        "finalize_incremental_asset_oriented_tags",
        finalize_selected,
    )
    evidence = incremental_evidence(
        album_authority=SyncAuthority.SELECTED,
        tag_authority=SyncAuthority.SELECTED,
    )
    context = SyncStepContext(
        mode="full",
        generation=GENERATION,
        config=SyncStepConfig(batch_size=50),
        counters={
            "album_strategy_asset_oriented": 0,
            "tag_strategy_asset_oriented": 0,
            "tag_strategy_asset_fallback": 1,
        },
        evidence=evidence,
    )

    result = await FinalizationSyncStep(assets).run(  # type: ignore[arg-type]
        context,
        FinalizationScope(generation=GENERATION),
    )

    assert calls == [
        (
            assets,
            GENERATION,
            50,
            WINDOW_START,
            WINDOW_END,
            True,
            True,
        )
    ]
    assert assets.finalization_calls == []
    assert result.outputs["path"] == "bounded_relationship_authority"
    assert result.counters["assets_removed"] == 2


@pytest.mark.asyncio
async def test_tag_fallback_evidence_prunes_only_complete_tag_memberships(
    monkeypatch,
) -> None:
    assets = FakeAssets()
    calls = []

    async def finalize_selected(
        _repository,
        _generation,
        *,
        batch_size,
        window_start,
        window_end,
        album_asset_oriented,
        tag_asset_oriented,
    ):
        calls.append(
            (
                batch_size,
                window_start,
                window_end,
                album_asset_oriented,
                tag_asset_oriented,
            )
        )
        return {}

    monkeypatch.setattr(
        finalization_module,
        "finalize_incremental_asset_oriented_tags",
        finalize_selected,
    )

    await FinalizationSyncStep(assets).run(  # type: ignore[arg-type]
        SyncStepContext(
            mode="incremental",
            generation=GENERATION,
            config=SyncStepConfig(batch_size=20),
            evidence=incremental_evidence(
                album_authority=SyncAuthority.SELECTED,
                tag_authority=SyncAuthority.COMPLETE,
            ),
        ),
        FinalizationScope(generation=GENERATION),
    )

    assert calls == [
        (20, WINDOW_START, WINDOW_END, True, False)
    ]


@pytest.mark.asyncio
async def test_finalization_without_foundational_complete_evidence_does_not_prune(
    monkeypatch,
) -> None:
    assets = FakeAssets()
    helper_calls = []

    async def finalize_selected(*args, **kwargs):
        helper_calls.append((args, kwargs))
        return {}

    monkeypatch.setattr(
        finalization_module,
        "finalize_incremental_asset_oriented_tags",
        finalize_selected,
    )
    result = await FinalizationSyncStep(assets).run(  # type: ignore[arg-type]
        SyncStepContext(
            mode="incremental",
            generation=GENERATION,
            config=SyncStepConfig(batch_size=25),
            evidence=[
                SyncEvidence(
                    domain="assets",
                    authority=SyncAuthority.SELECTED,
                    selection=GenerationSelection(generation=GENERATION),
                    generation=GENERATION,
                )
            ],
        ),
        FinalizationScope(generation=GENERATION),
    )

    assert result.outputs["path"] == "none"
    assert assets.finalization_calls == []
    assert helper_calls == []
    assert assets.refresh_calls == 1


@pytest.mark.asyncio
async def test_manual_finalization_requires_validation_reference_and_confirmation() -> None:
    assets = FakeAssets()
    step = FinalizationSyncStep(assets)  # type: ignore[arg-type]
    context = SyncStepContext(
        mode="full",
        generation=GENERATION,
        config=SyncStepConfig(batch_size=25),
        manual=True,
        respect_conditionals=False,
        evidence=full_evidence(),
    )

    with pytest.raises(ValueError, match="validated task reference"):
        await step.run(
            context,
            FinalizationScope(
                generation=GENERATION,
                confirm_destructive=True,
            ),
        )

    with pytest.raises(ValueError, match="destructive confirmation"):
        await step.run(
            context,
            FinalizationScope(
                generation=GENERATION,
                validation_task_id=VALIDATION_TASK_ID,
            ),
        )

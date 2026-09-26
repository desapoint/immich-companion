"""Typed first-class synchronization contracts."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from companion.action_schema import AssetSelectionRequest
from companion.synchronization.evidence import SyncAuthority, SyncEvidence
from companion.synchronization.registry import SyncStepRegistry
from companion.synchronization.scopes import (
    CatalogScope,
    RelationshipScope,
    SyncScope,
)
from companion.synchronization.selections import (
    AllSelection,
    AssetSelection,
    GenerationSelection,
    RequestSelection,
    WindowSelection,
)
from companion.synchronization.steps import (
    SyncStep,
    SyncStepConfig,
    SyncStepContext,
    SyncStepResult,
)

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")


def test_asset_request_selection_round_trips_as_discriminated_json() -> None:
    adapter = TypeAdapter(AssetSelection)
    selection = RequestSelection(
        request=AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE])
    )

    restored = adapter.validate_json(adapter.dump_json(selection))

    assert isinstance(restored, RequestSelection)
    assert restored.kind == "request"
    assert restored.request.ids == [ASSET_ONE]


def test_sync_scope_round_trips_relationship_scope() -> None:
    adapter = TypeAdapter(SyncScope)
    scope = RelationshipScope(
        kinds={"albums", "tags"},
        strategy="automatic",
        assets=GenerationSelection(generation=17),
        albums=AllSelection(),
        tags=AllSelection(),
    )

    restored = adapter.validate_json(adapter.dump_json(scope))

    assert isinstance(restored, RelationshipScope)
    assert restored.kinds == {"albums", "tags"}
    assert restored.strategy == "automatic"
    assert isinstance(restored.assets, GenerationSelection)
    assert restored.assets.generation == 17


def test_sync_scope_json_schema_exposes_kind_discriminator() -> None:
    schema = TypeAdapter(SyncScope).json_schema()

    assert schema["discriminator"]["propertyName"] == "kind"
    assert set(schema["discriminator"]["mapping"]) == {
        "events",
        "catalogs",
        "assets",
        "stacks",
        "relationships",
        "validation",
        "finalization",
    }


def test_catalog_scope_requires_at_least_one_enabled_domain() -> None:
    with pytest.raises(ValidationError, match="requires albums and/or tags"):
        CatalogScope()


def test_relationship_scope_rejects_invalid_strategy_inputs() -> None:
    with pytest.raises(ValidationError, match="requires assets"):
        RelationshipScope(kinds={"tags"}, strategy="automatic", tags=AllSelection())

    with pytest.raises(ValidationError, match="require a tag selection"):
        RelationshipScope(kinds={"tags"}, strategy="by_relation")


def test_window_selection_requires_forward_time() -> None:
    instant = datetime(2026, 9, 25, 12, tzinfo=UTC)

    with pytest.raises(ValidationError, match="start must be before end"):
        WindowSelection(start=instant, end=instant)


def test_sync_evidence_round_trips_explicit_window_authority() -> None:
    selection = WindowSelection(
        start=datetime(2026, 9, 25, 11, tzinfo=UTC),
        end=datetime(2026, 9, 25, 12, tzinfo=UTC),
    )
    evidence = SyncEvidence(
        domain="assets",
        authority=SyncAuthority.WINDOW,
        selection=selection,
        generation=21,
    )

    restored = SyncEvidence.model_validate_json(evidence.model_dump_json())

    assert restored.authority == SyncAuthority.WINDOW
    assert isinstance(restored.selection, WindowSelection)
    assert restored.selection == selection


def test_sync_evidence_rejects_unsafe_authority_selection_pairs() -> None:
    with pytest.raises(ValidationError, match="Window authority requires"):
        SyncEvidence(
            domain="assets",
            authority=SyncAuthority.WINDOW,
            selection=GenerationSelection(generation=3),
            generation=3,
        )

    with pytest.raises(ValidationError, match="Selected authority requires"):
        SyncEvidence(
            domain="tag_memberships",
            authority=SyncAuthority.SELECTED,
            selection=AllSelection(),
            generation=3,
        )


class FakeStep(SyncStep[object]):
    name = "assets"
    phase = "assets"

    async def execute(
        self,
        _context: SyncStepContext,
        _data: object,
    ) -> tuple[int, int | None]:
        return 0, 0


def test_sync_step_registry_has_one_owner_per_step_name() -> None:
    step = FakeStep()
    registry = SyncStepRegistry([step])

    assert registry.get("assets") is step
    assert registry.names() == ("assets",)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeStep())

    with pytest.raises(KeyError, match="not registered"):
        registry.get("catalogs")


def test_sync_step_result_extends_existing_contract_with_evidence_and_outputs() -> None:
    evidence = SyncEvidence(
        domain="assets",
        authority=SyncAuthority.SELECTED,
        selection=GenerationSelection(generation=5),
        generation=5,
    )
    result = SyncStepResult(
        name="assets",
        phase="assets",
        skipped=False,
        completed=2,
        total=2,
        counters={"assets_seen": 2},
        evidence=[evidence],
        outputs={"selection": {"kind": "generation", "generation": 5}},
    )

    assert result.counters == {"assets_seen": 2}
    assert result.evidence == [evidence]
    assert result.outputs["selection"] == {"kind": "generation", "generation": 5}


@pytest.mark.asyncio
async def test_existing_sync_step_defaults_to_empty_evidence_and_outputs() -> None:
    result = await FakeStep().run(
        SyncStepContext(
            mode="full",
            generation=1,
            config=SyncStepConfig(),
        ),
        object(),
    )

    assert result.evidence == []
    assert result.outputs == {}

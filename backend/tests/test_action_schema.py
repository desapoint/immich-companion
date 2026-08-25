"""Validation coverage for selection and action request contracts."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from companion.action_schema import AssetActionPlanRequest, AssetSelectionRequest
from companion.asset_schema import SearchGroup

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ALBUM_ID = UUID("44444444-4444-4444-8444-444444444444")
SECOND_ALBUM_ID = UUID("55555555-5555-4555-8555-555555555555")


def test_selection_modes_are_explicit_and_deduplicated() -> None:
    explicit = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE, ASSET_ONE])
    matching = AssetSelectionRequest(
        mode="all_matching",
        expression=SearchGroup(),
        excluded_ids=[ASSET_ONE, ASSET_ONE],
    )

    assert explicit.ids == [ASSET_ONE]
    assert matching.excluded_ids == [ASSET_ONE]

    with pytest.raises(ValidationError):
        AssetSelectionRequest(mode="explicit", ids=[])
    with pytest.raises(ValidationError):
        AssetSelectionRequest(mode="all_matching")


def test_relation_actions_require_one_or_more_unique_relations() -> None:
    selection = AssetSelectionRequest(mode="explicit", ids=[ASSET_ONE])

    request = AssetActionPlanRequest(
        selection=selection,
        action="remove_album",
        relation_ids=[ALBUM_ID, SECOND_ALBUM_ID, ALBUM_ID],
    )
    assert request.relation_ids == [ALBUM_ID, SECOND_ALBUM_ID]

    with pytest.raises(ValidationError):
        AssetActionPlanRequest(selection=selection, action="remove_tag")
    with pytest.raises(ValidationError):
        AssetActionPlanRequest(
            selection=selection,
            action="favorite_toggle",
            relation_ids=[ALBUM_ID],
        )

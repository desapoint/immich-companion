"""Structured search validation and SQL compilation coverage."""

from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from companion.asset_repository import ASPECT_RATIO_RELATIVE_TOLERANCE, AssetRepository
from companion.asset_schema import SearchCondition, SearchGroup, StructuredAssetSearchQuery
from companion.models import AssetRecord


def compiled_sql(group: SearchGroup) -> str:
    predicate = AssetRepository._compile_group(group)
    return str(
        select(AssetRecord.id)
        .where(predicate)
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


def test_nested_album_intersection_union_and_exclusion_compile() -> None:
    album_a = UUID("11111111-1111-4111-8111-111111111111")
    album_b = UUID("22222222-2222-4222-8222-222222222222")
    expression = SearchGroup(
        operator="and",
        children=[
            SearchCondition(field="album", operator="in_album", value=str(album_a)),
            SearchGroup(
                operator="or",
                children=[
                    SearchCondition(field="album", operator="in_album", value=str(album_b)),
                    SearchCondition(field="album", operator="not_in_album", value=str(album_b)),
                ],
            ),
        ],
    )

    sql = compiled_sql(expression)

    assert "album_assets" in sql
    assert str(album_a) in sql
    assert str(album_b) in sql
    assert " AND " in sql
    assert " OR " in sql
    assert "NOT (EXISTS" in sql


def test_dimensions_aspect_ratio_and_states_compile() -> None:
    expression = SearchGroup(
        children=[
            SearchCondition(field="width", operator="at_least", value=1280),
            SearchCondition(field="width", operator="at_most", value=3840),
            SearchCondition(field="height", operator="at_least", value=720),
            SearchCondition(field="height", operator="at_most", value=2160),
            SearchCondition(field="aspect_ratio", operator="at_least", value=1.7),
            SearchCondition(field="aspect_ratio", operator="at_most", value=1.8),
            SearchCondition(field="favorite", operator="equals", value=True),
            SearchCondition(field="archived", operator="equals", value=False),
            SearchCondition(field="trashed", operator="equals", value=False),
        ]
    )

    sql = compiled_sql(expression)

    assert "assets.width >= 1280" in sql
    assert "assets.height <= 2160" in sql
    assert "CAST(assets.width AS FLOAT)" in sql
    assert "assets.is_favorite = true" in sql
    assert "assets.is_archived = false" in sql
    assert "assets.is_trashed = false" in sql


def test_fractional_aspect_ratio_uses_small_relative_approximation() -> None:
    condition = SearchCondition(field="aspect_ratio", operator="equals", value="16/9")

    sql = compiled_sql(SearchGroup(children=[condition]))

    assert condition.value == pytest.approx(16 / 9)
    assert "abs(" in sql
    assert str((16 / 9) * ASPECT_RATIO_RELATIVE_TOLERANCE) in sql


def test_invalid_field_operator_and_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchCondition(field="album", operator="contains", value="not-a-uuid")
    with pytest.raises(ValidationError):
        SearchCondition(field="width", operator="at_least", value="wide")
    for value in ["0", "-1", "16/0", "16/9/2", "wide"]:
        with pytest.raises(ValidationError):
            SearchCondition(field="aspect_ratio", operator="equals", value=value)
    with pytest.raises(ValidationError):
        StructuredAssetSearchQuery.model_validate(
            {
                "expression": {
                    "kind": "group",
                    "children": [
                        {
                            "kind": "condition",
                            "field": "trashed",
                            "operator": "equals",
                            "value": "sometimes",
                        }
                    ],
                }
            }
        )

"""Structured search validation and SQL compilation coverage."""

from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from companion.action_schema import AssetSelectionRequest
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


def compiled_order(sort_field: str, sort_direction: str) -> str:
    return str(
        select(AssetRecord.id)
        .order_by(*AssetRepository._sort_expressions(sort_field, sort_direction))
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


def test_multi_relation_any_all_none_and_empty_compile() -> None:
    album_a = UUID("11111111-1111-4111-8111-111111111111")
    album_b = UUID("22222222-2222-4222-8222-222222222222")
    tag_a = UUID("33333333-3333-4333-8333-333333333333")
    tag_b = UUID("44444444-4444-4444-8444-444444444444")
    expression = SearchGroup(
        children=[
            SearchCondition(
                field="album",
                operator="in_any",
                value=[str(album_a), str(album_b)],
            ),
            SearchCondition(
                field="tag",
                operator="in_all",
                value=[str(tag_a), str(tag_b)],
            ),
            SearchCondition(
                field="tag",
                operator="not_in_any",
                value=[str(tag_b)],
            ),
            SearchCondition(field="album", operator="has_none", value=[]),
            SearchCondition(field="tag", operator="has_none", value=[]),
        ]
    )

    sql = compiled_sql(expression)

    assert "album_assets" in sql
    assert "tag_assets" in sql
    assert str(album_a) in sql
    assert str(album_b) in sql
    assert str(tag_a) in sql
    assert str(tag_b) in sql
    assert " OR " in sql
    assert " AND " in sql
    assert sql.count("NOT (EXISTS") >= 3


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


def test_stack_membership_and_role_compile() -> None:
    expression = SearchGroup(
        children=[
            SearchCondition(field="stack", operator="equals", value=True),
            SearchCondition(field="stack_primary", operator="equals", value=False),
        ]
    )

    sql = compiled_sql(expression)

    assert "json_typeof(assets.stack) = 'object'" in sql
    assert "assets.stack ->> 'primaryAssetId'" in sql
    assert "CAST(assets.id AS VARCHAR)" in sql
    assert "!=" in sql


def test_stack_primary_and_secondary_both_require_stack_membership() -> None:
    primary_sql = compiled_sql(
        SearchGroup(
            children=[SearchCondition(field="stack_primary", operator="equals", value=True)]
        )
    )
    secondary_sql = compiled_sql(
        SearchGroup(
            children=[SearchCondition(field="stack_primary", operator="equals", value=False)]
        )
    )

    assert "json_typeof(assets.stack) = 'object'" in primary_sql
    assert "json_typeof(assets.stack) = 'object'" in secondary_sql
    assert "assets.stack ->> 'primaryAssetId'" in primary_sql
    assert "assets.stack ->> 'primaryAssetId'" in secondary_sql


def test_strict_dimension_and_aspect_ratio_comparisons_compile() -> None:
    expression = SearchGroup(
        children=[
            SearchCondition(field="width", operator="greater_than", value=3000),
            SearchCondition(field="aspect_ratio", operator="less_than", value="4/3"),
        ]
    )

    sql = compiled_sql(expression)

    assert "assets.width > 3000" in sql
    assert "< 1.3333333333333333" in sql


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
    with pytest.raises(ValidationError):
        SearchCondition(field="tag", operator="in_any", value=[])
    with pytest.raises(ValidationError):
        SearchCondition(field="tag", operator="in_all", value=["not-a-uuid"])
    with pytest.raises(ValidationError):
        SearchCondition(field="album", operator="has_none", value=[str(UUID(int=1))])
    with pytest.raises(ValidationError):
        SearchCondition(field="stack", operator="not_equals", value=True)
    with pytest.raises(ValidationError):
        SearchCondition(field="stack_primary", operator="equals", value="true")
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


@pytest.mark.parametrize(
    ("sort_field", "sort_direction", "expected"),
    [
        ("taken_at", "desc", "assets.file_created_at DESC NULLS LAST"),
        ("filename", "asc", "lower(assets.original_file_name) ASC NULLS LAST"),
        ("created_at", "desc", "assets.immich_created_at DESC NULLS LAST"),
        ("modified_at", "asc", "assets.file_modified_at ASC NULLS LAST"),
        ("width", "desc", "assets.width DESC NULLS LAST"),
        ("height", "asc", "assets.height ASC NULLS LAST"),
    ],
)
def test_allow_listed_sorting_is_null_safe_and_stable(
    sort_field: str,
    sort_direction: str,
    expected: str,
) -> None:
    sql = compiled_order(sort_field, sort_direction)

    assert expected in sql
    assert sql.endswith("assets.id ASC")


def test_structured_sort_defaults_and_invalid_values() -> None:
    criteria = StructuredAssetSearchQuery()

    assert criteria.sort_field == "taken_at"
    assert criteria.sort_direction == "desc"
    with pytest.raises(ValidationError):
        StructuredAssetSearchQuery(sort_field="checksum")
    with pytest.raises(ValidationError):
        StructuredAssetSearchQuery(sort_direction="random")


@pytest.mark.asyncio
async def test_selection_relationships_return_union_with_mixed_applicability_counts() -> None:
    album_id = UUID("44444444-4444-4444-8444-444444444444")
    tag_id = UUID("55555555-5555-4555-8555-555555555555")

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class Session:
        def __init__(self):
            self.statements = []
            self.results = [
                Result([(album_id, "Shared album", 1)]),
                Result([(tag_id, "Shared tag", 2)]),
            ]

        async def execute(self, statement):
            self.statements.append(statement)
            return self.results.pop(0)

    session = Session()

    class Database:
        @asynccontextmanager
        async def sessions(self):
            yield session

    repository = AssetRepository(Database())  # type: ignore[arg-type]
    relationships = await repository.selection_relationships(
        AssetSelectionRequest(
            mode="explicit",
            ids=[
                UUID("11111111-1111-4111-8111-111111111111"),
                UUID("22222222-2222-4222-8222-222222222222"),
            ],
        )
    )

    assert relationships.albums[0].selected_asset_count == 1
    assert relationships.tags[0].selected_asset_count == 2
    album_sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    tag_sql = str(session.statements[1].compile(dialect=postgresql.dialect()))
    assert "album_assets" in album_sql
    assert "tag_assets" in tag_sql
    assert "assets.is_trashed IS false" in album_sql

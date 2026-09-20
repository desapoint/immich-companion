"""Asset search query mixin."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    Float,
    String,
    and_,
    case,
    cast,
    delete,
    exists,
    func,
    literal,
    not_,
    or_,
    select,
    true,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert

from companion.action_schema import (
    AssetActionOperation,
    AssetSelectionCapabilities,
    AssetSelectionRelationship,
    AssetSelectionRelationships,
    AssetSelectionRequest,
    AssetSelectionResolution,
    AssetSelectionSummary,
)
from companion.asset_schema import (
    AlbumOption,
    AssetAlbumSummary,
    AssetPageSelection,
    AssetSearchMatchRequest,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetSortDirection,
    AssetSortField,
    AssetSummary,
    AssetTagSummary,
    SearchCondition,
    SearchGroup,
    StructuredAssetSearchQuery,
    TagOption,
)
from companion.database import DatabaseManager
from companion.asset_repository_hydration import (
    asset_fingerprint as _asset_fingerprint,
    immich_asset as _immich_asset,
    similarity_upsert_changes,
)
from companion.immich import ImmichAlbum, ImmichAsset, ImmichTag
from companion.models import (
    AlbumAssetRecord,
    AlbumRecord,
    AssetRecord,
    SelectionSetMemberRecord,
    SelectionSetRecord,
    SimilarityAssetChangeRecord,
    TagAssetRecord,
    TagRecord,
)

ASPECT_RATIO_RELATIVE_TOLERANCE = 0.001


class SyncValidationError(RuntimeError):
    """Raised when a staged generation is incomplete before finalization."""




class AssetSearchMixin:
    """SQL-backed free-text and structured asset search operations."""

    async def search(self, criteria: AssetSearchQuery) -> AssetSearchResponse:
        """Compose safe basic filters and return a stable result page."""

        predicates = [AssetRecord.is_trashed.is_(False)]
        if criteria.query:
            query = criteria.query.strip()
            if query:
                predicates.append(AssetRecord.original_file_name.icontains(query, autoescape=True))
        if criteria.asset_type:
            predicates.append(AssetRecord.asset_type == criteria.asset_type)
        if criteria.taken_after:
            predicates.append(AssetRecord.file_created_at >= criteria.taken_after)
        if criteria.taken_before:
            predicates.append(AssetRecord.file_created_at <= criteria.taken_before)
        if criteria.min_width:
            predicates.append(AssetRecord.width >= criteria.min_width)
        if criteria.max_width:
            predicates.append(AssetRecord.width <= criteria.max_width)
        if criteria.min_height:
            predicates.append(AssetRecord.height >= criteria.min_height)
        if criteria.max_height:
            predicates.append(AssetRecord.height <= criteria.max_height)
        aspect_ratio = cast(AssetRecord.width, Float) / cast(AssetRecord.height, Float)
        if criteria.min_aspect_ratio:
            predicates.append(aspect_ratio >= criteria.min_aspect_ratio)
        if criteria.max_aspect_ratio:
            predicates.append(aspect_ratio <= criteria.max_aspect_ratio)
        if criteria.favorite is not None:
            predicates.append(AssetRecord.is_favorite == criteria.favorite)
        if criteria.archived is not None:
            predicates.append(AssetRecord.is_archived == criteria.archived)
        if criteria.trashed is not None:
            predicates.append(AssetRecord.is_trashed == criteria.trashed)

        return await self._search_page(
            predicates,
            criteria.page,
            criteria.page_size,
            criteria.sort_field,
            criteria.sort_direction,
        )

    @staticmethod
    def _compile_condition(condition: SearchCondition):
        value = condition.value
        if condition.field == "filename":
            assert isinstance(value, str)
            if condition.operator == "contains":
                return AssetRecord.original_file_name.icontains(value.strip(), autoescape=True)
            comparison = func.lower(AssetRecord.original_file_name) == value.strip().lower()
            return not_(comparison) if condition.operator == "not_equals" else comparison
        if condition.field == "type":
            comparison = AssetRecord.asset_type == str(value)
            return not_(comparison) if condition.operator == "not_equals" else comparison
        if condition.field == "taken_at":
            assert isinstance(value, str)
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if condition.operator == "after":
                return AssetRecord.file_created_at >= parsed
            return AssetRecord.file_created_at <= parsed
        if condition.field in {"width", "height"}:
            column = AssetRecord.width if condition.field == "width" else AssetRecord.height
            if condition.operator == "at_least":
                return column >= int(value)
            if condition.operator == "at_most":
                return column <= int(value)
            if condition.operator == "greater_than":
                return column > int(value)
            if condition.operator == "less_than":
                return column < int(value)
            return column == int(value)
        if condition.field == "aspect_ratio":
            ratio = cast(AssetRecord.width, Float) / cast(AssetRecord.height, Float)
            numeric = float(value)
            if condition.operator == "at_least":
                return ratio >= numeric
            if condition.operator == "at_most":
                return ratio <= numeric
            if condition.operator == "greater_than":
                return ratio > numeric
            if condition.operator == "less_than":
                return ratio < numeric
            return func.abs(ratio - numeric) <= numeric * ASPECT_RATIO_RELATIVE_TOLERANCE
        if condition.field in {"favorite", "archived", "trashed"}:
            column = {
                "favorite": AssetRecord.is_favorite,
                "archived": AssetRecord.is_archived,
                "trashed": AssetRecord.is_trashed,
            }[condition.field]
            return column == bool(value)
        if condition.field in {"stack", "stack_primary"}:
            stack_present = and_(
                AssetRecord.stack.is_not(None),
                func.json_typeof(AssetRecord.stack) == "object",
            )
            if condition.field == "stack":
                return stack_present if bool(value) else not_(stack_present)
            is_primary = (
                AssetRecord.stack["primaryAssetId"].as_string()
                == cast(AssetRecord.id, String)
            )
            return and_(stack_present, is_primary if bool(value) else not_(is_primary))
        if condition.field in {"album", "tag"}:
            membership_model = AlbumAssetRecord if condition.field == "album" else TagAssetRecord
            relation_column = (
                AlbumAssetRecord.album_id if condition.field == "album" else TagAssetRecord.tag_id
            )
            any_membership = exists(select(1).where(membership_model.asset_id == AssetRecord.id))
            if condition.operator == "has_none":
                return not_(any_membership)
            assert isinstance(value, list)
            memberships = [
                exists(
                    select(1).where(
                        membership_model.asset_id == AssetRecord.id,
                        relation_column == UUID(identifier),
                    )
                )
                for identifier in value
            ]
            if condition.operator == "in_all":
                return and_(*memberships)
            any_selected = or_(*memberships)
            return not_(any_selected) if condition.operator == "not_in_any" else any_selected
        raise ValueError(f"Unsupported search field: {condition.field}")

    @classmethod
    def _compile_group(cls, group: SearchGroup):
        compiled = [
            cls._compile_group(child)
            if isinstance(child, SearchGroup)
            else cls._compile_condition(child)
            for child in group.children
        ]
        if compiled:
            expression = and_(*compiled) if group.operator == "and" else or_(*compiled)
        else:
            expression = true()
        return not_(expression) if group.negate else expression

    async def search_structured(self, criteria: StructuredAssetSearchQuery) -> AssetSearchResponse:
        """Compile a validated recursive expression and return one stable page."""

        predicate = self._compile_group(criteria.expression)
        return await self._search_page(
            [AssetRecord.is_trashed.is_(False), predicate],
            criteria.page,
            criteria.page_size,
            criteria.sort_field,
            criteria.sort_direction,
            selection_id=criteria.selection_id,
        )

    async def find_structured_match(
        self,
        asset_id: UUID,
        criteria: AssetSearchMatchRequest,
    ) -> AssetSummary | None:
        """Return one refreshed card only when it still matches an expression."""

        statement = select(AssetRecord).where(
            AssetRecord.id == asset_id,
            AssetRecord.is_trashed.is_(False),
            self._compile_group(criteria.expression),
        )
        async with self._database.sessions() as session:
            record = await session.scalar(statement)
            if record is None:
                return None
            summaries = await self._summaries_for_records(session, [record])
        return summaries[0]

    @staticmethod
    def _sort_expressions(
        sort_field: AssetSortField,
        sort_direction: AssetSortDirection,
    ) -> tuple[object, object]:
        columns = {
            "taken_at": AssetRecord.file_created_at,
            "filename": func.lower(AssetRecord.original_file_name),
            "created_at": AssetRecord.immich_created_at,
            "modified_at": AssetRecord.file_modified_at,
            "width": AssetRecord.width,
            "height": AssetRecord.height,
        }
        column = columns[sort_field]
        ordered = column.asc() if sort_direction == "asc" else column.desc()
        return ordered.nullslast(), AssetRecord.id.asc()

    async def _search_page(
        self,
        predicates: list[object],
        page: int,
        page_size: int,
        sort_field: AssetSortField,
        sort_direction: AssetSortDirection,
        selection_id: UUID | None = None,
    ) -> AssetSearchResponse:
        filtered = select(AssetRecord).where(*predicates)
        count_statement = select(func.count()).select_from(AssetRecord).where(*predicates)
        result_statement = (
            filtered.order_by(*self._sort_expressions(sort_field, sort_direction))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        async with self._database.sessions() as session:
            total = int(await session.scalar(count_statement) or 0)
            records = list((await session.scalars(result_statement)).all())
            items = await self._summaries_for_records(session, records)
            selection = None
            if selection_id is not None:
                selection_record = await session.get(SelectionSetRecord, selection_id)
                if (
                    selection_record is None
                    or selection_record.status != "active"
                    or selection_record.expires_at <= datetime.now(UTC)
                ):
                    raise ValueError("Selection set was not found or has expired")
                visible_ids = [record.id for record in records]
                selected_ids = list(
                    (
                        await session.scalars(
                            select(SelectionSetMemberRecord.asset_id).where(
                                SelectionSetMemberRecord.selection_id == selection_id,
                                SelectionSetMemberRecord.asset_id.in_(visible_ids),
                            )
                        )
                    ).all()
                )
                selection = AssetPageSelection(
                    id=selection_record.id,
                    revision=selection_record.revision,
                    selected_count=selection_record.selected_count,
                    selected_ids=selected_ids,
                )

        return AssetSearchResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
            selection=selection,
        )

    @staticmethod
    async def _summaries_for_records(session, records: list[AssetRecord]) -> list[AssetSummary]:
        """Hydrate card summaries and album memberships for known records."""

        album_map: dict[UUID, list[AssetAlbumSummary]] = {record.id: [] for record in records}
        tag_map: dict[UUID, list[AssetTagSummary]] = {record.id: [] for record in records}
        if records:
            album_statement = (
                select(
                    AlbumAssetRecord.asset_id,
                    AlbumRecord.id.label("album_id"),
                    AlbumRecord.album_name,
                )
                .join(AlbumRecord, AlbumRecord.id == AlbumAssetRecord.album_id)
                .where(AlbumAssetRecord.asset_id.in_([record.id for record in records]))
                .order_by(
                    AlbumAssetRecord.asset_id,
                    func.lower(AlbumRecord.album_name),
                    AlbumRecord.id,
                )
            )
            for asset_id, album_id, album_name in await session.execute(album_statement):
                album_map[asset_id].append(AssetAlbumSummary(id=album_id, name=album_name))
            tag_statement = (
                select(
                    TagAssetRecord.asset_id,
                    TagRecord.id.label("tag_id"),
                    TagRecord.tag_name,
                    TagRecord.color,
                )
                .join(TagRecord, TagRecord.id == TagAssetRecord.tag_id)
                .where(TagAssetRecord.asset_id.in_([record.id for record in records]))
                .order_by(
                    TagAssetRecord.asset_id,
                    func.lower(TagRecord.tag_name),
                    TagRecord.id,
                )
            )
            for asset_id, tag_id, tag_name, color in await session.execute(tag_statement):
                tag_map[asset_id].append(
                    AssetTagSummary(id=str(tag_id), name=tag_name, color=color)
                )
        return [
            AssetSummary.from_record(
                record,
                album_map.get(record.id, []),
                tag_map.get(record.id, []),
            )
            for record in records
        ]

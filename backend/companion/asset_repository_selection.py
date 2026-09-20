"""Asset selection and action persistence mixin."""

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
from companion.asset_repository_search import AssetSearchMixin
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




class AssetSelectionMixin:
    """Resolve selections and persist selection/action membership state."""

    async def resolve_selection(
        self,
        selection: AssetSelectionRequest,
        *,
        max_targets: int,
    ) -> AssetSelectionResolution:
        """Resolve an exact action target inside companion PostgreSQL."""

        excluded = set(selection.excluded_ids)
        requested: list[UUID]
        if selection.selection_id is not None:
            requested = await self.selection_ids(selection.selection_id)
            statement = select(AssetRecord).where(
                AssetRecord.id.in_(requested), AssetRecord.is_trashed.is_(False)
            )
        elif selection.mode == "explicit":
            requested = list(selection.ids)
            statement = select(AssetRecord).where(
                AssetRecord.id.in_(requested), AssetRecord.is_trashed.is_(False)
            )
        else:
            assert selection.expression is not None
            predicate = self._compile_group(selection.expression)
            statement = select(AssetRecord).where(AssetRecord.is_trashed.is_(False), predicate)
            if excluded:
                statement = statement.where(AssetRecord.id.not_in(excluded))
            statement = statement.order_by(AssetRecord.id).limit(max_targets + 1)

        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())

        if len(records) > max_targets:
            raise ValueError(f"Selection exceeds the {max_targets} asset safety limit")

        record_by_id = {record.id: record for record in records}
        if selection.mode == "explicit" or selection.selection_id is not None:
            target_order = selection.ids if selection.selection_id is None else requested
            ordered_records = [
                record_by_id[identifier]
                for identifier in target_order
                if identifier in record_by_id
            ]
            missing_ids = [
                identifier for identifier in target_order if identifier not in record_by_id
            ]
        else:
            ordered_records = records
            missing_ids = []

        total = len(ordered_records)
        archived = sum(record.is_archived for record in ordered_records)
        favorite = sum(record.is_favorite for record in ordered_records)
        trashed = sum(record.is_trashed for record in ordered_records)
        summary = AssetSelectionSummary(
            total=total,
            archived=archived,
            unarchived=total - archived,
            favorite=favorite,
            not_favorite=total - favorite,
            trashed=trashed,
            not_trashed=total - trashed,
            archive_action=("archive" if archived < total else "unarchive") if total else None,
            favorite_action=("favorite" if favorite < total else "unfavorite") if total else None,
            can_trash=trashed < total,
            can_restore=trashed > 0,
        )
        return AssetSelectionResolution(
            ids=[record.id for record in ordered_records],
            missing_ids=missing_ids,
            summary=summary,
        )

    async def selection_capabilities(
        self, selection: AssetSelectionRequest
    ) -> AssetSelectionCapabilities:
        """Return toolbar capabilities with database-side aggregate queries."""

        if selection.selection_id is not None:
            target_ids = select(SelectionSetMemberRecord.asset_id).where(
                SelectionSetMemberRecord.selection_id == selection.selection_id
            )
            predicate = AssetRecord.id.in_(target_ids)
        elif selection.mode == "explicit":
            predicate = AssetRecord.id.in_(selection.ids)
        else:
            assert selection.expression is not None
            predicate = self._compile_group(selection.expression)
            if selection.excluded_ids:
                predicate = and_(predicate, AssetRecord.id.not_in(selection.excluded_ids))

        active = and_(AssetRecord.is_trashed.is_(False), predicate)
        target_ids = select(AssetRecord.id).where(active)
        async with self._database.sessions() as session:
            count, favorite_count, archived_count, stack_count = (
                await session.execute(
                    select(
                        func.count(AssetRecord.id),
                        func.count().filter(AssetRecord.is_favorite.is_(True)),
                        func.count().filter(AssetRecord.is_archived.is_(True)),
                        func.count().filter(func.json_typeof(AssetRecord.stack) == "object"),
                    ).where(active)
                )
            ).one()
            has_albums = bool(
                await session.scalar(
                    select(exists().where(AlbumAssetRecord.asset_id.in_(target_ids)))
                )
            )
            has_tags = bool(
                await session.scalar(
                    select(exists().where(TagAssetRecord.asset_id.in_(target_ids)))
                )
            )
            single = (
                await session.scalar(select(AssetRecord).where(active).limit(1))
                if count == 1
                else None
            )

        stack = single.stack if single is not None and isinstance(single.stack, dict) else None
        return AssetSelectionCapabilities(
            count=count,
            all_favorite=count > 0 and favorite_count == count,
            all_archived=count > 0 and archived_count == count,
            has_tags=has_tags,
            has_albums=has_albums,
            has_stack_members=stack_count > 0,
            can_stack=count >= 2,
            single_asset_id=single.id if single is not None else None,
            can_set_stack_primary=bool(
                single is not None
                and stack
                and str(stack.get("primaryAssetId")) != str(single.id)
            ),
            can_remove_complete_stack=bool(stack),
        )

    async def selection_relationships(
        self, selection: AssetSelectionRequest
    ) -> AssetSelectionRelationships:
        """Return relationship options attached to any active selected asset."""

        if selection.selection_id is not None:
            selected_ids = select(SelectionSetMemberRecord.asset_id).where(
                SelectionSetMemberRecord.selection_id == selection.selection_id
            )
            predicate = AssetRecord.id.in_(selected_ids)
        elif selection.mode == "explicit":
            predicate = AssetRecord.id.in_(selection.ids)
        else:
            assert selection.expression is not None
            predicate = self._compile_group(selection.expression)
            if selection.excluded_ids:
                predicate = and_(predicate, AssetRecord.id.not_in(selection.excluded_ids))

        active = and_(AssetRecord.is_trashed.is_(False), predicate)
        album_statement = (
            select(
                AlbumRecord.id,
                AlbumRecord.album_name,
                func.count(AlbumAssetRecord.asset_id),
            )
            .join(AlbumAssetRecord, AlbumAssetRecord.album_id == AlbumRecord.id)
            .join(AssetRecord, AssetRecord.id == AlbumAssetRecord.asset_id)
            .where(active)
            .group_by(AlbumRecord.id, AlbumRecord.album_name)
            .order_by(func.lower(AlbumRecord.album_name), AlbumRecord.id)
        )
        tag_statement = (
            select(TagRecord.id, TagRecord.tag_name, func.count(TagAssetRecord.asset_id))
            .join(TagAssetRecord, TagAssetRecord.tag_id == TagRecord.id)
            .join(AssetRecord, AssetRecord.id == TagAssetRecord.asset_id)
            .where(active)
            .group_by(TagRecord.id, TagRecord.tag_name)
            .order_by(func.lower(TagRecord.tag_name), TagRecord.id)
        )
        async with self._database.sessions() as session:
            album_rows = (await session.execute(album_statement)).all()
            tag_rows = (await session.execute(tag_statement)).all()

        return AssetSelectionRelationships(
            albums=[
                AssetSelectionRelationship(
                    id=relation_id,
                    name=name,
                    selected_asset_count=count,
                )
                for relation_id, name, count in album_rows
            ],
            tags=[
                AssetSelectionRelationship(
                    id=relation_id,
                    name=name,
                    selected_asset_count=count,
                )
                for relation_id, name, count in tag_rows
            ],
        )

    async def relation_ids_for_assets(
        self, operation: Literal["remove_album", "remove_tag"], asset_ids: list[UUID]
    ) -> list[UUID]:
        """Resolve every current relation needed by a remove-all action."""

        if not asset_ids:
            return []
        model = AlbumAssetRecord if operation == "remove_album" else TagAssetRecord
        relation_column = (
            AlbumAssetRecord.album_id if operation == "remove_album" else TagAssetRecord.tag_id
        )
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(relation_column)
                        .where(model.asset_id.in_(asset_ids))
                        .distinct()
                        .order_by(relation_column)
                    )
                ).all()
            )

    async def list_matching_asset_ids(
        self, expression: SearchGroup, excluded_ids: Sequence[UUID] = ()
    ) -> list[UUID]:
        """Materialize a search result as explicit IDs at selection time."""

        predicate = self._compile_group(expression)
        statement = select(AssetRecord.id).where(AssetRecord.is_trashed.is_(False), predicate)
        if excluded_ids:
            statement = statement.where(AssetRecord.id.not_in(excluded_ids))
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        statement.order_by(AssetRecord.id)
                    )
                ).all()
            )

    async def create_selection(
        self, *, ttl_seconds: int, entity_kind: str = "asset"
    ) -> SelectionSetRecord:
        """Create an empty server-owned selection set."""

        now = datetime.now(UTC)
        record = SelectionSetRecord(
            entity_kind=entity_kind, expires_at=now + timedelta(seconds=ttl_seconds)
        )
        async with self._database.sessions() as session, session.begin():
            session.add(record)
            await session.flush()
        return record

    async def get_selection(self, selection_id: UUID) -> SelectionSetRecord | None:
        async with self._database.sessions() as session:
            return await session.get(SelectionSetRecord, selection_id)

    async def selection_ids(self, selection_id: UUID) -> list[UUID]:
        record = await self.get_selection(selection_id)
        if record is None or record.entity_kind != "asset":
            raise ValueError("Selection set was not found")
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(SelectionSetMemberRecord.asset_id)
                        .where(SelectionSetMemberRecord.selection_id == selection_id)
                        .order_by(SelectionSetMemberRecord.asset_id)
                    )
                ).all()
            )

    async def selection_membership(self, selection_id: UUID, asset_ids: list[UUID]) -> list[UUID]:
        record = await self.get_selection(selection_id)
        if record is None or record.entity_kind != "asset":
            raise ValueError("Selection set was not found")
        if not asset_ids:
            return []
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(SelectionSetMemberRecord.asset_id).where(
                            SelectionSetMemberRecord.selection_id == selection_id,
                            SelectionSetMemberRecord.asset_id.in_(asset_ids),
                        )
                    )
                ).all()
            )

    async def replace_selection_with_matching(
        self, selection_id: UUID, expression: SearchGroup
    ) -> SelectionSetRecord:
        """Replace a selection in one consistent server-side operation."""

        predicate = self._compile_group(expression)
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SelectionSetRecord)
                .where(SelectionSetRecord.id == selection_id)
                .with_for_update()
            )
            if record is None:
                raise ValueError("Selection set was not found")
            if record.entity_kind != "asset":
                raise ValueError("Selection set is not an asset selection")
            if record.status != "active" or record.expires_at <= datetime.now(UTC):
                raise ValueError("Selection set has expired")
            await session.execute(
                delete(SelectionSetMemberRecord).where(
                    SelectionSetMemberRecord.selection_id == selection_id
                )
            )
            source = select(
                literal(selection_id).label("selection_id"), AssetRecord.id.label("asset_id")
            ).where(predicate)
            await session.execute(
                insert(SelectionSetMemberRecord).from_select(["selection_id", "asset_id"], source)
            )
            record.selected_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(SelectionSetMemberRecord)
                    .where(SelectionSetMemberRecord.selection_id == selection_id)
                )
            )
            record.revision += 1
            record.updated_at = datetime.now(UTC)
            await session.flush()
        return record

    async def update_selection_members(
        self,
        selection_id: UUID,
        asset_ids: list[UUID],
        *,
        selected: bool,
        revision: int,
    ) -> SelectionSetRecord:
        """Apply one page-sized add/remove delta with optimistic revisioning."""

        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(SelectionSetRecord)
                .where(SelectionSetRecord.id == selection_id)
                .with_for_update()
            )
            if record is None:
                raise ValueError("Selection set was not found")
            if record.entity_kind != "asset":
                raise ValueError("Selection set is not an asset selection")
            if record.status != "active" or record.expires_at <= datetime.now(UTC):
                raise ValueError("Selection set has expired")
            if record.revision != revision:
                raise ValueError("Selection set changed; reload its membership")
            if selected:
                await session.execute(
                    insert(SelectionSetMemberRecord)
                    .values(
                        [
                            {"selection_id": selection_id, "asset_id": asset_id}
                            for asset_id in asset_ids
                        ]
                    )
                    .on_conflict_do_nothing()
                )
            else:
                await session.execute(
                    delete(SelectionSetMemberRecord).where(
                        SelectionSetMemberRecord.selection_id == selection_id,
                        SelectionSetMemberRecord.asset_id.in_(asset_ids),
                    )
                )
            record.selected_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(SelectionSetMemberRecord)
                    .where(SelectionSetMemberRecord.selection_id == selection_id)
                )
            )
            record.revision += 1
            record.updated_at = datetime.now(UTC)
            await session.flush()
        return record

    async def applicable_action_ids(
        self,
        operation: AssetActionOperation,
        target_ids: list[UUID],
        relation_id: UUID | None = None,
    ) -> set[UUID]:
        """Return targets whose synchronized state still needs the operation."""

        if not target_ids:
            return set()
        if operation == "stack":
            statement = select(AssetRecord.id).where(AssetRecord.id.in_(target_ids))
        elif operation in {"remove_from_stack", "remove_stack"}:
            statement = select(AssetRecord.id).where(
                AssetRecord.id.in_(target_ids),
                AssetRecord.stack.is_not(None),
                func.json_typeof(AssetRecord.stack) != "null",
            )
        elif operation == "set_stack_primary":
            async with self._database.sessions() as session:
                rows = (
                    await session.execute(
                        select(AssetRecord.id, AssetRecord.stack).where(
                            AssetRecord.id.in_(target_ids),
                            AssetRecord.stack.is_not(None),
                            func.json_typeof(AssetRecord.stack) != "null",
                        )
                    )
                ).all()
            return {
                identifier
                for identifier, payload in rows
                if isinstance(payload, dict)
                and str(payload.get("primaryAssetId")) != str(identifier)
            }
        elif operation in {"add_album", "add_tag", "remove_album", "remove_tag"}:
            assert relation_id is not None
            album_action = operation in {"add_album", "remove_album"}
            model = AlbumAssetRecord if album_action else TagAssetRecord
            relation_column = AlbumAssetRecord.album_id if album_action else TagAssetRecord.tag_id
            membership = select(model.asset_id).where(
                model.asset_id.in_(target_ids),
                relation_column == relation_id,
            )
            if operation in {"remove_album", "remove_tag"}:
                statement = membership
            else:
                statement = select(AssetRecord.id).where(
                    AssetRecord.id.in_(target_ids),
                    AssetRecord.id.not_in(membership),
                )
        else:
            column, desired = {
                "archive": (AssetRecord.is_archived, True),
                "unarchive": (AssetRecord.is_archived, False),
                "favorite": (AssetRecord.is_favorite, True),
                "unfavorite": (AssetRecord.is_favorite, False),
                "trash": (AssetRecord.is_trashed, True),
                "restore": (AssetRecord.is_trashed, False),
            }[operation]
            statement = select(AssetRecord.id).where(
                AssetRecord.id.in_(target_ids),
                column != desired,
            )
        async with self._database.sessions() as session:
            return set((await session.scalars(statement)).all())

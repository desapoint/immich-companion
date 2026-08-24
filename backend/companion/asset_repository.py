"""Companion-owned asset persistence, reconciliation, and SQL search."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Float, and_, cast, delete, exists, func, not_, or_, select, true
from sqlalchemy.dialects.postgresql import insert

from companion.asset_schema import (
    AlbumOption,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetSummary,
    SearchCondition,
    SearchGroup,
    StructuredAssetSearchQuery,
)
from companion.database import DatabaseManager
from companion.immich import ImmichAlbum, ImmichAsset
from companion.models import AlbumAssetRecord, AlbumRecord, AssetRecord


class AssetRepository:
    """Persist and search synchronized assets through SQLAlchemy 2."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @staticmethod
    def _values(asset: ImmichAsset, synced_at: datetime) -> dict[str, object]:
        return {
            "id": asset.id,
            "owner_id": asset.owner_id,
            "library_id": asset.library_id,
            "asset_type": asset.asset_type,
            "original_file_name": asset.original_file_name,
            "original_path": asset.original_path,
            "original_mime_type": asset.original_mime_type,
            "checksum": asset.checksum,
            "width": asset.width,
            "height": asset.height,
            "duration": asset.duration,
            "thumbhash": asset.thumbhash,
            "file_created_at": asset.file_created_at,
            "file_modified_at": asset.file_modified_at,
            "local_date_time": asset.local_date_time,
            "immich_created_at": asset.created_at,
            "immich_updated_at": asset.updated_at,
            "is_favorite": asset.is_favorite,
            "is_archived": asset.is_archived,
            "is_trashed": asset.is_trashed,
            "is_offline": asset.is_offline,
            "is_edited": asset.is_edited,
            "has_metadata": asset.has_metadata,
            "visibility": asset.visibility,
            "live_photo_video_id": asset.live_photo_video_id,
            "exif_info": asset.exif_info,
            "people": asset.people,
            "tags": asset.tags,
            "stack": asset.stack,
            "synced_at": synced_at,
        }

    async def reconcile(
        self,
        assets: list[ImmichAsset],
        albums: list[ImmichAlbum] | None = None,
    ) -> tuple[int, int, int]:
        """Upsert a complete traversal and remove rows absent from that traversal."""

        synced_at = datetime.now(UTC)
        unique_assets = {asset.id: asset for asset in assets}
        asset_ids = list(unique_assets)
        rows = [self._values(asset, synced_at) for asset in unique_assets.values()]

        async with self._database.sessions() as session, session.begin():
            existing_ids = set(
                (
                    await session.scalars(
                        select(AssetRecord.id).where(AssetRecord.id.in_(asset_ids))
                    )
                ).all()
            )

            if rows:
                statement = insert(AssetRecord).values(rows)
                update_columns = {
                    column.name: getattr(statement.excluded, column.name)
                    for column in AssetRecord.__table__.columns
                    if column.name != "id"
                }
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[AssetRecord.id],
                        set_=update_columns,
                    )
                )
                removed_result = await session.execute(
                    delete(AssetRecord).where(AssetRecord.id.not_in(asset_ids))
                )
            else:
                removed_result = await session.execute(delete(AssetRecord))

            if albums is not None:
                album_rows = [
                    {
                        "id": album.id,
                        "album_name": album.album_name,
                        "description": album.description,
                        "album_thumbnail_asset_id": album.album_thumbnail_asset_id,
                        "asset_count": album.asset_count,
                        "immich_created_at": album.created_at,
                        "immich_updated_at": album.updated_at,
                        "synced_at": synced_at,
                    }
                    for album in albums
                ]
                await session.execute(delete(AlbumAssetRecord))
                if album_rows:
                    album_statement = insert(AlbumRecord).values(album_rows)
                    await session.execute(
                        album_statement.on_conflict_do_update(
                            index_elements=[AlbumRecord.id],
                            set_={
                                column.name: getattr(album_statement.excluded, column.name)
                                for column in AlbumRecord.__table__.columns
                                if column.name != "id"
                            },
                        )
                    )
                    album_ids = [album.id for album in albums]
                    await session.execute(
                        delete(AlbumRecord).where(AlbumRecord.id.not_in(album_ids))
                    )
                    memberships = [
                        {"album_id": album.id, "asset_id": asset_id}
                        for album in albums
                        for asset_id in album.asset_ids
                        if asset_id in unique_assets
                    ]
                    if memberships:
                        await session.execute(
                            insert(AlbumAssetRecord)
                            .values(memberships)
                            .on_conflict_do_nothing()
                        )
                else:
                    await session.execute(delete(AlbumRecord))

        created = len(unique_assets) - len(existing_ids)
        updated = len(existing_ids)
        removed = int(removed_result.rowcount or 0)
        return created, updated, removed

    async def search(self, criteria: AssetSearchQuery) -> AssetSearchResponse:
        """Compose safe basic filters and return a stable result page."""

        predicates = []
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

        return await self._search_page(predicates, criteria.page, criteria.page_size)

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
            return column == int(value)
        if condition.field == "aspect_ratio":
            ratio = cast(AssetRecord.width, Float) / cast(AssetRecord.height, Float)
            numeric = float(value)
            if condition.operator == "at_least":
                return ratio >= numeric
            if condition.operator == "at_most":
                return ratio <= numeric
            return func.abs(ratio - numeric) <= 0.005
        if condition.field in {"favorite", "archived", "trashed"}:
            column = {
                "favorite": AssetRecord.is_favorite,
                "archived": AssetRecord.is_archived,
                "trashed": AssetRecord.is_trashed,
            }[condition.field]
            return column == bool(value)
        if condition.field == "album":
            membership = exists(
                select(1).where(
                    AlbumAssetRecord.asset_id == AssetRecord.id,
                    AlbumAssetRecord.album_id == UUID(str(value)),
                )
            )
            return not_(membership) if condition.operator == "not_in_album" else membership
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

    async def search_structured(
        self, criteria: StructuredAssetSearchQuery
    ) -> AssetSearchResponse:
        """Compile a validated recursive expression and return one stable page."""

        predicate = self._compile_group(criteria.expression)
        return await self._search_page([predicate], criteria.page, criteria.page_size)

    async def _search_page(
        self,
        predicates: list[object],
        page: int,
        page_size: int,
    ) -> AssetSearchResponse:
        filtered = select(AssetRecord).where(*predicates)
        count_statement = select(func.count()).select_from(AssetRecord).where(*predicates)
        result_statement = (
            filtered.order_by(AssetRecord.file_created_at.desc(), AssetRecord.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        async with self._database.sessions() as session:
            total = int(await session.scalar(count_statement) or 0)
            records = list((await session.scalars(result_statement)).all())

        return AssetSearchResponse(
            items=[AssetSummary.from_record(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )

    async def list_albums(self) -> list[AlbumOption]:
        """Return stable album choices for the structured search builder."""

        statement = select(AlbumRecord).order_by(
            func.lower(AlbumRecord.album_name), AlbumRecord.id
        )
        async with self._database.sessions() as session:
            albums = list((await session.scalars(statement)).all())
        return [
            AlbumOption(id=album.id, name=album.album_name, asset_count=album.asset_count)
            for album in albums
        ]

    async def has_asset(self, asset_id: UUID) -> bool:
        """Return whether an asset exists in the synchronized index."""

        async with self._database.sessions() as session:
            return await session.scalar(
                select(AssetRecord.id).where(AssetRecord.id == asset_id)
            ) is not None

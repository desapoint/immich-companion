"""Companion-owned asset persistence, reconciliation, and SQL search."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    delete,
    func,
    select,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert

from companion.asset_repository_catalog import AssetCatalogRelationMixin, SyncValidationError
from companion.asset_repository_hydration import (
    asset_fingerprint as _asset_fingerprint,
)
from companion.asset_repository_hydration import (
    immich_asset as _immich_asset,
)
from companion.asset_repository_hydration import similarity_upsert_changes
from companion.asset_repository_search import AssetSearchMixin
from companion.asset_repository_selection import AssetSelectionMixin
from companion.asset_schema import (
    AlbumOption,
    AssetSummary,
    TagOption,
)
from companion.database import DatabaseManager
from companion.immich import ImmichAlbum, ImmichAsset, ImmichTag
from companion.models import (
    AlbumAssetRecord,
    AlbumRecord,
    AssetRecord,
    SimilarityAssetChangeRecord,
    TagAssetRecord,
    TagRecord,
)

__all__ = ["ASPECT_RATIO_RELATIVE_TOLERANCE", "AssetRepository", "similarity_upsert_changes"]


ASPECT_RATIO_RELATIVE_TOLERANCE = 0.001
ASSET_HYDRATION_BATCH_SIZE = 1_000


class AssetRepository(AssetSearchMixin, AssetSelectionMixin, AssetCatalogRelationMixin):
    """Persist and search synchronized assets through SQLAlchemy 2."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @staticmethod
    async def _queue_similarity_changes(
        session,
        changes: list[tuple[UUID, str, str | None]],
    ) -> None:
        """Coalesce asset changes in the same transaction as synchronized metadata."""

        if not changes:
            return
        enqueued_at = datetime.now(UTC)
        values = [
            {
                "asset_id": asset_id,
                "operation": operation,
                "source_fingerprint": source_fingerprint,
                "enqueued_at": enqueued_at,
            }
            for asset_id, operation, source_fingerprint in changes
        ]
        statement = insert(SimilarityAssetChangeRecord).values(values)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[SimilarityAssetChangeRecord.asset_id],
                set_={
                    "operation": statement.excluded.operation,
                    "source_fingerprint": statement.excluded.source_fingerprint,
                    "enqueued_at": statement.excluded.enqueued_at,
                },
            )
        )

    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]:
        """Load active synchronized assets without issuing one unbounded IN query."""

        if not asset_ids:
            return {}
        unique_ids = list(dict.fromkeys(asset_ids))
        records: list[AssetRecord] = []
        async with self._database.sessions() as session:
            for offset in range(0, len(unique_ids), ASSET_HYDRATION_BATCH_SIZE):
                batch = unique_ids[offset : offset + ASSET_HYDRATION_BATCH_SIZE]
                records.extend(
                    (
                        await session.scalars(
                            select(AssetRecord).where(
                                AssetRecord.id.in_(batch),
                                AssetRecord.is_trashed.is_(False),
                            )
                        )
                    ).all()
                )
        return {record.id: self._immich_asset(record) for record in records}

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
            "file_size_bytes": asset.file_size_bytes,
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
            # EXIF is fetched live for the viewer and is not written by the
            # inventory path. People synchronization is intentionally deferred.
            "people": [],
            "tags": asset.tags,
            "stack": asset.stack,
            "synced_at": synced_at,
        }

    async def reconcile(
        self,
        assets: list[ImmichAsset],
        albums: list[ImmichAlbum] | None = None,
        tags: list[ImmichTag] | None = None,
    ) -> tuple[int, int, int]:
        """Upsert a complete traversal and remove rows absent from that traversal."""

        synced_at = datetime.now(UTC)
        unique_assets = {asset.id: asset for asset in assets if not asset.is_trashed}
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
                    name: getattr(statement.excluded, name) for name in rows[0] if name != "id"
                }
                update_columns["file_size_bytes"] = func.coalesce(
                    statement.excluded.file_size_bytes,
                    AssetRecord.file_size_bytes,
                )
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
                            insert(AlbumAssetRecord).values(memberships).on_conflict_do_nothing()
                        )
                else:
                    await session.execute(delete(AlbumRecord))

            if tags is not None:
                await session.execute(delete(TagAssetRecord))
                tag_rows = []
                tag_memberships = []
                for tag in tags:
                    member_ids = [
                        asset_id for asset_id in tag.asset_ids if asset_id in unique_assets
                    ]
                    tag_rows.append(
                        {
                            "id": tag.id,
                            "tag_name": tag.name,
                            "tag_value": tag.value,
                            "color": tag.color,
                            "asset_count": len(member_ids),
                            "synced_at": synced_at,
                        }
                    )
                    tag_memberships.extend(
                        {"tag_id": tag.id, "asset_id": asset_id} for asset_id in member_ids
                    )
                if tag_rows:
                    tag_statement = insert(TagRecord).values(tag_rows)
                    await session.execute(
                        tag_statement.on_conflict_do_update(
                            index_elements=[TagRecord.id],
                            set_={
                                column.name: getattr(tag_statement.excluded, column.name)
                                for column in TagRecord.__table__.columns
                                if column.name != "id"
                            },
                        )
                    )
                    tag_ids = [tag.id for tag in tags]
                    await session.execute(delete(TagRecord).where(TagRecord.id.not_in(tag_ids)))
                    if tag_memberships:
                        await session.execute(
                            insert(TagAssetRecord).values(tag_memberships).on_conflict_do_nothing()
                        )
                else:
                    await session.execute(delete(TagRecord))

        created = len(unique_assets) - len(existing_ids)
        updated = len(existing_ids)
        removed = int(removed_result.rowcount or 0)
        return created, updated, removed

    _immich_asset = staticmethod(_immich_asset)
    _fingerprint = staticmethod(_asset_fingerprint)

    async def validate_generation(
        self,
        generation: int,
        counters: dict[str, int],
        *,
        full: bool,
        allow_counter_repair: bool = False,
    ) -> dict[str, int]:
        """Prove every staged catalog, relation, stack, and full asset count."""

        checks = {
            "albums_seen": select(func.count())
            .select_from(AlbumRecord)
            .where(AlbumRecord.sync_generation == generation),
            "tags_seen": select(func.count())
            .select_from(TagRecord)
            .where(TagRecord.sync_generation == generation),
            "album_memberships": select(func.count())
            .select_from(AlbumAssetRecord)
            .where(AlbumAssetRecord.sync_generation == generation),
            "tag_memberships": select(func.count())
            .select_from(TagAssetRecord)
            .where(TagAssetRecord.sync_generation == generation),
            "stack_members": select(func.count())
            .select_from(AssetRecord)
            .where(AssetRecord.stack_generation == generation)
            .where(func.json_typeof(AssetRecord.stack) != "null"),
        }
        if full:
            checks["assets_seen"] = (
                select(func.count())
                .select_from(AssetRecord)
                .where(AssetRecord.sync_generation == generation)
            )
        async with self._database.sessions() as session:
            actual = {
                name: int(await session.scalar(statement) or 0)
                for name, statement in checks.items()
            }
        mismatches = {
            name: (counters.get(name, 0), value)
            for name, value in actual.items()
            if counters.get(name, 0) != value
        }
        if mismatches and not allow_counter_repair:
            raise SyncValidationError(
                "Staged generation validation failed: "
                + ", ".join(
                    f"{name} expected {expected}, found {value}"
                    for name, (expected, value) in mismatches.items()
                )
            )
        return actual

    async def finalize_generation(
        self,
        generation: int,
        *,
        remove_assets: bool,
        batch_size: int,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> dict[str, int]:
        """Delete only absence proven by a fully successful staged traversal."""

        removed = {
            "album_memberships_removed": 0,
            "tag_memberships_removed": 0,
            "albums_removed": 0,
            "tags_removed": 0,
            "stacks_cleared": 0,
            "assets_removed": 0,
        }
        removed["album_memberships_removed"] = await self._delete_stale_memberships(
            AlbumAssetRecord,
            (AlbumAssetRecord.album_id, AlbumAssetRecord.asset_id),
            generation,
            batch_size,
        )
        removed["tag_memberships_removed"] = await self._delete_stale_memberships(
            TagAssetRecord,
            (TagAssetRecord.tag_id, TagAssetRecord.asset_id),
            generation,
            batch_size,
        )
        removed["albums_removed"] = await self._delete_stale_entities(
            AlbumRecord, AlbumRecord.id, AlbumRecord.sync_generation, generation, batch_size
        )
        removed["tags_removed"] = await self._delete_stale_entities(
            TagRecord, TagRecord.id, TagRecord.sync_generation, generation, batch_size
        )
        while True:
            async with self._database.sessions() as session, session.begin():
                identifiers = list(
                    (
                        await session.scalars(
                            select(AssetRecord.id)
                            .where(AssetRecord.stack_generation != generation)
                            .where(func.json_typeof(AssetRecord.stack) != "null")
                            .limit(batch_size)
                        )
                    ).all()
                )
                if not identifiers:
                    break
                result = await session.execute(
                    update(AssetRecord)
                    .where(AssetRecord.id.in_(identifiers))
                    .values(stack=None, stack_generation=generation)
                )
                removed["stacks_cleared"] += int(result.rowcount or 0)
        if remove_assets:
            removed["assets_removed"] = await self._delete_stale_entities(
                AssetRecord,
                AssetRecord.id,
                AssetRecord.sync_generation,
                generation,
                batch_size,
            )
        elif window_start is not None and window_end is not None:
            removed["assets_removed"] = await self._delete_missing_assets_in_window(
                generation,
                window_start,
                window_end,
                batch_size,
            )
        return removed

    async def _delete_missing_assets_in_window(
        self,
        generation: int,
        window_start: datetime,
        window_end: datetime,
        batch_size: int,
    ) -> int:
        """Remove active rows absent from a completed bounded incremental traversal."""

        if window_start >= window_end:
            return 0
        removed = 0
        while True:
            async with self._database.sessions() as session, session.begin():
                identifiers = list(
                    (
                        await session.scalars(
                            select(AssetRecord.id)
                            .where(
                                AssetRecord.is_trashed.is_(False),
                                AssetRecord.sync_generation != generation,
                                AssetRecord.immich_updated_at.is_not(None),
                                AssetRecord.immich_updated_at > window_start,
                                AssetRecord.immich_updated_at < window_end,
                            )
                            .limit(batch_size)
                        )
                    ).all()
                )
                if not identifiers:
                    return removed
                await self._queue_similarity_changes(
                    session,
                    [(identifier, "delete", None) for identifier in identifiers],
                )
                result = await session.execute(
                    delete(AssetRecord).where(AssetRecord.id.in_(identifiers))
                )
                removed += int(result.rowcount or 0)

    async def _delete_stale_memberships(
        self,
        model,
        columns: tuple[object, object],
        generation: int,
        batch_size: int,
    ) -> int:
        removed = 0
        while True:
            async with self._database.sessions() as session, session.begin():
                keys = list(
                    (
                        await session.execute(
                            select(*columns)
                            .where(model.sync_generation != generation)
                            .limit(batch_size)
                        )
                    ).tuples()
                )
                if not keys:
                    return removed
                result = await session.execute(delete(model).where(tuple_(*columns).in_(keys)))
                removed += int(result.rowcount or 0)

    async def _delete_stale_entities(
        self,
        model,
        identifier_column,
        generation_column,
        generation: int,
        batch_size: int,
    ) -> int:
        removed = 0
        while True:
            async with self._database.sessions() as session, session.begin():
                identifiers = list(
                    (
                        await session.scalars(
                            select(identifier_column)
                            .where(generation_column != generation)
                            .limit(batch_size)
                        )
                    ).all()
                )
                if not identifiers:
                    return removed
                if model is AssetRecord:
                    await self._queue_similarity_changes(
                        session,
                        [(identifier, "delete", None) for identifier in identifiers],
                    )
                result = await session.execute(
                    delete(model).where(identifier_column.in_(identifiers))
                )
                removed += int(result.rowcount or 0)

    async def list_albums(self) -> list[AlbumOption]:
        """Return stable album choices for the structured search builder."""

        statement = select(AlbumRecord).order_by(func.lower(AlbumRecord.album_name), AlbumRecord.id)
        async with self._database.sessions() as session:
            albums = list((await session.scalars(statement)).all())
        return [
            AlbumOption(id=album.id, name=album.album_name, asset_count=album.asset_count)
            for album in albums
        ]

    async def album_asset_counts(self) -> dict[UUID, int]:
        """Return active-workspace membership counts keyed by album."""

        async with self._database.sessions() as session:
            rows = (await session.execute(select(AlbumRecord.id, AlbumRecord.asset_count))).all()
        return {identifier: count for identifier, count in rows}

    async def list_tags(self) -> list[TagOption]:
        """Return stable tag choices for Simple and Expert search controls."""

        statement = select(TagRecord).order_by(func.lower(TagRecord.tag_name), TagRecord.id)
        async with self._database.sessions() as session:
            tags = list((await session.scalars(statement)).all())
        return [
            TagOption(
                id=tag.id,
                name=tag.tag_name,
                color=tag.color,
                asset_count=tag.asset_count,
            )
            for tag in tags
        ]

    async def tag_asset_counts(self) -> dict[UUID, int]:
        """Return active-workspace membership counts keyed by tag."""

        async with self._database.sessions() as session:
            rows = (await session.execute(select(TagRecord.id, TagRecord.asset_count))).all()
        return {identifier: count for identifier, count in rows}

    async def has_asset(self, asset_id: UUID) -> bool:
        """Return whether an asset exists in the synchronized index."""

        async with self._database.sessions() as session:
            return (
                await session.scalar(select(AssetRecord.id).where(AssetRecord.id == asset_id))
                is not None
            )

    async def get_relation_ids(
        self,
        asset_ids: set[UUID] | list[UUID],
    ) -> dict[UUID, tuple[set[UUID], set[UUID]]]:
        """Load album/tag membership for a bounded asset set without N+1 queries."""

        unique_ids = list(dict.fromkeys(asset_ids))
        relations = {asset_id: (set(), set()) for asset_id in unique_ids}
        if not unique_ids:
            return relations
        async with self._database.sessions() as session:
            album_rows = list(
                (
                    await session.execute(
                        select(AlbumAssetRecord.asset_id, AlbumAssetRecord.album_id).where(
                            AlbumAssetRecord.asset_id.in_(unique_ids)
                        )
                    )
                ).all()
            )
            tag_rows = list(
                (
                    await session.execute(
                        select(TagAssetRecord.asset_id, TagAssetRecord.tag_id).where(
                            TagAssetRecord.asset_id.in_(unique_ids)
                        )
                    )
                ).all()
            )
        for asset_id, album_id in album_rows:
            relations.setdefault(asset_id, (set(), set()))[0].add(album_id)
        for asset_id, tag_id in tag_rows:
            relations.setdefault(asset_id, (set(), set()))[1].add(tag_id)
        return relations



    async def get_asset_summary(self, asset_id: UUID) -> AssetSummary | None:
        """Return one synchronized asset summary without applying search filters."""

        async with self._database.sessions() as session:
            record = await session.get(AssetRecord, asset_id)
            if record is not None and record.is_trashed:
                return None
            if record is None:
                return None
            summaries = await self._summaries_for_records(session, [record])
        return summaries[0] if summaries else None

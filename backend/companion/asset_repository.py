"""Companion-owned asset persistence, reconciliation, and SQL search."""

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
from companion.asset_repository_selection import AssetSelectionMixin
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


class AssetRepository(AssetSearchMixin, AssetSelectionMixin):
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
        """Load active synchronized assets without calling Immich per member."""

        if not asset_ids:
            return {}
        async with self._database.sessions() as session:
            records = list(
                (
                    await session.scalars(
                        select(AssetRecord).where(
                            AssetRecord.id.in_(set(asset_ids)),
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

    async def upsert_album_catalog(
        self,
        albums: list[ImmichAlbum],
        generation: int,
    ) -> tuple[int, int]:
        """Upsert a complete album catalog without deleting prior rows early."""

        if not albums:
            return 0, 0
        synced_at = datetime.now(UTC)
        rows = [
            {
                "id": album.id,
                "album_name": album.album_name,
                "description": album.description,
                "album_thumbnail_asset_id": album.album_thumbnail_asset_id,
                "asset_count": album.asset_count,
                "immich_created_at": album.created_at,
                "immich_updated_at": album.updated_at,
                "synced_at": synced_at,
                "sync_generation": generation,
            }
            for album in albums
        ]
        async with self._database.sessions() as session, session.begin():
            existing = {
                identifier: previous_generation
                for identifier, previous_generation in (
                    await session.execute(
                        select(AlbumRecord.id, AlbumRecord.sync_generation).where(
                            AlbumRecord.id.in_([album.id for album in albums])
                        )
                    )
                )
            }
            statement = insert(AlbumRecord).values(rows)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AlbumRecord.id],
                    set_={
                        name: getattr(statement.excluded, name) for name in rows[0] if name != "id"
                    },
                )
            )
        created = len(rows) - len(existing)
        newly_observed = sum(value != generation for value in existing.values())
        return created, newly_observed

    async def upsert_tag_catalog(
        self,
        tags: list[ImmichTag],
        generation: int,
    ) -> tuple[int, int]:
        """Upsert a complete tag catalog without deleting prior rows early."""

        if not tags:
            return 0, 0
        synced_at = datetime.now(UTC)
        rows = [
            {
                "id": tag.id,
                "tag_name": tag.name,
                "tag_value": tag.value,
                "color": tag.color,
                "asset_count": len(tag.asset_ids),
                "synced_at": synced_at,
                "sync_generation": generation,
            }
            for tag in tags
        ]
        async with self._database.sessions() as session, session.begin():
            existing = {
                identifier: previous_generation
                for identifier, previous_generation in (
                    await session.execute(
                        select(TagRecord.id, TagRecord.sync_generation).where(
                            TagRecord.id.in_([tag.id for tag in tags])
                        )
                    )
                )
            }
            statement = insert(TagRecord).values(rows)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[TagRecord.id],
                    set_={
                        name: getattr(statement.excluded, name) for name in rows[0] if name != "id"
                    },
                )
            )
        created = len(rows) - len(existing)
        newly_observed = sum(value != generation for value in existing.values())
        return created, newly_observed

    async def upsert_asset_batch(
        self,
        assets: list[ImmichAsset],
        generation: int,
        *,
        track_similarity_changes: bool = True,
    ) -> tuple[int, int, int]:
        """Commit active assets and evict any trashed API payloads."""

        if not assets:
            return 0, 0, 0
        trashed_ids = [asset.id for asset in assets if asset.is_trashed]
        if trashed_ids:
            await self.remove_assets(trashed_ids)
        assets = [asset for asset in assets if not asset.is_trashed]
        if not assets:
            return 0, 0, 0
        synced_at = datetime.now(UTC)
        rows = []
        fingerprints: dict[UUID, str] = {}
        for asset in assets:
            fingerprint = self._fingerprint(asset)
            fingerprints[asset.id] = fingerprint
            rows.append(
                {
                    **self._values(asset, synced_at),
                    "sync_fingerprint": fingerprint,
                    "sync_generation": generation,
                }
            )
        async with self._database.sessions() as session, session.begin():
            existing = {
                identifier: (fingerprint, previous_generation, file_size, modified_at)
                for identifier, fingerprint, previous_generation, file_size, modified_at in (
                    await session.execute(
                        select(
                            AssetRecord.id,
                            AssetRecord.sync_fingerprint,
                            AssetRecord.sync_generation,
                            AssetRecord.file_size_bytes,
                            AssetRecord.file_modified_at,
                        ).where(AssetRecord.id.in_([asset.id for asset in assets]))
                    )
                )
            }
            statement = insert(AssetRecord).values(rows)
            payload_changed = or_(
                AssetRecord.sync_fingerprint.is_(None),
                AssetRecord.sync_fingerprint != statement.excluded.sync_fingerprint,
            )
            update_columns = {"sync_generation": statement.excluded.sync_generation}
            for name in rows[0]:
                if name in {"id", "sync_generation", "stack", "stack_generation"}:
                    continue
                incoming = getattr(statement.excluded, name)
                if name == "file_size_bytes":
                    incoming = func.coalesce(incoming, AssetRecord.file_size_bytes)
                update_columns[name] = case(
                    (payload_changed, incoming),
                    else_=getattr(AssetRecord, name),
                )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AssetRecord.id],
                    set_=update_columns,
                )
            )
            if track_similarity_changes:
                await self._queue_similarity_changes(
                    session,
                    similarity_upsert_changes(assets, existing),
                )
        created = len(rows) - len(existing)
        changed = 0
        unchanged = 0
        for identifier, fingerprint in fingerprints.items():
            previous = existing.get(identifier)
            if previous is None or previous[1] == generation:
                continue
            if previous[0] == fingerprint:
                unchanged += 1
            else:
                changed += 1
        return created, changed, unchanged

    async def refresh_asset(
        self, asset: ImmichAsset, *, track_similarity_changes: bool = True
    ) -> None:
        """Upsert one active asset or evict it when Immich reports it trashed."""

        if asset.is_trashed:
            await self.remove_asset(asset.id)
            return
        synced_at = datetime.now(UTC)
        fingerprint = self._fingerprint(asset)
        insert_values = {
            **self._values(asset, synced_at),
            "sync_fingerprint": fingerprint,
        }
        # Stack state is owned by the independent stack synchronization stage.
        insert_values.pop("stack", None)
        update_values = dict(insert_values)
        update_values.pop("id", None)
        update_values.pop("sync_generation", None)
        update_values.pop("stack_generation", None)
        if asset.file_size_bytes is None:
            update_values.pop("file_size_bytes", None)
        async with self._database.sessions() as session, session.begin():
            previous = (
                await session.execute(
                    select(
                        AssetRecord.sync_fingerprint,
                        AssetRecord.sync_generation,
                        AssetRecord.file_size_bytes,
                        AssetRecord.file_modified_at,
                    ).where(AssetRecord.id == asset.id)
                )
            ).one_or_none()
            await session.execute(
                insert(AssetRecord)
                .values(insert_values)
                .on_conflict_do_update(
                    index_elements=[AssetRecord.id],
                    set_=update_values,
                )
            )
            changes = similarity_upsert_changes(
                [asset],
                {asset.id: tuple(previous)} if previous is not None else {},
            )
            if changes and track_similarity_changes:
                await self._queue_similarity_changes(
                    session,
                    changes,
                )

    async def replace_asset_stack_snapshots(
        self,
        asset_ids: list[UUID],
        stack_payload_by_asset: dict[UUID, dict[str, object]],
    ) -> None:
        """Persist authoritative stack state for one targeted repair set."""

        unique_ids = list(dict.fromkeys(asset_ids))
        if not unique_ids:
            return
        async with self._database.sessions() as session, session.begin():
            for asset_id in unique_ids:
                await session.execute(
                    update(AssetRecord)
                    .where(AssetRecord.id == asset_id)
                    .values(stack=stack_payload_by_asset.get(asset_id))
                )

    async def stack_asset_ids(self, asset_id: UUID) -> list[UUID]:
        """Return the locally synchronized members of an asset's stack."""

        stack = await self.get_asset_stack(asset_id)
        if stack is None:
            return []
        payload = stack[1]
        members = payload.get("assets")
        if not isinstance(members, list):
            return []
        ids: list[UUID] = []
        for member in members:
            if not isinstance(member, dict):
                continue
            try:
                member_id = UUID(str(member.get("id")))
            except (TypeError, ValueError):
                continue
            if member_id not in ids:
                ids.append(member_id)
        return ids

    async def get_asset_stack(self, asset_id: UUID) -> tuple[UUID, dict[str, object]] | None:
        """Return an asset's synchronized stack ID and payload, if present."""

        async with self._database.sessions() as session:
            payload = await session.scalar(
                select(AssetRecord.stack).where(AssetRecord.id == asset_id)
            )
        if not isinstance(payload, dict):
            return None
        try:
            stack_id = UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError):
            return None
        return stack_id, payload

    async def remove_asset(self, asset_id: UUID) -> int:
        """Remove one API-confirmed permanent deletion and its memberships."""

        return await self.remove_assets([asset_id])

    async def remove_assets(self, asset_ids: list[UUID]) -> int:
        """Remove API-confirmed unavailable assets and their memberships."""

        if not asset_ids:
            return 0

        unique_ids = list(dict.fromkeys(asset_ids))
        async with self._database.sessions() as session, session.begin():
            await self._queue_similarity_changes(
                session,
                [(asset_id, "delete", None) for asset_id in unique_ids],
            )
            result = await session.execute(
                delete(AssetRecord).where(AssetRecord.id.in_(unique_ids))
            )
            return int(result.rowcount or 0)

    async def apply_asset_action_event(
        self, operation: AssetActionOperation, asset_ids: list[UUID]
    ) -> None:
        """Reflect an API-confirmed flag change while durable repair is queued."""

        flag = {
            "favorite": (AssetRecord.is_favorite, True),
            "unfavorite": (AssetRecord.is_favorite, False),
            "archive": (AssetRecord.is_archived, True),
            "unarchive": (AssetRecord.is_archived, False),
        }.get(operation)
        if flag is None or not asset_ids:
            return
        column, value = flag
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                update(AssetRecord).where(AssetRecord.id.in_(asset_ids)).values({column: value})
            )

    async def apply_membership_event(
        self,
        relation: str,
        relation_id: UUID,
        asset_id: UUID,
        present: bool,
    ) -> None:
        """Apply one authoritative album/tag membership delta."""

        model = AlbumAssetRecord if relation == "album" else TagAssetRecord
        relation_column = model.album_id if relation == "album" else model.tag_id
        async with self._database.sessions() as session, session.begin():
            if present:
                generation = await session.scalar(
                    select(AssetRecord.sync_generation).where(AssetRecord.id == asset_id)
                )
                if generation is None:
                    raise SyncValidationError(
                        f"{relation} membership referenced unknown asset {asset_id}"
                    )
                await session.execute(
                    insert(model)
                    .values(
                        **{
                            "asset_id": asset_id,
                            "sync_generation": generation,
                            ("album_id" if relation == "album" else "tag_id"): relation_id,
                        }
                    )
                    .on_conflict_do_update(
                        index_elements=[relation_column, model.asset_id],
                        set_={"sync_generation": generation},
                    )
                )
            else:
                await session.execute(
                    delete(model).where(
                        relation_column == relation_id,
                        model.asset_id == asset_id,
                    )
                )

    async def replace_album_memberships(self, album_id: UUID, asset_ids: list[UUID]) -> int:
        """Replace one album snapshot after its complete remote traversal succeeds."""

        unique_ids = list(dict.fromkeys(asset_ids))
        async with self._database.sessions() as session, session.begin():
            if unique_ids:
                await session.execute(
                    delete(AlbumAssetRecord).where(
                        AlbumAssetRecord.album_id == album_id,
                        AlbumAssetRecord.asset_id.not_in(unique_ids),
                    )
                )
                await session.execute(
                    insert(AlbumAssetRecord)
                    .values(
                        [{"album_id": album_id, "asset_id": asset_id} for asset_id in unique_ids]
                    )
                    .on_conflict_do_nothing()
                )
            else:
                await session.execute(
                    delete(AlbumAssetRecord).where(AlbumAssetRecord.album_id == album_id)
                )
            count = await session.scalar(
                select(func.count())
                .select_from(AlbumAssetRecord)
                .where(AlbumAssetRecord.album_id == album_id)
            )
            await session.execute(
                update(AlbumRecord)
                .where(AlbumRecord.id == album_id)
                .values(asset_count=int(count or 0))
            )
            return int(count or 0)

    async def replace_tag_memberships(self, tag_id: UUID, asset_ids: list[UUID]) -> int:
        """Replace one tag snapshot after its complete remote traversal succeeds."""

        unique_ids = list(dict.fromkeys(asset_ids))
        async with self._database.sessions() as session, session.begin():
            if unique_ids:
                await session.execute(
                    delete(TagAssetRecord).where(
                        TagAssetRecord.tag_id == tag_id,
                        TagAssetRecord.asset_id.not_in(unique_ids),
                    )
                )
                await session.execute(
                    insert(TagAssetRecord)
                    .values([{"tag_id": tag_id, "asset_id": asset_id} for asset_id in unique_ids])
                    .on_conflict_do_nothing()
                )
            else:
                await session.execute(delete(TagAssetRecord).where(TagAssetRecord.tag_id == tag_id))
            count = await session.scalar(
                select(func.count())
                .select_from(TagAssetRecord)
                .where(TagAssetRecord.tag_id == tag_id)
            )
            await session.execute(
                update(TagRecord).where(TagRecord.id == tag_id).values(asset_count=int(count or 0))
            )
            return int(count or 0)

    async def replace_asset_tag_memberships(self, asset_id: UUID, tag_ids: list[UUID]) -> None:
        """Replace one asset's tag memberships after a complete detail/fallback read."""

        unique_ids = list(dict.fromkeys(tag_ids))
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                delete(TagAssetRecord).where(
                    TagAssetRecord.asset_id == asset_id,
                    TagAssetRecord.tag_id.not_in(unique_ids) if unique_ids else true(),
                )
            )
            if unique_ids:
                await session.execute(
                    insert(TagAssetRecord)
                    .values([{"tag_id": tag_id, "asset_id": asset_id} for tag_id in unique_ids])
                    .on_conflict_do_nothing()
                )

    async def replace_asset_album_memberships(self, asset_id: UUID, album_ids: list[UUID]) -> None:
        """Replace one asset's album memberships after a complete API read."""

        unique_ids = list(dict.fromkeys(album_ids))
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                delete(AlbumAssetRecord).where(
                    AlbumAssetRecord.asset_id == asset_id,
                    AlbumAssetRecord.album_id.not_in(unique_ids) if unique_ids else true(),
                )
            )
            if unique_ids:
                await session.execute(
                    insert(AlbumAssetRecord)
                    .values(
                        [{"album_id": album_id, "asset_id": asset_id} for album_id in unique_ids]
                    )
                    .on_conflict_do_nothing()
                )

    async def apply_stack_batch(
        self,
        stacks: list[tuple[dict[str, object], list[UUID]]],
        generation: int,
    ) -> int:
        """Apply compact stack payloads only after their asset batch exists."""

        applied = 0
        async with self._database.sessions() as session, session.begin():
            for payload, asset_ids in stacks:
                if not asset_ids:
                    continue
                already_observed = int(
                    await session.scalar(
                        select(func.count())
                        .select_from(AssetRecord)
                        .where(AssetRecord.id.in_(asset_ids))
                        .where(AssetRecord.stack_generation == generation)
                    )
                    or 0
                )
                result = await session.execute(
                    update(AssetRecord)
                    .where(AssetRecord.id.in_(asset_ids))
                    .values(stack=payload, stack_generation=generation)
                )
                applied += max(0, int(result.rowcount or 0) - already_observed)
        return applied

    async def upsert_album_memberships(
        self,
        album_id: UUID,
        asset_ids: list[UUID],
        generation: int,
    ) -> int:
        """Mark one bounded album-membership observation batch."""

        if not asset_ids:
            return 0
        async with self._database.sessions() as session:
            existing_asset_ids = set(
                (
                    await session.scalars(
                        select(AssetRecord.id).where(
                            AssetRecord.id.in_(asset_ids),
                            AssetRecord.is_trashed.is_(False),
                        )
                    )
                ).all()
            )
            already_observed = set(
                (
                    await session.scalars(
                        select(AlbumAssetRecord.asset_id).where(
                            AlbumAssetRecord.album_id == album_id,
                            AlbumAssetRecord.asset_id.in_(asset_ids),
                            AlbumAssetRecord.sync_generation == generation,
                        )
                    )
                ).all()
            )
        missing = set(asset_ids) - existing_asset_ids
        if missing:
            raise SyncValidationError(
                f"Album membership referenced {len(missing)} unsynchronized assets"
            )
        rows = [
            {"album_id": album_id, "asset_id": asset_id, "sync_generation": generation}
            for asset_id in dict.fromkeys(asset_ids)
            if asset_id in existing_asset_ids
        ]
        if not rows:
            return 0
        async with self._database.sessions() as session, session.begin():
            statement = insert(AlbumAssetRecord).values(rows)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AlbumAssetRecord.album_id, AlbumAssetRecord.asset_id],
                    set_={"sync_generation": generation},
                )
            )
        return len(rows) - len(already_observed)

    async def upsert_tag_memberships(
        self,
        tag_id: UUID,
        asset_ids: list[UUID],
        generation: int,
    ) -> int:
        """Mark one bounded tag-membership observation batch."""

        if not asset_ids:
            return 0
        async with self._database.sessions() as session:
            existing_asset_ids = set(
                (
                    await session.scalars(
                        select(AssetRecord.id).where(
                            AssetRecord.id.in_(asset_ids),
                            AssetRecord.is_trashed.is_(False),
                        )
                    )
                ).all()
            )
            already_observed = set(
                (
                    await session.scalars(
                        select(TagAssetRecord.asset_id).where(
                            TagAssetRecord.tag_id == tag_id,
                            TagAssetRecord.asset_id.in_(asset_ids),
                            TagAssetRecord.sync_generation == generation,
                        )
                    )
                ).all()
            )
        missing = set(asset_ids) - existing_asset_ids
        if missing:
            raise SyncValidationError(
                f"Tag membership referenced {len(missing)} unsynchronized assets"
            )
        rows = [
            {"tag_id": tag_id, "asset_id": asset_id, "sync_generation": generation}
            for asset_id in dict.fromkeys(asset_ids)
            if asset_id in existing_asset_ids
        ]
        if not rows:
            return 0
        async with self._database.sessions() as session, session.begin():
            statement = insert(TagAssetRecord).values(rows)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[TagAssetRecord.tag_id, TagAssetRecord.asset_id],
                    set_={"sync_generation": generation},
                )
            )
        return len(rows) - len(already_observed)

    async def refresh_relation_counts(self) -> None:
        """Derive catalog counts from the successfully reconciled memberships."""

        active_album_membership = AlbumAssetRecord.asset_id.in_(
            select(AssetRecord.id).where(AssetRecord.is_trashed.is_(False))
        )
        active_tag_membership = TagAssetRecord.asset_id.in_(
            select(AssetRecord.id).where(AssetRecord.is_trashed.is_(False))
        )
        album_count = (
            select(func.count())
            .select_from(AlbumAssetRecord)
            .where(AlbumAssetRecord.album_id == AlbumRecord.id, active_album_membership)
            .correlate(AlbumRecord)
            .scalar_subquery()
        )
        tag_count = (
            select(func.count())
            .select_from(TagAssetRecord)
            .where(TagAssetRecord.tag_id == TagRecord.id, active_tag_membership)
            .correlate(TagRecord)
            .scalar_subquery()
        )
        async with self._database.sessions() as session, session.begin():
            await session.execute(update(AlbumRecord).values(asset_count=album_count))
            await session.execute(update(TagRecord).values(asset_count=tag_count))

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

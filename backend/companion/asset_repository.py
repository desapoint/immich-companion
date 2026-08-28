"""Companion-owned asset persistence, reconciliation, and SQL search."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import (
    Float,
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
from companion.immich import ImmichAlbum, ImmichAsset, ImmichTag
from companion.models import (
    AlbumAssetRecord,
    AlbumRecord,
    AssetRecord,
    SelectionSetMemberRecord,
    SelectionSetRecord,
    TagAssetRecord,
    TagRecord,
)

ASPECT_RATIO_RELATIVE_TOLERANCE = 0.001


class SyncValidationError(RuntimeError):
    """Raised when a staged generation is incomplete before finalization."""


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
        unique_assets = {
            asset.id: asset for asset in assets if not asset.is_trashed
        }
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

    @staticmethod
    def _fingerprint(asset: ImmichAsset) -> str:
        """Hash the canonical relevant Immich payload for replay suppression."""

        payload = asset.model_dump(mode="json", by_alias=True, exclude_none=False)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()

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
                identifier: (fingerprint, previous_generation)
                for identifier, fingerprint, previous_generation in (
                    await session.execute(
                        select(
                            AssetRecord.id,
                            AssetRecord.sync_fingerprint,
                            AssetRecord.sync_generation,
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
                update_columns[name] = case(
                    (payload_changed, getattr(statement.excluded, name)),
                    else_=getattr(AssetRecord, name),
                )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[AssetRecord.id],
                    set_=update_columns,
                )
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

    async def refresh_asset(self, asset: ImmichAsset) -> None:
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
        async with self._database.sessions() as session, session.begin():
            await session.execute(
                insert(AssetRecord)
                .values(insert_values)
                .on_conflict_do_update(
                    index_elements=[AssetRecord.id],
                    set_=update_values,
                )
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

    async def get_asset_stack(
        self, asset_id: UUID
    ) -> tuple[UUID, dict[str, object]] | None:
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

        async with self._database.sessions() as session, session.begin():
            result = await session.execute(
                delete(AssetRecord).where(
                    AssetRecord.id.in_(list(dict.fromkeys(asset_ids)))
                )
            )
            return int(result.rowcount or 0)

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
                        [
                            {"album_id": album_id, "asset_id": asset_id}
                            for asset_id in unique_ids
                        ]
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
                    .values(
                        [{"tag_id": tag_id, "asset_id": asset_id} for asset_id in unique_ids]
                    )
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
                update(TagRecord)
                .where(TagRecord.id == tag_id)
                .values(asset_count=int(count or 0))
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

    async def replace_asset_album_memberships(
        self, asset_id: UUID, album_ids: list[UUID]
    ) -> None:
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
                        [
                            {"album_id": album_id, "asset_id": asset_id}
                            for album_id in unique_ids
                        ]
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
        return removed

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
                result = await session.execute(
                    delete(model).where(identifier_column.in_(identifiers))
                )
                removed += int(result.rowcount or 0)

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
            return column == int(value)
        if condition.field == "aspect_ratio":
            ratio = cast(AssetRecord.width, Float) / cast(AssetRecord.height, Float)
            numeric = float(value)
            if condition.operator == "at_least":
                return ratio >= numeric
            if condition.operator == "at_most":
                return ratio <= numeric
            return func.abs(ratio - numeric) <= numeric * ASPECT_RATIO_RELATIVE_TOLERANCE
        if condition.field in {"favorite", "archived", "trashed"}:
            column = {
                "favorite": AssetRecord.is_favorite,
                "archived": AssetRecord.is_archived,
                "trashed": AssetRecord.is_trashed,
            }[condition.field]
            return column == bool(value)
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

    async def list_matching_asset_ids(self, expression: SearchGroup) -> list[UUID]:
        """Materialize a search result as explicit IDs at selection time."""

        predicate = self._compile_group(expression)
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(AssetRecord.id)
                        .where(AssetRecord.is_trashed.is_(False), predicate)
                        .order_by(AssetRecord.id)
                    )
                ).all()
            )

    async def create_selection(self, *, ttl_seconds: int) -> SelectionSetRecord:
        """Create an empty server-owned selection set."""

        now = datetime.now(UTC)
        record = SelectionSetRecord(expires_at=now + timedelta(seconds=ttl_seconds))
        async with self._database.sessions() as session, session.begin():
            session.add(record)
            await session.flush()
        return record

    async def get_selection(self, selection_id: UUID) -> SelectionSetRecord | None:
        async with self._database.sessions() as session:
            return await session.get(SelectionSetRecord, selection_id)

    async def selection_ids(self, selection_id: UUID) -> list[UUID]:
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

    async def selection_membership(
        self, selection_id: UUID, asset_ids: list[UUID]
    ) -> list[UUID]:
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
                insert(SelectionSetMemberRecord).from_select(
                    ["selection_id", "asset_id"], source
                )
            )
            record.selected_count = int(
                await session.scalar(
                    select(func.count()).select_from(SelectionSetMemberRecord).where(
                        SelectionSetMemberRecord.selection_id == selection_id
                    )
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
            if record.status != "active" or record.expires_at <= datetime.now(UTC):
                raise ValueError("Selection set has expired")
            if record.revision != revision:
                raise ValueError("Selection set changed; reload its membership")
            if selected:
                await session.execute(
                    insert(SelectionSetMemberRecord)
                    .values([
                        {"selection_id": selection_id, "asset_id": asset_id}
                        for asset_id in asset_ids
                    ])
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
                    select(func.count()).select_from(SelectionSetMemberRecord).where(
                        SelectionSetMemberRecord.selection_id == selection_id
                    )
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
            )
        elif operation == "set_stack_primary":
            async with self._database.sessions() as session:
                rows = (
                    await session.execute(
                        select(AssetRecord.id, AssetRecord.stack).where(
                            AssetRecord.id.in_(target_ids),
                            AssetRecord.stack.is_not(None),
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

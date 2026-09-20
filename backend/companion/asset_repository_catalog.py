"""Catalog, relation, and stack persistence for synchronized assets."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    case,
    delete,
    func,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import insert

from companion.action_schema import (
    AssetActionOperation,
)
from companion.asset_repository_hydration import (
    similarity_upsert_changes,
)
from companion.immich import ImmichAlbum, ImmichAsset, ImmichTag
from companion.models import (
    AlbumAssetRecord,
    AlbumRecord,
    AssetRecord,
    TagAssetRecord,
    TagRecord,
)

ASPECT_RATIO_RELATIVE_TOLERANCE = 0.001




class SyncValidationError(RuntimeError):
    """Raised when a staged membership references an unknown asset."""


class AssetCatalogRelationMixin:
    """Persist synchronized catalogs, memberships, stacks, and relation counts."""

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

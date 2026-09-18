"""Adaptive tag-reconciliation helpers for staged synchronization."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select, update

from companion.asset_repository import AssetRepository
from companion.immich import ImmichApiClient, ImmichApiError
from companion.models import AlbumAssetRecord, AlbumRecord, AssetRecord, TagRecord


async def generation_asset_ids(repository: AssetRepository, generation: int) -> list[UUID]:
    """Return the assets observed by the current staged generation."""

    async with repository._database.sessions() as session:  # noqa: SLF001
        return list(
            (
                await session.scalars(
                    select(AssetRecord.id)
                    .where(
                        AssetRecord.sync_generation == generation,
                        AssetRecord.is_trashed.is_(False),
                    )
                    .order_by(AssetRecord.id)
                )
            ).all()
        )


async def reconcile_generation_asset_tags(
    immich: ImmichApiClient,
    repository: AssetRepository,
    asset_ids: list[UUID],
    *,
    generation: int,
    concurrency: int,
) -> tuple[int, int, int]:
    """Replace tag memberships from detailed asset payloads in bounded waves.

    Returns ``(links, payload_assets, fallback_assets)``. A 404 or a detail
    response without the explicit tags relationship requests a safe fallback
    to the existing tag-oriented traversal for the run.
    """

    links = 0
    payload_assets = 0
    fallback_assets = 0
    for start in range(0, len(asset_ids), concurrency):
        wave = asset_ids[start : start + concurrency]

        async def fetch(identifier: UUID):
            try:
                return await immich.get_asset(identifier)
            except ImmichApiError as error:
                if error.status_code == 404:
                    return None
                raise

        details = await asyncio.gather(*(fetch(identifier) for identifier in wave))
        observed_by_tag: dict[UUID, list[UUID]] = defaultdict(list)
        for detail in details:
            if detail is None or not detail.includes_tags:
                fallback_assets += 1
                continue
            tag_ids = list(
                dict.fromkeys(UUID(str(tag["id"])) for tag in detail.tags if tag.get("id"))
            )
            await repository.replace_asset_tag_memberships(detail.id, tag_ids)
            for tag_id in tag_ids:
                observed_by_tag[tag_id].append(detail.id)
            links += len(tag_ids)
            payload_assets += 1

        # Stamp each tag's generation in one bounded write instead of opening a
        # transaction and re-reading the asset generation for every individual
        # asset/tag link. This keeps staged validation authoritative while
        # reducing database round trips from O(links) to O(tags per wave).
        for tag_id, member_ids in observed_by_tag.items():
            await repository.upsert_tag_memberships(tag_id, member_ids, generation)
    return links, payload_assets, fallback_assets


async def finalize_incremental_asset_oriented_tags(
    repository: AssetRepository,
    generation: int,
    *,
    batch_size: int,
    window_start,
    window_end,
) -> dict[str, int]:
    """Finalize an incremental generation without globally pruning tag links.

    Asset-oriented reconciliation is authoritative only for assets in the
    bounded incremental window. Untouched assets intentionally retain older
    tag-membership generations, so deleting all stale tag generations here
    would corrupt their memberships.
    """

    removed = {
        "album_memberships_removed": 0,
        "tag_memberships_removed": 0,
        "albums_removed": 0,
        "tags_removed": 0,
        "stacks_cleared": 0,
        "assets_removed": 0,
    }
    removed["album_memberships_removed"] = await repository._delete_stale_memberships(  # noqa: SLF001
        AlbumAssetRecord,
        (AlbumAssetRecord.album_id, AlbumAssetRecord.asset_id),
        generation,
        batch_size,
    )
    removed["albums_removed"] = await repository._delete_stale_entities(  # noqa: SLF001
        AlbumRecord, AlbumRecord.id, AlbumRecord.sync_generation, generation, batch_size
    )
    removed["tags_removed"] = await repository._delete_stale_entities(  # noqa: SLF001
        TagRecord, TagRecord.id, TagRecord.sync_generation, generation, batch_size
    )
    while True:
        async with repository._database.sessions() as session, session.begin():  # noqa: SLF001
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
    if window_start is not None and window_end is not None:
        removed["assets_removed"] = await repository._delete_missing_assets_in_window(  # noqa: SLF001
            generation,
            window_start,
            window_end,
            batch_size,
        )
    return removed

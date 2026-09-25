"""First-class relationship synchronization and strategy components."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal
from uuid import UUID

from companion.adaptive_tag_sync import (
    reconcile_generation_asset_relations,
    reconcile_generation_asset_tags,
)
from companion.asset_repository import AssetRepository
from companion.immich import ImmichAlbum, ImmichApiClient, ImmichApiError, ImmichTag
from companion.synchronization.batching import async_items_with_last, prefetch_async
from companion.synchronization.evidence import SyncAuthority, SyncEvidence
from companion.synchronization.scopes import RelationshipScope
from companion.synchronization.selections import (
    AllSelection,
    ExplicitIdsSelection,
    GenerationSelection,
    PersistedSelection,
    RequestSelection,
    SyncSelectionResolver,
    WindowSelection,
)
from companion.synchronization.steps import (
    SyncStep,
    SyncStepContext,
    SyncStepProgress,
    SyncStepResult,
)

type ChosenRelationshipStrategy = Literal["by_asset", "by_relation"]


@dataclass(frozen=True, slots=True)
class AssetRelationshipOutcome:
    association_completed: int
    tag_fallback_assets: int


class RelationshipStrategySelector:
    """Choose the current relationship strategy without changing its cost model."""

    def __init__(self, assets: AssetRepository) -> None:
        self._assets = assets

    async def choose(
        self,
        scope: RelationshipScope,
        *,
        asset_ids: list[UUID],
        albums: list[ImmichAlbum],
        tags: list[ImmichTag],
        page_size: int,
        resuming_relation_traversal: bool,
    ) -> ChosenRelationshipStrategy:
        if resuming_relation_traversal:
            return "by_relation"
        if scope.strategy == "by_asset":
            return "by_asset"
        if scope.strategy == "by_relation":
            return "by_relation"
        if not asset_ids:
            return "by_asset"

        tag_counts = await self._assets.tag_asset_counts()
        relation_requests = 0
        if "albums" in scope.kinds:
            relation_requests += sum(
                max(1, (album.asset_count + page_size - 1) // page_size)
                for album in albums
            )
        if "tags" in scope.kinds:
            relation_requests += sum(
                max(1, (tag_counts.get(tag.id, 0) + page_size - 1) // page_size)
                for tag in tags
            )
        return "by_asset" if len(asset_ids) * 2 <= relation_requests else "by_relation"


class AssetRelationshipStrategy:
    """Reconcile selected assets while retaining the current tag fallback behavior."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        selections: SyncSelectionResolver,
        *,
        metadata_concurrency: int,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._selections = selections
        self._metadata_concurrency = metadata_concurrency

    async def execute(
        self,
        context: SyncStepContext,
        scope: RelationshipScope,
        *,
        resolved_asset_ids: list[UUID] | None = None,
    ) -> AssetRelationshipOutcome:
        if scope.assets is None:
            raise ValueError("Asset-oriented relationship synchronization requires assets")
        if isinstance(scope.assets, (AllSelection, WindowSelection)):
            raise ValueError(
                "Asset-oriented relationships require explicit, persisted, request, "
                "or generation-selected assets"
            )

        association_completed = 0
        fallback_assets = 0
        if resolved_asset_ids is not None:
            batches = [resolved_asset_ids]
        else:
            batches = self._selections.iter_asset_ids(
                scope.assets,
                batch_size=context.config.batch_size or 1,
            )

        if isinstance(batches, list):
            for asset_ids in batches:
                completed, fallback = await self._execute_batch(
                    context,
                    scope,
                    asset_ids,
                )
                association_completed += completed
                fallback_assets += fallback
        else:
            async for asset_ids in batches:
                completed, fallback = await self._execute_batch(
                    context,
                    scope,
                    asset_ids,
                )
                association_completed += completed
                fallback_assets += fallback

        return AssetRelationshipOutcome(association_completed, fallback_assets)

    async def _execute_batch(
        self,
        context: SyncStepContext,
        scope: RelationshipScope,
        asset_ids: list[UUID],
    ) -> tuple[int, int]:
        if "albums" in scope.kinds and "tags" in scope.kinds:
            result = await reconcile_generation_asset_relations(
                self._immich,
                self._assets,
                asset_ids,
                generation=context.generation,
                concurrency=self._metadata_concurrency,
            )
            context.counters["album_memberships"] += result.album_links
            context.counters["tag_memberships"] += result.tag_links
            context.counters["tag_asset_detail_payload"] += result.payload_assets
            context.counters["tag_asset_detail_fallback"] += result.tag_fallback_assets
            return result.album_links + result.tag_links, result.tag_fallback_assets

        if "tags" in scope.kinds:
            links, payload_assets, fallback_assets = await reconcile_generation_asset_tags(
                self._immich,
                self._assets,
                asset_ids,
                generation=context.generation,
                concurrency=self._metadata_concurrency,
            )
            context.counters["tag_memberships"] += links
            context.counters["tag_asset_detail_payload"] += payload_assets
            context.counters["tag_asset_detail_fallback"] += fallback_assets
            return links, fallback_assets

        album_links = await self._reconcile_album_relationships(context, asset_ids)
        context.counters["album_memberships"] += album_links
        return album_links, 0

    async def _reconcile_album_relationships(
        self,
        context: SyncStepContext,
        asset_ids: list[UUID],
    ) -> int:
        links = 0
        for start in range(0, len(asset_ids), self._metadata_concurrency):
            wave = asset_ids[start : start + self._metadata_concurrency]

            async def fetch(identifier: UUID):
                try:
                    return identifier, await self._immich.list_albums_for_asset(identifier)
                except ImmichApiError as error:
                    if error.status_code == 404:
                        return identifier, None
                    raise

            resolved = await asyncio.gather(*(fetch(identifier) for identifier in wave))
            observed_by_album: dict[UUID, list[UUID]] = defaultdict(list)
            replacements: list[tuple[UUID, list[UUID]]] = []
            for asset_id, albums in resolved:
                if albums is None:
                    continue
                album_ids = list(dict.fromkeys(album.id for album in albums))
                replacements.append((asset_id, album_ids))
                links += len(album_ids)
                for album_id in album_ids:
                    observed_by_album[album_id].append(asset_id)

            await asyncio.gather(
                *(
                    self._assets.replace_asset_album_memberships(asset_id, album_ids)
                    for asset_id, album_ids in replacements
                )
            )
            for album_id, member_ids in observed_by_album.items():
                await self._assets.upsert_album_memberships(
                    album_id,
                    member_ids,
                    context.generation,
                )
        return links


class RelationTraversalStrategy:
    """Traverse album/tag relations with current paging, concurrency, and pacing."""

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        *,
        page_prefetch: int,
        pace_callback: Callable[[SyncStepContext, float], Awaitable[None]],
        checkpoint_callback: Callable[[str | None, int, str], Awaitable[None]],
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._page_prefetch = page_prefetch
        self._pace_callback = pace_callback
        self._checkpoint_callback = checkpoint_callback

    async def execute(
        self,
        context: SyncStepContext,
        *,
        kinds: set[str],
        albums: list[ImmichAlbum],
        tags: list[ImmichTag],
        relation_kind: str,
        completed_relation: int,
        completed_page: int,
        association_completed: int,
    ) -> int:
        if context.config.page_size is None:
            raise ValueError("RelationshipSyncStep requires config.page_size")
        relation_concurrency = context.config.concurrency
        page_size = context.config.page_size

        if "albums" in kinds and relation_kind != "tags":
            album_start = 0
            resume_page = 1
            if relation_kind == "albums":
                album_start = (
                    max(0, completed_relation - 1)
                    if completed_page
                    else completed_relation
                )
                resume_page = completed_page + 1 if completed_page else 1
            for wave_start in range(album_start, len(albums), relation_concurrency):
                wave = albums[wave_start : wave_start + relation_concurrency]
                tasks: list[asyncio.Task[tuple[int, int]]] = []
                async with asyncio.TaskGroup() as group:
                    tasks = [
                        group.create_task(
                            self._sync_album(
                                context,
                                album,
                                start_page=(
                                    resume_page
                                    if wave_start == album_start and index == 0
                                    else 1
                                ),
                                page_size=page_size,
                            )
                        )
                        for index, album in enumerate(wave)
                    ]
                results = [task.result() for task in tasks]
                context.counters["album_memberships"] += sum(
                    result[0] for result in results
                )
                association_completed += sum(result[1] for result in results)
                completed_albums = wave_start + len(wave)
                await self._checkpoint_callback(
                    f"albums:{completed_albums}:0",
                    association_completed,
                    f"Album associations {completed_albums}/{len(albums)}",
                )

        if "tags" not in kinds:
            return association_completed

        skipped_tags = 0
        tag_start = 0
        if relation_kind == "tags":
            tag_start = (
                completed_relation
                if completed_page == 0
                else max(0, completed_relation - 1)
            )
        for wave_start in range(tag_start, len(tags), relation_concurrency):
            wave = tags[wave_start : wave_start + relation_concurrency]
            tasks: list[asyncio.Task[tuple[int, int, bool]]] = []
            async with asyncio.TaskGroup() as group:
                tasks = [
                    group.create_task(
                        self._sync_tag(
                            context,
                            tag,
                            page_size=page_size,
                        )
                    )
                    for tag in wave
                ]
            results = [task.result() for task in tasks]
            context.counters["tag_memberships"] += sum(result[0] for result in results)
            association_completed += sum(result[1] for result in results)
            empty_tags = sum(result[2] for result in results)
            skipped_tags += empty_tags
            context.counters["tag_relationships_scanned"] += len(wave)
            context.counters["tag_empty_relationships"] += empty_tags
            completed_tags = wave_start + len(wave)
            await self._checkpoint_callback(
                f"tags:{completed_tags}:0",
                association_completed,
                f"Tag associations {completed_tags}/{len(tags)}"
                + (f" · skipped {skipped_tags} empty" if skipped_tags else ""),
            )
        return association_completed

    async def _sync_album(
        self,
        context: SyncStepContext,
        album: ImmichAlbum,
        *,
        start_page: int,
        page_size: int,
    ) -> tuple[int, int]:
        persisted = 0
        observed = 0
        pages = prefetch_async(
            self._immich.iter_album_asset_ids(
                album.id,
                page_size=page_size,
                start_page=start_page,
            ),
            self._page_prefetch,
        )
        async for asset_ids, is_last_page in async_items_with_last(pages):
            started = perf_counter()
            if asset_ids:
                persisted += await self._assets.upsert_album_memberships(
                    album.id,
                    asset_ids,
                    context.generation,
                )
            observed += len(asset_ids)
            if not is_last_page:
                await self._pace_callback(context, started)
        return persisted, observed

    async def _sync_tag(
        self,
        context: SyncStepContext,
        tag: ImmichTag,
        *,
        page_size: int,
    ) -> tuple[int, int, bool]:
        persisted = 0
        observed = 0
        pages = prefetch_async(
            self._immich.iter_tag_asset_ids(
                tag.id,
                page_size=page_size,
                start_page=1,
            ),
            self._page_prefetch,
        )
        async for asset_ids, is_last_page in async_items_with_last(pages):
            started = perf_counter()
            if asset_ids:
                persisted += await self._assets.upsert_tag_memberships(
                    tag.id,
                    asset_ids,
                    context.generation,
                )
            observed += len(asset_ids)
            if not is_last_page:
                await self._pace_callback(context, started)
        return persisted, observed, observed == 0


class RelationshipSyncStep(SyncStep[RelationshipScope]):
    """Synchronize album/tag relationships through explicit strategy components."""

    name = "relationships"
    phase = "relationships"

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        selections: SyncSelectionResolver,
        *,
        page_prefetch: int = 0,
        metadata_concurrency: int = 1,
    ) -> None:
        if page_prefetch < 0:
            raise ValueError("page_prefetch cannot be negative")
        if metadata_concurrency < 1:
            raise ValueError("metadata_concurrency must be at least 1")
        self._immich = immich
        self._assets = assets
        self._selections = selections
        self._page_prefetch = page_prefetch
        self._metadata_concurrency = metadata_concurrency
        self._selector = RelationshipStrategySelector(assets)

    async def run(
        self,
        context: SyncStepContext,
        scope: RelationshipScope,
    ) -> SyncStepResult:
        if not self.should_run(context):
            return SyncStepResult(
                name=self.name,
                phase=self.phase,
                skipped=True,
                completed=0,
                total=None,
                counters=dict(context.counters),
            )

        completed, evidence, outputs = await self._execute_relationship(context, scope)
        return SyncStepResult(
            name=self.name,
            phase=self.phase,
            skipped=False,
            completed=completed,
            total=None,
            counters=dict(context.counters),
            evidence=evidence,
            outputs=outputs,
        )

    async def execute(
        self,
        context: SyncStepContext,
        scope: RelationshipScope,
    ) -> tuple[int, None]:
        completed, _evidence, _outputs = await self._execute_relationship(context, scope)
        return completed, None

    async def _execute_relationship(
        self,
        context: SyncStepContext,
        scope: RelationshipScope,
    ) -> tuple[int, list[SyncEvidence], dict[str, object]]:
        if context.config.batch_size is None:
            raise ValueError("RelationshipSyncStep requires config.batch_size")
        if context.config.page_size is None:
            raise ValueError("RelationshipSyncStep requires config.page_size")

        for counter in (
            "album_memberships",
            "tag_memberships",
            "tag_relationships_scanned",
            "tag_empty_relationships",
            "tag_asset_detail_payload",
            "tag_asset_detail_fallback",
            "album_strategy_asset_oriented",
            "tag_strategy_asset_oriented",
            "tag_strategy_asset_fallback",
        ):
            context.counters.setdefault(counter, 0)
        context.counters["tag_association_concurrency"] = context.config.concurrency

        relation_kind = ""
        completed_relation = 0
        completed_page = 0
        if context.cursor:
            relation_kind, relation_text, page_text = context.cursor.split(":", 2)
            completed_relation = int(relation_text)
            completed_page = int(page_text)

        album_selection = scope.albums
        tag_selection = scope.tags
        if scope.strategy == "automatic":
            if "albums" in scope.kinds and album_selection is None:
                album_selection = AllSelection()
            if "tags" in scope.kinds and tag_selection is None:
                tag_selection = AllSelection()

        albums, tags = await asyncio.gather(
            self._load_albums(
                album_selection,
                batch_size=context.config.batch_size,
            )
            if "albums" in scope.kinds
            else self._empty_albums(),
            self._load_tags(
                tag_selection,
                batch_size=context.config.batch_size,
            )
            if "tags" in scope.kinds
            else self._empty_tags(),
        )

        association_completed = context.counters["album_memberships"] + context.counters[
            "tag_memberships"
        ]
        await self._checkpoint(
            context,
            context.cursor,
            association_completed,
            f"Preparing {len(albums)} album and {len(tags)} tag associations",
        )

        target_ids: list[UUID] = []
        if scope.strategy == "automatic" and not relation_kind and scope.assets is not None:
            target_ids = await self._resolve_asset_ids(
                scope.assets,
                batch_size=context.config.batch_size,
            )

        chosen = await self._selector.choose(
            scope,
            asset_ids=target_ids,
            albums=albums,
            tags=tags,
            page_size=context.config.page_size,
            resuming_relation_traversal=bool(relation_kind),
        )
        use_asset = chosen == "by_asset"
        context.counters["album_strategy_asset_oriented"] = (
            1 if use_asset and "albums" in scope.kinds else 0
        )
        context.counters["tag_strategy_asset_oriented"] = (
            1 if use_asset and "tags" in scope.kinds else 0
        )
        context.counters["tag_strategy_asset_fallback"] = 0

        evidence: list[SyncEvidence] = []
        tag_fallback = False
        if use_asset:
            asset_strategy = AssetRelationshipStrategy(
                self._immich,
                self._assets,
                self._selections,
                metadata_concurrency=(
                    context.config.metadata_concurrency
                    if context.config.metadata_concurrency is not None
                    else self._metadata_concurrency
                ),
            )
            outcome = await asset_strategy.execute(
                context,
                scope,
                resolved_asset_ids=target_ids if scope.strategy == "automatic" else None,
            )
            association_completed += outcome.association_completed
            tag_fallback = "tags" in scope.kinds and outcome.tag_fallback_assets > 0
            if "albums" in scope.kinds:
                evidence.append(
                    self._selected_evidence(
                        "album_memberships",
                        scope.assets,
                        context.generation,
                    )
                )
            if "tags" in scope.kinds and not tag_fallback:
                evidence.append(
                    self._selected_evidence(
                        "tag_memberships",
                        scope.assets,
                        context.generation,
                    )
                )
            if not tag_fallback:
                await self._checkpoint(
                    context,
                    None,
                    association_completed,
                    (
                        f"Associations complete · "
                        f"{context.counters['album_memberships']} album links · "
                        f"{context.counters['tag_memberships']} tag links · "
                        "changed-asset strategy"
                    ),
                )
                return association_completed, evidence, {
                    "strategy": chosen,
                    "tag_fallback": False,
                }
            context.counters["tag_strategy_asset_fallback"] = 1
            if not isinstance(tag_selection, AllSelection):
                tag_selection = AllSelection()
                tags = await self._load_tags(
                    tag_selection,
                    batch_size=context.config.batch_size,
                )

        relation_kinds = {"tags"} if use_asset and tag_fallback else set(scope.kinds)
        traversal = RelationTraversalStrategy(
            self._immich,
            self._assets,
            page_prefetch=(
                context.config.page_prefetch
                if context.config.page_prefetch is not None
                else self._page_prefetch
            ),
            pace_callback=self.pace,
            checkpoint_callback=lambda cursor, completed, detail: self._checkpoint(
                context,
                cursor,
                completed,
                detail,
            ),
        )
        association_completed = await traversal.execute(
            context,
            kinds=relation_kinds,
            albums=albums,
            tags=tags,
            relation_kind=relation_kind,
            completed_relation=completed_relation,
            completed_page=completed_page,
            association_completed=association_completed,
        )

        if "albums" in relation_kinds:
            evidence.append(
                self._relation_evidence(
                    "album_memberships",
                    album_selection or AllSelection(),
                    context.generation,
                )
            )
        if "tags" in relation_kinds:
            evidence = [
                item for item in evidence if item.domain != "tag_memberships"
            ]
            evidence.append(
                self._relation_evidence(
                    "tag_memberships",
                    tag_selection or AllSelection(),
                    context.generation,
                )
            )

        await self._checkpoint(
            context,
            None,
            association_completed,
            (
                f"Associations complete · "
                f"{context.counters['album_memberships']} album links · "
                f"{context.counters['tag_memberships']} tag links"
            ),
        )
        return association_completed, evidence, {
            "strategy": chosen,
            "tag_fallback": tag_fallback,
        }

    async def _load_albums(
        self,
        selection: object | None,
        *,
        batch_size: int,
    ) -> list[ImmichAlbum]:
        if selection is None:
            return []
        catalog = await self._immich.list_album_catalog()
        if isinstance(selection, AllSelection):
            return catalog
        selected = await self._relation_ids(
            selection,
            kind="album",
            batch_size=batch_size,
        )
        return [album for album in catalog if album.id in selected]

    async def _load_tags(
        self,
        selection: object | None,
        *,
        batch_size: int,
    ) -> list[ImmichTag]:
        if selection is None:
            return []
        catalog = await self._immich.list_tag_catalog()
        if isinstance(selection, AllSelection):
            return catalog
        selected = await self._relation_ids(
            selection,
            kind="tag",
            batch_size=batch_size,
        )
        return [tag for tag in catalog if tag.id in selected]

    async def _relation_ids(
        self,
        selection: object,
        *,
        kind: Literal["album", "tag"],
        batch_size: int,
    ) -> set[UUID]:
        if isinstance(selection, ExplicitIdsSelection):
            return set(dict.fromkeys(selection.ids))
        if not isinstance(selection, PersistedSelection):
            raise TypeError(f"Unsupported {kind} relationship selection")
        ids: set[UUID] = set()
        iterator = (
            self._selections.iter_album_ids(selection, batch_size=batch_size)
            if kind == "album"
            else self._selections.iter_tag_ids(selection, batch_size=batch_size)
        )
        async for batch in iterator:
            ids.update(batch)
        return ids

    async def _resolve_asset_ids(
        self,
        selection: object,
        *,
        batch_size: int,
    ) -> list[UUID]:
        if isinstance(selection, (AllSelection, WindowSelection)):
            raise ValueError(
                "Automatic relationship selection requires a local selected-asset source"
            )
        if not isinstance(
            selection,
            (
                ExplicitIdsSelection,
                PersistedSelection,
                RequestSelection,
                GenerationSelection,
            ),
        ):
            raise TypeError("Unsupported relationship asset selection")
        return [
            asset_id
            async for batch in self._selections.iter_asset_ids(
                selection,
                batch_size=batch_size,
            )
            for asset_id in batch
        ]

    @staticmethod
    async def _empty_albums() -> list[ImmichAlbum]:
        return []

    @staticmethod
    async def _empty_tags() -> list[ImmichTag]:
        return []

    @staticmethod
    def _selected_evidence(
        domain: Literal["album_memberships", "tag_memberships"],
        selection: object | None,
        generation: int,
    ) -> SyncEvidence:
        if not isinstance(
            selection,
            (
                ExplicitIdsSelection,
                PersistedSelection,
                RequestSelection,
                GenerationSelection,
            ),
        ):
            raise ValueError("Selected relationship evidence requires selected assets")
        return SyncEvidence(
            domain=domain,
            authority=SyncAuthority.SELECTED,
            selection=selection,
            generation=generation,
        )

    @staticmethod
    def _relation_evidence(
        domain: Literal["album_memberships", "tag_memberships"],
        selection: object,
        generation: int,
    ) -> SyncEvidence:
        if isinstance(selection, AllSelection):
            return SyncEvidence(
                domain=domain,
                authority=SyncAuthority.COMPLETE,
                selection=selection,
                generation=generation,
            )
        if isinstance(selection, (ExplicitIdsSelection, PersistedSelection)):
            return SyncEvidence(
                domain=domain,
                authority=SyncAuthority.SELECTED,
                selection=selection,
                generation=generation,
            )
        raise TypeError("Unsupported relationship evidence selection")

    async def pace(self, context: SyncStepContext, started: float) -> None:
        """Pace relation pages according to the run-specific operational config."""

        await super().pace(context, started)

    async def _checkpoint(
        self,
        context: SyncStepContext,
        cursor: str | None,
        completed: int,
        detail: str,
    ) -> None:
        context.cursor = cursor
        await context.checkpoint_callback(
            cursor,
            context.counters,
            SyncStepProgress(
                phase=self.phase,
                completed=completed,
                total=None,
                detail=detail,
            ),
        )


__all__ = [
    "AssetRelationshipStrategy",
    "RelationTraversalStrategy",
    "RelationshipStrategySelector",
    "RelationshipSyncStep",
]

"""Database-backed provider for the published composite duplicate projection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from companion.composite_duplicate_repository import (
    CompositeDuplicateGroupIdentity,
    CompositeDuplicateSnapshotGroup,
    CompositeDuplicateSnapshotPage,
)
from companion.discovery.base import DiscoveredGroup
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset

logger = logging.getLogger("uvicorn.error")


class _CompositeSnapshotReader(Protocol):
    async def groups(self) -> list[CompositeDuplicateSnapshotGroup]: ...

    async def groups_by_ids(
        self, group_ids: list[str]
    ) -> list[CompositeDuplicateSnapshotGroup]: ...

    async def identities(
        self,
        *,
        group_ids: list[str] | None = None,
        stable_group_keys: list[str] | None = None,
    ) -> list[CompositeDuplicateGroupIdentity]: ...

    async def matching_group_ids(
        self,
        *,
        source: DiscoverySource | None = None,
        state: str = "all",
        limit: int = 5_001,
    ) -> list[str]: ...

    async def page(
        self,
        *,
        page: int,
        page_size: int,
        source: DiscoverySource | None = None,
        sort: str = "reclaimable",
        direction: str = "desc",
        state: str = "all",
        group_ids: list[str] | None = None,
    ) -> CompositeDuplicateSnapshotPage: ...


class _AssetReader(Protocol):
    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]: ...


@dataclass(frozen=True, slots=True)
class DiscoveredGroupPage:
    groups: list[DiscoveredGroup]
    total: int
    page: int
    page_size: int
    pages: int


class PersistedCompositeDuplicateProvider:
    """Hydrate the last published provider-neutral duplicate snapshot from local data."""

    def __init__(self, snapshots: _CompositeSnapshotReader, assets: _AssetReader) -> None:
        self._snapshots = snapshots
        self._assets = assets

    async def _hydrate(
        self, snapshot: list[CompositeDuplicateSnapshotGroup]
    ) -> list[DiscoveredGroup]:
        asset_ids = list(
            dict.fromkeys(asset_id for group in snapshot for asset_id in group.asset_ids)
        )
        assets = await self._assets.get_immich_assets(asset_ids)
        discovered: list[DiscoveredGroup] = []
        for group in snapshot:
            group_assets = tuple(
                assets[asset_id] for asset_id in group.asset_ids if asset_id in assets
            )
            if len(group_assets) != len(group.asset_ids):
                logger.warning(
                    "Skipping persisted composite duplicate group %s because %s/%s local "
                    "members are available",
                    group.group_id,
                    len(group_assets),
                    len(group.asset_ids),
                )
                continue
            if any(asset.asset_type == "VIDEO" for asset in group_assets):
                logger.warning(
                    "Skipping persisted composite duplicate group %s because it contains video",
                    group.group_id,
                )
                continue
            discovered.append(
                DiscoveredGroup(
                    group_id=group.group_id,
                    discovery_source=group.discovery_source,
                    provider_group_id=group.provider_group_id,
                    assets=group_assets,
                    provider_metadata=group.provider_metadata,
                    discovery_evidence=group.evidence,
                    similarity_validation=group.similarity_validation,
                )
            )
        return discovered

    async def resolve_identities(
        self,
        *,
        group_ids: list[str] | None = None,
        stable_group_keys: list[str] | None = None,
    ) -> list[CompositeDuplicateGroupIdentity]:
        return await self._snapshots.identities(
            group_ids=group_ids,
            stable_group_keys=stable_group_keys,
        )

    async def discover_groups(self, group_ids: list[str]) -> list[DiscoveredGroup]:
        return await self._hydrate(await self._snapshots.groups_by_ids(group_ids))

    async def discover(self) -> list[DiscoveredGroup]:
        return await self._hydrate(await self._snapshots.groups())

    async def resolve_matching_group_ids(
        self,
        *,
        source: str = "both",
        state: str = "all",
        limit: int = 5_001,
    ) -> list[str]:
        source_value = (
            DiscoverySource.IMMICH_DUPLICATE
            if source == "immich"
            else DiscoverySource.COMPANION_SIMILARITY
            if source == "similarity"
            else None
        )
        return await self._snapshots.matching_group_ids(
            source=source_value,
            state=state,
            limit=limit,
        )

    async def discover_page(
        self,
        *,
        page: int,
        page_size: int,
        source: str = "both",
        sort: str = "reclaimable",
        direction: str = "desc",
        state: str = "all",
    ) -> DiscoveredGroupPage:
        source_value = (
            DiscoverySource.IMMICH_DUPLICATE
            if source == "immich"
            else DiscoverySource.COMPANION_SIMILARITY
            if source == "similarity"
            else None
        )
        snapshot = await self._snapshots.page(
            page=page,
            page_size=page_size,
            source=source_value,
            sort=sort,
            direction=direction,
            state=state,
            group_ids=None,
        )
        return DiscoveredGroupPage(
            groups=await self._hydrate(snapshot.groups),
            total=snapshot.total,
            page=snapshot.page,
            page_size=snapshot.page_size,
            pages=snapshot.pages,
        )

    async def discover_selected_page(
        self,
        group_ids: list[str],
        *,
        page: int,
        page_size: int,
        source: str = "both",
        sort: str = "reclaimable",
        direction: str = "desc",
    ) -> DiscoveredGroupPage:
        """Page only persisted selected groups before member hydration."""

        source_value = (
            DiscoverySource.IMMICH_DUPLICATE
            if source == "immich"
            else DiscoverySource.COMPANION_SIMILARITY
            if source == "similarity"
            else None
        )
        snapshot = await self._snapshots.page(
            page=page,
            page_size=page_size,
            source=source_value,
            sort=sort,
            direction=direction,
            state="all",
            group_ids=group_ids,
        )
        return DiscoveredGroupPage(
            groups=await self._hydrate(snapshot.groups),
            total=snapshot.total,
            page=snapshot.page,
            page_size=snapshot.page_size,
            pages=snapshot.pages,
        )

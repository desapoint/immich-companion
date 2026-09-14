"""Database-backed provider for the published composite duplicate projection."""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID

from companion.composite_duplicate_repository import CompositeDuplicateSnapshotGroup
from companion.discovery.base import DiscoveredGroup
from companion.immich import ImmichAsset

logger = logging.getLogger("uvicorn.error")


class _CompositeSnapshotReader(Protocol):
    async def groups(self) -> list[CompositeDuplicateSnapshotGroup]: ...


class _AssetReader(Protocol):
    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]: ...


class PersistedCompositeDuplicateProvider:
    """Hydrate the last published provider-neutral duplicate snapshot from local data."""

    def __init__(self, snapshots: _CompositeSnapshotReader, assets: _AssetReader) -> None:
        self._snapshots = snapshots
        self._assets = assets

    async def discover(self) -> list[DiscoveredGroup]:
        snapshot = await self._snapshots.groups()
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

"""Database-backed Immich duplicate-group discovery provider."""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.immich_duplicate_repository import ImmichDuplicateSnapshotGroup

logger = logging.getLogger("uvicorn.error")


class _AssetReader(Protocol):
    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]: ...


class _DuplicateSnapshotReader(Protocol):
    async def groups(self) -> list[ImmichDuplicateSnapshotGroup]: ...


class ImmichDuplicateProvider:
    """Adapt the last published Immich duplicate snapshot to discovery groups."""

    def __init__(self, snapshots: _DuplicateSnapshotReader, assets: _AssetReader) -> None:
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
                    "Skipping persisted Immich duplicate group %s because "
                    "%s/%s local members are available",
                    group.provider_group_id,
                    len(group_assets),
                    len(group.asset_ids),
                )
                continue
            discovered.append(
                DiscoveredGroup(
                    group_id=f"immich:{group.provider_group_id}",
                    discovery_source=DiscoverySource.IMMICH_DUPLICATE,
                    provider_group_id=group.provider_group_id,
                    assets=group_assets,
                    provider_metadata={
                        "endpoint": "/api/duplicates",
                        "source": "companion_database",
                    },
                )
            )
        return discovered

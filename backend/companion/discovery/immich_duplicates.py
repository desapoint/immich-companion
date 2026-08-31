"""Immich API duplicate-group discovery provider."""

from __future__ import annotations

from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.group_decision import DiscoverySource
from companion.immich import ImmichApiClient, ImmichAsset


class ImmichDuplicateProvider:
    """Adapt live Immich duplicate groups to provider-neutral snapshots."""

    def __init__(self, immich: ImmichApiClient) -> None:
        self._immich = immich

    async def discover(self) -> list[DiscoveredGroup]:
        groups = await self._immich.list_duplicate_groups()
        hydrated: dict[UUID, ImmichAsset] = {}
        discovered: list[DiscoveredGroup] = []
        for group in groups:
            assets: list[ImmichAsset] = []
            for asset in group.assets:
                if asset.library_id is not None and asset.file_size_bytes is None:
                    if asset.id not in hydrated:
                        hydrated[asset.id] = await self._immich.get_asset(asset.id)
                    asset = hydrated[asset.id]
                assets.append(asset)
            provider_id = str(group.duplicate_id)
            discovered.append(
                DiscoveredGroup(
                    # Preserve the established public/internal key while the
                    # provider ID is migrated out of compatibility requests.
                    group_id=f"immich:{provider_id}",
                    discovery_source=DiscoverySource.IMMICH_DUPLICATE,
                    provider_group_id=provider_id,
                    assets=tuple(assets),
                    provider_metadata={"endpoint": "/api/duplicates"},
                )
            )
        return discovered

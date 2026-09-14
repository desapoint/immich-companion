"""Immich API duplicate-group discovery provider."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.group_decision import DiscoverySource
from companion.immich import ImmichApiClient, ImmichAsset


class _AssetReader(Protocol):
    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]: ...


LOCAL_HYDRATION_BATCH_SIZE = 1_000
LIVE_HYDRATION_BATCH_SIZE = 16
LIVE_HYDRATION_CONCURRENCY = 2


class ImmichDuplicateProvider:
    """Adapt live Immich duplicate groups to provider-neutral snapshots."""

    def __init__(
        self, immich: ImmichApiClient, assets: _AssetReader | None = None
    ) -> None:
        self._immich = immich
        self._assets = assets

    async def discover(self) -> list[DiscoveredGroup]:
        groups = await self._immich.list_duplicate_groups()
        hydrated: dict[UUID, ImmichAsset] = {}
        local_sizes: dict[UUID, int] = {}
        sparse: dict[UUID, list[ImmichAsset]] = {}
        for group in groups:
            for asset in group.assets:
                if asset.library_id is not None and asset.file_size_bytes is None:
                    sparse.setdefault(asset.id, []).append(asset)
        if self._assets is not None:
            sparse_ids = list(sparse)
            for offset in range(0, len(sparse_ids), LOCAL_HYDRATION_BATCH_SIZE):
                local = await self._assets.get_immich_assets(
                    sparse_ids[offset : offset + LOCAL_HYDRATION_BATCH_SIZE]
                )
                for asset_id, source in local.items():
                    if (
                        source.file_size_bytes is not None
                        and all(
                            source.file_modified_at == asset.file_modified_at
                            and (asset.checksum is None or asset.checksum == source.checksum)
                            for asset in sparse[asset_id]
                        )
                    ):
                        local_sizes[asset_id] = source.file_size_bytes
        unresolved = [asset_id for asset_id in sparse if asset_id not in local_sizes]
        slots = asyncio.Semaphore(LIVE_HYDRATION_CONCURRENCY)

        async def fetch_live(asset_id: UUID) -> tuple[UUID, ImmichAsset]:
            async with slots:
                return asset_id, await self._immich.get_asset(asset_id)

        for offset in range(0, len(unresolved), LIVE_HYDRATION_BATCH_SIZE):
            hydrated.update(
                await asyncio.gather(
                    *(fetch_live(asset_id) for asset_id in unresolved[
                        offset : offset + LIVE_HYDRATION_BATCH_SIZE
                    ])
                )
            )
        discovered: list[DiscoveredGroup] = []
        for group in groups:
            assets: list[ImmichAsset] = []
            for asset in group.assets:
                if asset.library_id is not None and asset.file_size_bytes is None:
                    if asset.id in local_sizes:
                        asset = asset.model_copy(
                            update={
                                "exif_info": {
                                    **(asset.exif_info or {}),
                                    "fileSizeInByte": local_sizes[asset.id],
                                }
                            }
                        )
                    else:
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

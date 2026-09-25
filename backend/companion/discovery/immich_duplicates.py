"""Immich duplicate discovery from a persisted snapshot with a legacy live fallback."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Protocol, cast
from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset, ImmichDuplicateGroup
from companion.immich_duplicate_repository import ImmichDuplicateSnapshotGroup

logger = logging.getLogger("uvicorn.error")

LOCAL_HYDRATION_BATCH_SIZE = 1_000
PERSISTED_GROUP_BATCH_SIZE = 250
LIVE_HYDRATION_BATCH_SIZE = 16
LIVE_HYDRATION_CONCURRENCY = 2


class _AssetReader(Protocol):
    async def get_immich_assets(self, asset_ids: list[UUID]) -> dict[UUID, ImmichAsset]: ...


class _DuplicateSnapshotReader(Protocol):
    async def groups(self) -> list[ImmichDuplicateSnapshotGroup]: ...


class _LiveDuplicateReader(Protocol):
    async def list_duplicate_groups(self) -> list[ImmichDuplicateGroup]: ...

    async def get_asset(self, asset_id: UUID) -> ImmichAsset: ...


class ImmichDuplicateProvider:
    """Adapt the persisted Immich snapshot; retain live fallback for legacy callers."""

    def __init__(
        self,
        source: _DuplicateSnapshotReader | _LiveDuplicateReader,
        assets: _AssetReader | None = None,
    ) -> None:
        if hasattr(source, "groups"):
            if assets is None:
                raise TypeError("Database-backed Immich duplicate discovery requires assets")
            self._snapshots = cast(_DuplicateSnapshotReader, source)
            self._immich: _LiveDuplicateReader | None = None
        else:
            self._snapshots = None
            self._immich = cast(_LiveDuplicateReader, source)
        self._assets = assets

    async def discover(self) -> list[DiscoveredGroup]:
        groups: list[DiscoveredGroup] = []
        async for batch in self.discover_batches():
            groups.extend(batch)
        return groups

    async def discover_batches(
        self,
        *,
        batch_size: int = PERSISTED_GROUP_BATCH_SIZE,
    ) -> AsyncIterator[list[DiscoveredGroup]]:
        """Yield persisted groups with only one hydration batch resident at a time."""

        batch_size = max(1, min(batch_size, 1_000))
        if self._snapshots is None:
            groups = await self._discover_live()
            for offset in range(0, len(groups), batch_size):
                yield groups[offset : offset + batch_size]
            return

        page_reader = getattr(self._snapshots, "groups_page", None)
        if not callable(page_reader):
            groups = await self._discover_persisted()
            for offset in range(0, len(groups), batch_size):
                yield groups[offset : offset + batch_size]
            return

        cursor: str | None = None
        while True:
            snapshot, cursor = await page_reader(
                after_provider_group_id=cursor,
                limit=batch_size,
            )
            if snapshot:
                yield await self._hydrate_persisted(snapshot)
            if cursor is None:
                return

    async def _hydrate_persisted(
        self,
        snapshot: list[ImmichDuplicateSnapshotGroup],
    ) -> list[DiscoveredGroup]:
        assert self._assets is not None
        asset_ids = list(
            dict.fromkeys(asset_id for group in snapshot for asset_id in group.asset_ids)
        )
        assets = await self._assets.get_immich_assets(asset_ids)
        discovered: list[DiscoveredGroup] = []
        for group in snapshot:
            hydrated_assets = tuple(
                assets[asset_id] for asset_id in group.asset_ids if asset_id in assets
            )
            if len(hydrated_assets) != len(group.asset_ids):
                logger.warning(
                    "Skipping persisted Immich duplicate group %s because "
                    "%s/%s local members are available",
                    group.provider_group_id,
                    len(hydrated_assets),
                    len(group.asset_ids),
                )
                continue
            group_assets = tuple(
                asset for asset in hydrated_assets if asset.asset_type != "VIDEO"
            )
            if len(group_assets) < 2:
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

    async def _discover_persisted(self) -> list[DiscoveredGroup]:
        assert self._snapshots is not None
        return await self._hydrate_persisted(await self._snapshots.groups())

    async def _discover_live(self) -> list[DiscoveredGroup]:
        """Compatibility path for tests/direct callers that do not inject discovery."""

        assert self._immich is not None
        groups = await self._immich.list_duplicate_groups()
        hydrated: dict[UUID, ImmichAsset] = {}
        local_sizes: dict[UUID, int] = {}
        sparse: dict[UUID, list[ImmichAsset]] = {}
        for group in groups:
            for asset in group.assets:
                if asset.asset_type == "VIDEO":
                    continue
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
                    *(
                        fetch_live(asset_id)
                        for asset_id in unresolved[
                            offset : offset + LIVE_HYDRATION_BATCH_SIZE
                        ]
                    )
                )
            )

        discovered: list[DiscoveredGroup] = []
        for group in groups:
            assets: list[ImmichAsset] = []
            for asset in group.assets:
                if asset.asset_type == "VIDEO":
                    continue
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
            if len(group.assets) >= 2 and len(assets) < 2:
                continue
            provider_id = str(group.duplicate_id)
            discovered.append(
                DiscoveredGroup(
                    group_id=f"immich:{provider_id}",
                    discovery_source=DiscoverySource.IMMICH_DUPLICATE,
                    provider_group_id=provider_id,
                    assets=tuple(assets),
                    provider_metadata={"endpoint": "/api/duplicates"},
                )
            )
        return discovered

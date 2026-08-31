"""Completed Companion similarity scans as reviewable duplicate groups."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_scan_repository import SimilarityScanSnapshot


class _ScanReader(Protocol):
    async def latest_completed(self) -> SimilarityScanSnapshot | None: ...


class _AssetReader(Protocol):
    async def get_immich_assets(
        self,
        asset_ids: list[UUID],
    ) -> dict[UUID, ImmichAsset]: ...


class SimilarityDuplicateProvider:
    """Adapt only the latest atomically completed scan into pair-first groups."""

    def __init__(
        self,
        scans: _ScanReader,
        assets: _AssetReader,
    ) -> None:
        self._scans = scans
        self._assets = assets

    async def discover(self) -> list[DiscoveredGroup]:
        snapshot = await self._scans.latest_completed()
        if snapshot is None:
            return []
        asset_ids = [
            asset_id
            for pair in snapshot.pairs
            for asset_id in (pair.asset_id_low, pair.asset_id_high)
        ]
        assets = await self._assets.get_immich_assets(asset_ids)
        parameters = snapshot.parameters
        groups: list[DiscoveredGroup] = []
        for pair in snapshot.pairs:
            low = assets.get(pair.asset_id_low)
            high = assets.get(pair.asset_id_high)
            if low is None or high is None:
                continue
            stable_id = (
                "companion:"
                f"{parameters.model_version}:"
                f"{parameters.feature_version}:"
                f"{parameters.comparison_version}:"
                f"{pair.asset_id_low}:{pair.asset_id_high}"
            )
            groups.append(
                DiscoveredGroup(
                    group_id=stable_id,
                    discovery_source=DiscoverySource.COMPANION_SIMILARITY,
                    provider_group_id=(
                        f"{snapshot.id}:{pair.asset_id_low}:{pair.asset_id_high}"
                    ),
                    assets=(low, high),
                    provider_metadata={
                        "scan_id": str(snapshot.id),
                        "scan_threshold_percent": str(parameters.similarity_threshold),
                        "scan_scope": parameters.scope,
                        "similarity_percent": str(pair.evidence.similarity_percent),
                        "model_version": parameters.model_version,
                        "feature_version": str(parameters.feature_version),
                        "comparison_version": str(parameters.comparison_version),
                        "completed_at": snapshot.completed_at.isoformat(),
                    },
                )
            )
        return groups

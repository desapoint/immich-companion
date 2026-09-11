"""Completed Companion similarity scans as reviewable duplicate groups."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_grouping import (
    SIMILARITY_GROUPING_VERSION,
    SimilarityGroupingEdge,
    validated_similarity_groups,
)
from companion.similarity_scan_repository import SimilarityScanSnapshot


class _ScanReader(Protocol):
    async def latest_completed(self) -> SimilarityScanSnapshot | None: ...


class _AssetReader(Protocol):
    async def get_immich_assets(
        self,
        asset_ids: list[UUID],
    ) -> dict[UUID, ImmichAsset]: ...


class SimilarityDuplicateProvider:
    """Adapt the latest completed scan into validated review groups."""

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
        parameters = snapshot.parameters
        validated_groups = validated_similarity_groups(
            tuple(
                SimilarityGroupingEdge(
                    asset_id_low=pair.asset_id_low,
                    asset_id_high=pair.asset_id_high,
                    similarity_percent=pair.evidence.similarity_percent,
                )
                for pair in snapshot.pairs
            ),
            mode=parameters.validation_mode,
            threshold=parameters.similarity_threshold,
            preferred_anchor_asset_id=parameters.anchor_asset_id,
        )
        asset_ids = sorted(
            {asset_id for group in validated_groups for asset_id in group.asset_ids},
            key=lambda asset_id: asset_id.int,
        )
        assets = await self._assets.get_immich_assets(asset_ids)
        groups: list[DiscoveredGroup] = []
        for validated in validated_groups:
            ordered_ids = (
                validated.anchor_asset_id,
                *(
                    asset_id
                    for asset_id in validated.asset_ids
                    if asset_id != validated.anchor_asset_id
                ),
            )
            group_assets = tuple(
                assets[asset_id] for asset_id in ordered_ids if asset_id in assets
            )
            if len(group_assets) != len(validated.asset_ids):
                continue
            member_key = ":".join(str(asset_id) for asset_id in validated.asset_ids)
            version_key = (
                f"{parameters.model_version}:"
                f"{parameters.feature_version}:"
                f"{parameters.comparison_version}:"
                f"{parameters.config_fingerprint[:12]}:"
                f"{parameters.validation_mode}:"
            )
            if len(validated.asset_ids) == 2:
                stable_id = f"companion:{version_key}{member_key}"
                provider_group_id = f"{snapshot.id}:{member_key}"
            else:
                stable_id = (
                    f"companion:{version_key}cohesion-{SIMILARITY_GROUPING_VERSION}:{member_key}"
                )
                provider_group_id = (
                    f"{snapshot.id}:cohesion-{SIMILARITY_GROUPING_VERSION}:{member_key}"
                )
            groups.append(
                DiscoveredGroup(
                    group_id=stable_id,
                    discovery_source=DiscoverySource.COMPANION_SIMILARITY,
                    provider_group_id=provider_group_id,
                    assets=group_assets,
                    provider_metadata={
                        "scan_id": str(snapshot.id),
                        "scan_threshold_percent": str(parameters.similarity_threshold),
                        "scan_scope": parameters.scope,
                        "similarity_percent": str(validated.minimum_similarity_percent),
                        "minimum_similarity_percent": str(
                            validated.minimum_similarity_percent
                        ),
                        "maximum_similarity_percent": str(
                            validated.maximum_similarity_percent
                        ),
                        "cohesive_pair_count": str(validated.pair_count),
                        "grouping_version": str(SIMILARITY_GROUPING_VERSION),
                        "validation_mode": parameters.validation_mode,
                        "anchor_asset_id": str(validated.anchor_asset_id),
                        "model_version": parameters.model_version,
                        "feature_version": str(parameters.feature_version),
                        "comparison_version": str(parameters.comparison_version),
                        "config_fingerprint": parameters.config_fingerprint,
                        "completed_at": snapshot.completed_at.isoformat(),
                    },
                    similarity_validation=validated,
                )
            )
        return groups

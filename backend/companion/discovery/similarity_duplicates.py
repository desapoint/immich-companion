"""Completed Companion similarity scans as reviewable duplicate groups."""

from __future__ import annotations

from collections.abc import AsyncIterator
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.duplicate_identity import INDEXED_GROUP_ID_MAX_BYTES, member_set_key
from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_grouping import (
    SIMILARITY_GROUPING_VERSION,
    SimilarityGroupingEdge,
    SimilarityGroupValidator,
    ValidatedSimilarityGroup,
)
from companion.similarity_scan_repository import SimilarityScanRunSummary

SIMILARITY_GROUP_HYDRATION_ASSET_BUDGET = 1_000


class _ScanReader(Protocol):
    async def latest_completed_summary(self) -> SimilarityScanRunSummary | None: ...

    def iter_grouping_edges(
        self,
        scan_id: UUID,
        *,
        batch_size: int = 1_000,
    ) -> AsyncIterator[list[SimilarityGroupingEdge]]: ...


class _AssetReader(Protocol):
    async def get_immich_assets(
        self,
        asset_ids: list[UUID],
    ) -> dict[UUID, ImmichAsset]: ...


def _similarity_group_ids(
    summary: SimilarityScanRunSummary,
    validated: ValidatedSimilarityGroup,
) -> tuple[str, str]:
    """Preserve existing small IDs and hash only oversized indexed identities."""

    parameters = summary.parameters
    version_key = (
        f"{parameters.model_version}:"
        f"{parameters.feature_version}:"
        f"{parameters.comparison_version}:"
        f"{parameters.config_fingerprint[:12]}:"
        f"{parameters.validation_mode}:"
    )
    cohesion_key = (
        ""
        if len(validated.asset_ids) == 2
        else f"cohesion-{SIMILARITY_GROUPING_VERSION}:"
    )
    stable_prefix = f"companion:{version_key}{cohesion_key}"
    provider_prefix = f"{summary.id}:{cohesion_key}"
    member_key_bytes = len(validated.asset_ids) * 36 + len(validated.asset_ids) - 1

    if (
        len(stable_prefix.encode()) + member_key_bytes <= INDEXED_GROUP_ID_MAX_BYTES
        and len(provider_prefix.encode()) + member_key_bytes
        <= INDEXED_GROUP_ID_MAX_BYTES
    ):
        member_key = ":".join(str(asset_id) for asset_id in validated.asset_ids)
        return f"{stable_prefix}{member_key}", f"{provider_prefix}{member_key}"

    members_digest = member_set_key(validated.asset_ids)
    group_kind = cohesion_key.removesuffix(":") or "pair"
    stable_identity = (
        f"{version_key}{group_kind}:{members_digest}"
    )
    stable_digest = sha256(stable_identity.encode()).hexdigest()
    group_id = f"companion:sha256:{stable_digest}"
    provider_group_id = f"{summary.id}:{group_kind}:sha256:{members_digest}"
    return group_id, provider_group_id


class SimilarityDuplicateProvider:
    """Adapt the latest completed scan into validated review groups."""

    def __init__(
        self,
        scans: _ScanReader,
        assets: _AssetReader,
    ) -> None:
        self._scans = scans
        self._assets = assets

    async def _validated_groups(self):
        summary = await self._scans.latest_completed_summary()
        if summary is None or summary.pair_evidence_pruned_at is not None:
            return None

        parameters = summary.parameters
        validator = SimilarityGroupValidator(
            mode=parameters.validation_mode,
            threshold=parameters.similarity_threshold,
            preferred_anchor_asset_id=parameters.anchor_asset_id,
            max_link_depth=parameters.max_link_depth,
        )
        async for batch in self._scans.iter_grouping_edges(summary.id):
            validator.add_edges(batch)
        return summary, validator.groups()

    @staticmethod
    def _materialize_group(
        summary: SimilarityScanRunSummary,
        validated,
        assets: dict[UUID, ImmichAsset],
    ) -> DiscoveredGroup | None:
        parameters = summary.parameters
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
            return None

        stable_id, provider_group_id = _similarity_group_ids(summary, validated)
        return DiscoveredGroup(
            group_id=stable_id,
            discovery_source=DiscoverySource.COMPANION_SIMILARITY,
            provider_group_id=provider_group_id,
            assets=group_assets,
            provider_metadata={
                "scan_id": str(summary.id),
                "scan_threshold_percent": str(parameters.similarity_threshold),
                "scan_scope": parameters.scope,
                "similarity_percent": str(validated.minimum_similarity_percent),
                "minimum_similarity_percent": str(validated.minimum_similarity_percent),
                "maximum_similarity_percent": str(validated.maximum_similarity_percent),
                "cohesive_pair_count": str(validated.pair_count),
                "grouping_version": str(SIMILARITY_GROUPING_VERSION),
                "validation_mode": parameters.validation_mode,
                "max_link_depth": str(parameters.max_link_depth),
                "anchor_asset_id": str(validated.anchor_asset_id),
                "model_version": parameters.model_version,
                "feature_version": str(parameters.feature_version),
                "comparison_version": str(parameters.comparison_version),
                "config_fingerprint": parameters.config_fingerprint,
                "completed_at": summary.completed_at.isoformat(),
            },
            similarity_validation=validated,
        )

    async def discover_batches(
        self,
        *,
        batch_size: int = 250,
    ) -> AsyncIterator[list[DiscoveredGroup]]:
        """Materialize similarity groups in bounded asset-hydration batches."""

        batch_size = max(1, batch_size)
        state = await self._validated_groups()
        if state is None:
            return
        summary, validated_groups = state

        pending: list[ValidatedSimilarityGroup] = []
        pending_asset_ids: set[UUID] = set()

        async def flush() -> list[DiscoveredGroup]:
            asset_ids = sorted(pending_asset_ids, key=lambda asset_id: asset_id.int)
            assets = await self._assets.get_immich_assets(asset_ids)
            return [
                group
                for validated in pending
                if (group := self._materialize_group(summary, validated, assets)) is not None
            ]

        for validated in validated_groups:
            additional_assets = sum(
                1 for asset_id in validated.asset_ids if asset_id not in pending_asset_ids
            )
            if pending and (
                len(pending) >= batch_size
                or len(pending_asset_ids) + additional_assets
                > SIMILARITY_GROUP_HYDRATION_ASSET_BUDGET
            ):
                groups = await flush()
                if groups:
                    yield groups
                pending = []
                pending_asset_ids = set()
            pending.append(validated)
            pending_asset_ids.update(validated.asset_ids)

        if pending:
            groups = await flush()
            if groups:
                yield groups

    async def discover(self) -> list[DiscoveredGroup]:
        groups: list[DiscoveredGroup] = []
        async for batch in self.discover_batches():
            groups.extend(batch)
        return groups

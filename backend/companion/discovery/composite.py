"""Composition for independent duplicate discovery providers."""

from __future__ import annotations

from companion.discovery.base import (
    DiscoveredGroup,
    DiscoveryEvidence,
    GroupDiscoveryProvider,
)
from companion.group_decision import DiscoverySource


def _member_key(group: DiscoveredGroup) -> tuple[int, ...]:
    return tuple(sorted(asset.id.int for asset in group.assets))


def _primary_group(left: DiscoveredGroup, right: DiscoveredGroup) -> DiscoveredGroup:
    if left.discovery_source is DiscoverySource.IMMICH_DUPLICATE:
        return left
    if right.discovery_source is DiscoverySource.IMMICH_DUPLICATE:
        return right
    return left


def _coalesce(left: DiscoveredGroup, right: DiscoveredGroup) -> DiscoveredGroup:
    primary = _primary_group(left, right)
    evidence_by_source: dict[DiscoverySource, DiscoveryEvidence] = {}
    for evidence in (*left.evidence, *right.evidence):
        if evidence.discovery_source in evidence_by_source:
            raise ValueError(
                "A discovery provider returned the same exact member set more than once: "
                f"{evidence.discovery_source.value}"
            )
        evidence_by_source[evidence.discovery_source] = evidence
    evidence = tuple(
        evidence_by_source[source]
        for source in (
            DiscoverySource.IMMICH_DUPLICATE,
            DiscoverySource.COMPANION_SIMILARITY,
        )
        if source in evidence_by_source
    )
    metadata = dict(primary.provider_metadata)
    for item in evidence:
        prefix = item.discovery_source.value
        if item.provider_group_id is not None:
            metadata[f"{prefix}.provider_group_id"] = item.provider_group_id
        metadata.update({f"{prefix}.{key}": value for key, value in item.metadata.items()})
    return DiscoveredGroup(
        group_id=primary.group_id,
        discovery_source=primary.discovery_source,
        provider_group_id=primary.provider_group_id,
        assets=primary.assets,
        provider_metadata=metadata,
        discovery_evidence=evidence,
        similarity_validation=left.similarity_validation or right.similarity_validation,
    )


class CompositeGroupDiscoveryProvider:
    """Publish provider snapshots in deterministic registration order."""

    def __init__(self, *providers: GroupDiscoveryProvider) -> None:
        self._providers = providers

    async def discover(self) -> list[DiscoveredGroup]:
        groups: list[DiscoveredGroup] = []
        group_ids: set[str] = set()
        member_positions: dict[tuple[int, ...], int] = {}
        for provider in self._providers:
            for group in await provider.discover():
                if group.group_id in group_ids:
                    raise ValueError(f"Duplicate discovery group ID: {group.group_id}")
                group_ids.add(group.group_id)
                key = _member_key(group)
                position = member_positions.get(key)
                if position is not None:
                    current = groups[position]
                    if current.discovery_source is not group.discovery_source:
                        groups[position] = _coalesce(current, group)
                        continue
                member_positions.setdefault(key, len(groups))
                groups.append(group)
        return groups

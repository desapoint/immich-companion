"""Composition for independent duplicate discovery providers."""

from __future__ import annotations

from collections.abc import AsyncIterator

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
        async for batch in self.discover_batches():
            groups.extend(batch)
        return groups

    async def discover_batches(
        self,
        *,
        batch_size: int = 250,
    ) -> AsyncIterator[list[DiscoveredGroup]]:
        """Consume provider snapshots in batches while preserving coalescing semantics."""

        if not self._providers:
            return
        batch_size = max(1, batch_size)

        async def provider_batches(provider) -> AsyncIterator[list[DiscoveredGroup]]:
            batch_reader = getattr(provider, "discover_batches", None)
            if callable(batch_reader):
                async for batch in batch_reader(batch_size=batch_size):
                    yield batch
                return
            groups = await provider.discover()
            for offset in range(0, len(groups), batch_size):
                yield groups[offset : offset + batch_size]

        pending: list[DiscoveredGroup | None] = []
        pending_group_ids: set[str] = set()
        pending_member_positions: dict[tuple[int, ...], int] = {}
        for provider in self._providers[1:]:
            async for provider_batch in provider_batches(provider):
                for group in provider_batch:
                    if group.group_id in pending_group_ids:
                        raise ValueError(f"Duplicate discovery group ID: {group.group_id}")
                    pending_group_ids.add(group.group_id)
                    key = _member_key(group)
                    position = pending_member_positions.get(key)
                    if position is not None:
                        current = pending[position]
                        if (
                            current is not None
                            and current.discovery_source is not group.discovery_source
                        ):
                            pending[position] = _coalesce(current, group)
                            continue
                    pending_member_positions.setdefault(key, len(pending))
                    pending.append(group)

        emitted_group_ids: set[str] = set()
        output: list[DiscoveredGroup] = []

        async for source_batch in provider_batches(self._providers[0]):
            for group in source_batch:
                if group.group_id in emitted_group_ids or group.group_id in pending_group_ids:
                    raise ValueError(f"Duplicate discovery group ID: {group.group_id}")
                emitted_group_ids.add(group.group_id)
                position = pending_member_positions.get(_member_key(group))
                if position is not None:
                    current = pending[position]
                    if (
                        current is not None
                        and current.discovery_source is not group.discovery_source
                    ):
                        group = _coalesce(group, current)
                        pending[position] = None
                output.append(group)
                if len(output) >= batch_size:
                    yield output
                    output = []
        if output:
            yield output

        output = []
        for group in pending:
            if group is None:
                continue
            if group.group_id in emitted_group_ids:
                raise ValueError(f"Duplicate discovery group ID: {group.group_id}")
            emitted_group_ids.add(group.group_id)
            output.append(group)
            if len(output) >= batch_size:
                yield output
                output = []
        if output:
            yield output

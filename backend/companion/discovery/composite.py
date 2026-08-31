"""Composition for independent duplicate discovery providers."""

from __future__ import annotations

from companion.discovery.base import DiscoveredGroup, GroupDiscoveryProvider


class CompositeGroupDiscoveryProvider:
    """Publish provider snapshots in deterministic registration order."""

    def __init__(self, *providers: GroupDiscoveryProvider) -> None:
        self._providers = providers

    async def discover(self) -> list[DiscoveredGroup]:
        groups: list[DiscoveredGroup] = []
        seen: set[str] = set()
        for provider in self._providers:
            for group in await provider.discover():
                if group.group_id in seen:
                    raise ValueError(f"Duplicate discovery group ID: {group.group_id}")
                seen.add(group.group_id)
                groups.append(group)
        return groups

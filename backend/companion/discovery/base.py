"""Provider-neutral duplicate group discovery contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset


@dataclass(frozen=True, slots=True)
class DiscoveredGroup:
    """One immutable group snapshot emitted by any discovery provider."""

    group_id: str
    discovery_source: DiscoverySource
    provider_group_id: str | None
    assets: tuple[ImmichAsset, ...]
    provider_metadata: Mapping[str, str] = field(default_factory=dict)


class GroupDiscoveryProvider(Protocol):
    """Discover current group snapshots without making resolution decisions."""

    async def discover(self) -> list[DiscoveredGroup]: ...

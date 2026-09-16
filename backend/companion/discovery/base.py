"""Provider-neutral duplicate group discovery contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from companion.group_decision import DiscoverySource
from companion.immich import ImmichAsset
from companion.similarity_grouping import ValidatedSimilarityGroup


@dataclass(frozen=True, slots=True)
class DiscoveryEvidence:
    """Provider-specific provenance retained when logical groups coalesce."""

    discovery_source: DiscoverySource
    provider_group_id: str | None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiscoveredGroup:
    """One immutable group snapshot emitted by any discovery provider."""

    group_id: str
    discovery_source: DiscoverySource
    provider_group_id: str | None
    assets: tuple[ImmichAsset, ...]
    provider_metadata: Mapping[str, str] = field(default_factory=dict)
    discovery_evidence: tuple[DiscoveryEvidence, ...] = ()
    similarity_validation: ValidatedSimilarityGroup | None = None

    @property
    def evidence(self) -> tuple[DiscoveryEvidence, ...]:
        """Return explicit evidence or synthesize the originating provider entry."""

        return self.discovery_evidence or (
            DiscoveryEvidence(
                discovery_source=self.discovery_source,
                provider_group_id=self.provider_group_id,
                metadata=self.provider_metadata,
            ),
        )


class GroupDiscoveryProvider(Protocol):
    """Discover current group snapshots without making resolution decisions."""

    async def discover(self) -> list[DiscoveredGroup]: ...

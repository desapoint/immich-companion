"""Duplicate discovery provider contracts and built-in adapters."""

from companion.discovery.base import DiscoveredGroup, GroupDiscoveryProvider
from companion.discovery.immich_duplicates import ImmichDuplicateProvider

__all__ = ["DiscoveredGroup", "GroupDiscoveryProvider", "ImmichDuplicateProvider"]

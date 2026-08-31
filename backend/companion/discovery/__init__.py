"""Duplicate discovery provider contracts and built-in adapters."""

from companion.discovery.base import DiscoveredGroup, GroupDiscoveryProvider
from companion.discovery.immich_duplicates import ImmichDuplicateProvider
from companion.discovery.similarity_candidates import (
    SimilarityCandidateFeature,
    SimilarityCandidatePair,
    bounded_similarity_candidates,
)

__all__ = [
    "DiscoveredGroup",
    "GroupDiscoveryProvider",
    "ImmichDuplicateProvider",
    "SimilarityCandidateFeature",
    "SimilarityCandidatePair",
    "bounded_similarity_candidates",
]

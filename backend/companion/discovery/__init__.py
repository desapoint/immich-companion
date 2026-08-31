"""Duplicate discovery provider contracts and built-in adapters."""

from companion.discovery.base import DiscoveredGroup, GroupDiscoveryProvider
from companion.discovery.composite import CompositeGroupDiscoveryProvider
from companion.discovery.immich_duplicates import ImmichDuplicateProvider
from companion.discovery.similarity_candidates import (
    SimilarityCandidateFeature,
    SimilarityCandidatePair,
    bounded_similarity_candidates,
)
from companion.discovery.similarity_duplicates import SimilarityDuplicateProvider

__all__ = [
    "DiscoveredGroup",
    "CompositeGroupDiscoveryProvider",
    "GroupDiscoveryProvider",
    "ImmichDuplicateProvider",
    "SimilarityDuplicateProvider",
    "SimilarityCandidateFeature",
    "SimilarityCandidatePair",
    "bounded_similarity_candidates",
]

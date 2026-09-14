"""Duplicate discovery provider contracts and built-in adapters."""

from companion.discovery.base import DiscoveredGroup, DiscoveryEvidence, GroupDiscoveryProvider
from companion.discovery.composite import CompositeGroupDiscoveryProvider
from companion.discovery.immich_duplicates import ImmichDuplicateProvider
from companion.discovery.persisted_composite import PersistedCompositeDuplicateProvider
from companion.discovery.similarity_candidates import (
    CANDIDATE_INDEX_VERSION,
    BoundedSimilarityCandidateIndex,
    SimilarityCandidateFeature,
    SimilarityCandidatePair,
    SimilarityCandidateStats,
    bounded_similarity_candidates,
)
from companion.discovery.similarity_duplicates import SimilarityDuplicateProvider

__all__ = [
    "CANDIDATE_INDEX_VERSION",
    "BoundedSimilarityCandidateIndex",
    "DiscoveredGroup",
    "DiscoveryEvidence",
    "CompositeGroupDiscoveryProvider",
    "GroupDiscoveryProvider",
    "ImmichDuplicateProvider",
    "PersistedCompositeDuplicateProvider",
    "SimilarityDuplicateProvider",
    "SimilarityCandidateFeature",
    "SimilarityCandidatePair",
    "SimilarityCandidateStats",
    "bounded_similarity_candidates",
]

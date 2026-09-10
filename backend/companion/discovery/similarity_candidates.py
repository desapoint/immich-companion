"""Bounded perceptual-neighbor candidate lookup for Companion discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


class SimilarityCandidateFeature(Protocol):
    """Compact feature fields required before an expensive comparison."""

    asset_id: UUID
    model_version: str
    feature_version: int
    width: int
    height: int
    perceptual_hash: str


@dataclass(frozen=True, slots=True)
class SimilarityCandidatePair:
    """One canonical pair that passed cheap candidate filters."""

    asset_id_low: UUID
    asset_id_high: UUID
    perceptual_distance: int


@dataclass(slots=True)
class SimilarityCandidateStats:
    """Low-overhead counters proving candidate lookup stays degree-bounded."""

    assets_received: int = 0
    assets_indexed: int = 0
    invalid_features: int = 0
    index_nodes_visited: int = 0
    raw_neighbor_matches: int = 0
    pairs_emitted: int = 0
    peak_query_matches: int = 0
    peak_active_index_assets: int = 0


@dataclass(slots=True)
class _HashNode:
    value: int
    asset_ids: list[UUID] = field(default_factory=list)
    children: dict[int, _HashNode] = field(default_factory=dict)


class _HammingBkTree:
    """BK-tree specialized for fixed-width integer Hamming distance."""

    def __init__(self) -> None:
        self._root: _HashNode | None = None
        self._nodes_by_asset: dict[UUID, _HashNode] = {}

    @staticmethod
    def _distance(left: int, right: int) -> int:
        return (left ^ right).bit_count()

    def add(self, value: int, asset_id: UUID) -> None:
        if self._root is None:
            self._root = _HashNode(value=value, asset_ids=[asset_id])
            self._nodes_by_asset[asset_id] = self._root
            return
        node = self._root
        while True:
            distance = self._distance(value, node.value)
            if distance == 0:
                node.asset_ids.append(asset_id)
                self._nodes_by_asset[asset_id] = node
                return
            child = node.children.get(distance)
            if child is None:
                child = _HashNode(value=value, asset_ids=[asset_id])
                node.children[distance] = child
                self._nodes_by_asset[asset_id] = child
                return
            node = child

    def remove(self, asset_id: UUID) -> None:
        """Remove a saturated asset while preserving the immutable hash index shape."""

        node = self._nodes_by_asset.pop(asset_id, None)
        if node is not None:
            node.asset_ids.remove(asset_id)

    def find(
        self,
        value: int,
        maximum_distance: int,
        stats: SimilarityCandidateStats | None = None,
    ) -> list[tuple[int, UUID]]:
        if self._root is None:
            return []
        matches: list[tuple[int, UUID]] = []
        pending = [self._root]
        while pending:
            node = pending.pop()
            if stats is not None:
                stats.index_nodes_visited += 1
            distance = self._distance(value, node.value)
            if distance <= maximum_distance:
                matches.extend((distance, asset_id) for asset_id in node.asset_ids)
            lower = distance - maximum_distance
            upper = distance + maximum_distance
            pending.extend(
                child
                for edge, child in node.children.items()
                if lower <= edge <= upper
            )
        if stats is not None:
            stats.raw_neighbor_matches += len(matches)
            stats.peak_query_matches = max(stats.peak_query_matches, len(matches))
        return matches


def _aspect_ratio(feature: SimilarityCandidateFeature) -> float:
    return feature.width / feature.height


def _aspect_difference(
    left: SimilarityCandidateFeature,
    right: SimilarityCandidateFeature,
) -> float:
    left_ratio = _aspect_ratio(left)
    right_ratio = _aspect_ratio(right)
    return abs(left_ratio - right_ratio) / max(left_ratio, right_ratio)


def bounded_similarity_candidates(
    features: list[SimilarityCandidateFeature],
    *,
    maximum_perceptual_distance: int = 12,
    maximum_aspect_difference: float = 0.05,
    maximum_neighbors_per_asset: int = 8,
    stats: SimilarityCandidateStats | None = None,
) -> list[SimilarityCandidatePair]:
    """Return deterministic plausible pairs without constructing an all-pairs matrix."""

    if not 0 <= maximum_perceptual_distance <= 64:
        raise ValueError("maximum_perceptual_distance must be between 0 and 64")
    if not 0 <= maximum_aspect_difference <= 1:
        raise ValueError("maximum_aspect_difference must be between 0 and 1")
    if maximum_neighbors_per_asset < 1:
        raise ValueError("maximum_neighbors_per_asset must be positive")

    if stats is not None:
        stats.assets_received = len(features)
    by_id = {feature.asset_id: feature for feature in features}
    ordered = sorted(by_id.values(), key=lambda feature: feature.asset_id.int)
    trees: dict[tuple[str, int], _HammingBkTree] = {}
    neighbor_counts: dict[UUID, int] = {}
    pairs: list[SimilarityCandidatePair] = []
    active_index_assets = 0

    for feature in ordered:
        if feature.width <= 0 or feature.height <= 0:
            if stats is not None:
                stats.invalid_features += 1
            continue
        try:
            hash_value = int(feature.perceptual_hash, 16)
        except ValueError:
            if stats is not None:
                stats.invalid_features += 1
            continue
        version = (feature.model_version, feature.feature_version)
        tree = trees.setdefault(version, _HammingBkTree())
        matches = sorted(
            tree.find(hash_value, maximum_perceptual_distance, stats),
            key=lambda item: (item[0], item[1].int),
        )
        for distance, candidate_id in matches:
            if neighbor_counts.get(feature.asset_id, 0) >= maximum_neighbors_per_asset:
                break
            if neighbor_counts.get(candidate_id, 0) >= maximum_neighbors_per_asset:
                continue
            candidate = by_id[candidate_id]
            if _aspect_difference(feature, candidate) > maximum_aspect_difference:
                continue
            low, high = sorted((feature.asset_id, candidate_id), key=lambda value: value.int)
            pairs.append(
                SimilarityCandidatePair(
                    asset_id_low=low,
                    asset_id_high=high,
                    perceptual_distance=distance,
                )
            )
            neighbor_counts[feature.asset_id] = neighbor_counts.get(feature.asset_id, 0) + 1
            neighbor_counts[candidate_id] = neighbor_counts.get(candidate_id, 0) + 1
            if neighbor_counts[candidate_id] >= maximum_neighbors_per_asset:
                tree.remove(candidate_id)
                active_index_assets -= 1
        if neighbor_counts.get(feature.asset_id, 0) < maximum_neighbors_per_asset:
            tree.add(hash_value, feature.asset_id)
            active_index_assets += 1
            if stats is not None:
                stats.assets_indexed += 1
                stats.peak_active_index_assets = max(
                    stats.peak_active_index_assets,
                    active_index_assets,
                )

    if stats is not None:
        stats.pairs_emitted = len(pairs)

    return pairs

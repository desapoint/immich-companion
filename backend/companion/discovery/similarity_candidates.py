"""Bounded perceptual-neighbor candidate lookup for Companion discovery."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

CANDIDATE_INDEX_VERSION = 3


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


@dataclass(frozen=True, slots=True)
class _ActiveFeature:
    model_version: str
    feature_version: int
    width: int
    height: int


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


def perceptual_hash_distance(left_hash: str, right_hash: str) -> int:
    """Return the production Hamming distance for two fixed-width perceptual hashes."""

    return (int(left_hash, 16) ^ int(right_hash, 16)).bit_count()


def _aspect_ratio(width: int, height: int) -> float:
    return width / height


def _aspect_ratio_difference(
    left_width: int,
    left_height: int,
    right_width: int,
    right_height: int,
) -> float:
    left_ratio = _aspect_ratio(left_width, left_height)
    right_ratio = _aspect_ratio(right_width, right_height)
    return abs(left_ratio - right_ratio) / max(left_ratio, right_ratio)


def aspect_ratio_difference(
    left: SimilarityCandidateFeature,
    right: SimilarityCandidateFeature,
) -> float:
    """Return the production normalized aspect-ratio difference for one pair."""

    return _aspect_ratio_difference(left.width, left.height, right.width, right.height)


class BoundedSimilarityCandidateIndex:
    """Incremental deterministic candidate index with bounded retained pair state."""

    def __init__(
        self,
        features: Iterable[SimilarityCandidateFeature] | None = None,
        *,
        maximum_perceptual_distance: int = 12,
        maximum_aspect_difference: float = 0.05,
        maximum_neighbors_per_asset: int = 8,
        stats: SimilarityCandidateStats | None = None,
        retain_pairs: bool = True,
    ) -> None:
        if not 0 <= maximum_perceptual_distance <= 64:
            raise ValueError("maximum_perceptual_distance must be between 0 and 64")
        if not 0 <= maximum_aspect_difference <= 1:
            raise ValueError("maximum_aspect_difference must be between 0 and 1")
        if maximum_neighbors_per_asset < 1:
            raise ValueError("maximum_neighbors_per_asset must be positive")

        by_id = {feature.asset_id: feature for feature in (features or ())}
        self.ordered_features = sorted(
            by_id.values(),
            key=lambda feature: feature.asset_id.int,
        )
        self._maximum_perceptual_distance = maximum_perceptual_distance
        self._maximum_aspect_difference = maximum_aspect_difference
        self._maximum_neighbors_per_asset = maximum_neighbors_per_asset
        self._maximum_forward_neighbors = max(1, maximum_neighbors_per_asset - 1)
        self._stats = stats
        self._trees: dict[tuple[str, int], _HammingBkTree] = {}
        self._active_features: dict[UUID, _ActiveFeature] = {}
        self._neighbor_counts: dict[UUID, int] = {}
        self._pairs: list[SimilarityCandidatePair] = []
        self._retain_pairs = retain_pairs
        self._processed = 0
        self._active_index_assets = 0
        self._last_asset_id: UUID | None = None

    @property
    def processed(self) -> int:
        return self._processed

    @property
    def pairs(self) -> list[SimilarityCandidatePair]:
        return self._pairs

    def process_next(self, count: int) -> list[SimilarityCandidatePair]:
        """Process at most count constructor inputs and return new pairs."""

        if count < 1:
            raise ValueError("count must be positive")
        stop = min(len(self.ordered_features), self._processed + count)
        return self.process_batch(self.ordered_features[self._processed : stop])

    def process_batch(
        self,
        features: Iterable[SimilarityCandidateFeature],
    ) -> list[SimilarityCandidatePair]:
        """Consume one monotonically ordered feature batch and return emitted pairs."""

        ordered = sorted(
            {feature.asset_id: feature for feature in features}.values(),
            key=lambda feature: feature.asset_id.int,
        )
        emitted: list[SimilarityCandidatePair] = []
        for feature in ordered:
            if (
                self._last_asset_id is not None
                and feature.asset_id.int <= self._last_asset_id.int
            ):
                raise ValueError("Candidate feature batches must be strictly increasing")
            self._last_asset_id = feature.asset_id
            if self._stats is not None:
                self._stats.assets_received += 1
            emitted.extend(self._process_feature(feature))
            self._processed += 1
        if self._retain_pairs:
            self._pairs.extend(emitted)
        if self._stats is not None:
            self._stats.pairs_emitted += len(emitted)
        return emitted

    def _process_feature(
        self,
        feature: SimilarityCandidateFeature,
    ) -> list[SimilarityCandidatePair]:
        stats = self._stats
        if feature.width <= 0 or feature.height <= 0:
            if stats is not None:
                stats.invalid_features += 1
            return []
        try:
            hash_value = int(feature.perceptual_hash, 16)
        except ValueError:
            if stats is not None:
                stats.invalid_features += 1
            return []

        version = (feature.model_version, feature.feature_version)
        tree = self._trees.setdefault(version, _HammingBkTree())
        matches = tree.find(hash_value, self._maximum_perceptual_distance, stats)
        matches.sort(key=lambda item: (item[0], item[1].int))

        emitted: list[SimilarityCandidatePair] = []
        for distance, candidate_id in matches:
            if self._neighbor_counts.get(feature.asset_id, 0) >= self._maximum_forward_neighbors:
                break
            if self._neighbor_counts.get(candidate_id, 0) >= self._maximum_neighbors_per_asset:
                continue
            candidate = self._active_features[candidate_id]
            if (
                _aspect_ratio_difference(
                    feature.width,
                    feature.height,
                    candidate.width,
                    candidate.height,
                )
                > self._maximum_aspect_difference
            ):
                continue
            if feature.asset_id.int < candidate_id.int:
                low, high = feature.asset_id, candidate_id
            else:
                low, high = candidate_id, feature.asset_id
            emitted.append(
                SimilarityCandidatePair(
                    asset_id_low=low,
                    asset_id_high=high,
                    perceptual_distance=distance,
                )
            )
            self._neighbor_counts[feature.asset_id] = (
                self._neighbor_counts.get(feature.asset_id, 0) + 1
            )
            self._neighbor_counts[candidate_id] = self._neighbor_counts.get(candidate_id, 0) + 1
            if self._neighbor_counts[candidate_id] >= self._maximum_neighbors_per_asset:
                tree.remove(candidate_id)
                self._active_features.pop(candidate_id, None)
                self._active_index_assets -= 1

        if self._neighbor_counts.get(feature.asset_id, 0) < self._maximum_neighbors_per_asset:
            tree.add(hash_value, feature.asset_id)
            self._active_features[feature.asset_id] = _ActiveFeature(
                model_version=feature.model_version,
                feature_version=feature.feature_version,
                width=feature.width,
                height=feature.height,
            )
            self._active_index_assets += 1
            if stats is not None:
                stats.assets_indexed += 1
                stats.peak_active_index_assets = max(
                    stats.peak_active_index_assets,
                    self._active_index_assets,
                )
        return emitted


def bounded_similarity_candidates(
    features: list[SimilarityCandidateFeature],
    *,
    maximum_perceptual_distance: int = 12,
    maximum_aspect_difference: float = 0.05,
    maximum_neighbors_per_asset: int = 8,
    stats: SimilarityCandidateStats | None = None,
) -> list[SimilarityCandidatePair]:
    """Return deterministic plausible pairs without constructing an all-pairs matrix."""

    index = BoundedSimilarityCandidateIndex(
        features,
        maximum_perceptual_distance=maximum_perceptual_distance,
        maximum_aspect_difference=maximum_aspect_difference,
        maximum_neighbors_per_asset=maximum_neighbors_per_asset,
        stats=stats,
    )
    index.process_next(len(index.ordered_features) or 1)
    return index.pairs

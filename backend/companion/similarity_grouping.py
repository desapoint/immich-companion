"""Deterministic all-pairs cohesion for accepted similarity edges."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from uuid import UUID

SIMILARITY_GROUPING_VERSION = 1


@dataclass(frozen=True, slots=True)
class SimilarityGroupingEdge:
    asset_id_low: UUID
    asset_id_high: UUID
    similarity_percent: float

    def __post_init__(self) -> None:
        if self.asset_id_low.int >= self.asset_id_high.int:
            raise ValueError("Similarity grouping edges must use canonical asset order.")
        if not 0 <= self.similarity_percent <= 100:
            raise ValueError("similarity_percent must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class CohesiveSimilarityGroup:
    asset_ids: tuple[UUID, ...]
    minimum_similarity_percent: float
    maximum_similarity_percent: float
    pair_count: int


def _member_key(asset_ids: frozenset[UUID]) -> tuple[int, ...]:
    return tuple(sorted(asset_id.int for asset_id in asset_ids))


def cohesive_similarity_groups(
    edges: tuple[SimilarityGroupingEdge, ...],
) -> tuple[CohesiveSimilarityGroup, ...]:
    """Cover accepted edges with deterministic groups that are complete cliques.

    Groups may overlap. This is intentional: a non-transitive chain A-B-C must
    remain the two review groups A-B and B-C rather than becoming a false A-B-C
    equivalence group.
    """

    scores: dict[tuple[UUID, UUID], float] = {}
    for edge in edges:
        key = (edge.asset_id_low, edge.asset_id_high)
        scores[key] = max(scores.get(key, 0.0), edge.similarity_percent)
    if not scores:
        return ()

    def has_edge(left: UUID, right: UUID) -> bool:
        pair = (left, right) if left.int < right.int else (right, left)
        return pair in scores

    def is_cohesive(asset_ids: frozenset[UUID]) -> bool:
        return all(has_edge(left, right) for left, right in combinations(asset_ids, 2))

    groups: list[frozenset[UUID]] = []
    memberships: dict[UUID, set[int]] = {}
    ordered_edges = sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0][0].int, item[0][1].int),
    )
    for (left, right), _score in ordered_edges:
        candidate_indexes = memberships.get(left, set()) | memberships.get(right, set())
        candidates: list[tuple[int, frozenset[UUID]]] = []
        for index in candidate_indexes:
            proposed = groups[index] | {left, right}
            if is_cohesive(proposed):
                candidates.append((index, proposed))
        if candidates:
            index, proposed = min(
                candidates,
                key=lambda candidate: (-len(candidate[1]), _member_key(candidate[1])),
            )
            if proposed != groups[index]:
                groups[index] = proposed
                memberships.setdefault(left, set()).add(index)
                memberships.setdefault(right, set()).add(index)
            continue

        index = len(groups)
        groups.append(frozenset((left, right)))
        memberships.setdefault(left, set()).add(index)
        memberships.setdefault(right, set()).add(index)

    unique = sorted(set(groups), key=lambda group: (-len(group), _member_key(group)))
    maximal: list[frozenset[UUID]] = []
    for group in unique:
        if not any(group < existing for existing in maximal):
            maximal.append(group)

    result: list[CohesiveSimilarityGroup] = []
    for group in sorted(maximal, key=_member_key):
        asset_ids = tuple(sorted(group, key=lambda asset_id: asset_id.int))
        group_scores = [
            scores[(left, right) if left.int < right.int else (right, left)]
            for left, right in combinations(asset_ids, 2)
        ]
        result.append(
            CohesiveSimilarityGroup(
                asset_ids=asset_ids,
                minimum_similarity_percent=min(group_scores),
                maximum_similarity_percent=max(group_scores),
                pair_count=len(group_scores),
            )
        )
    return tuple(result)

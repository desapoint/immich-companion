"""Deterministic validation strategies for accepted similarity edges."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Literal
from uuid import UUID

SIMILARITY_GROUPING_VERSION = 2
SimilarityValidationMode = Literal["reference", "linked", "strict"]


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
class SimilarityAdmissionEvidence:
    asset_id: UUID
    admitted_by_asset_id: UUID | None
    admission_similarity_percent: float | None
    best_group_match_asset_id: UUID | None
    best_group_match_similarity_percent: float | None
    link_depth: int


@dataclass(frozen=True, slots=True)
class ValidatedSimilarityGroup:
    asset_ids: tuple[UUID, ...]
    anchor_asset_id: UUID
    validation_mode: SimilarityValidationMode
    minimum_similarity_percent: float
    maximum_similarity_percent: float
    pair_count: int
    admission_evidence: tuple[SimilarityAdmissionEvidence, ...]


CohesiveSimilarityGroup = ValidatedSimilarityGroup


def _member_key(asset_ids: frozenset[UUID]) -> tuple[int, ...]:
    return tuple(sorted(asset_id.int for asset_id in asset_ids))


def _pair(left: UUID, right: UUID) -> tuple[UUID, UUID]:
    return (left, right) if left.int < right.int else (right, left)


def _components(scores: dict[tuple[UUID, UUID], float]) -> list[frozenset[UUID]]:
    neighbors: dict[UUID, set[UUID]] = {}
    for left, right in scores:
        neighbors.setdefault(left, set()).add(right)
        neighbors.setdefault(right, set()).add(left)
    remaining = set(neighbors)
    result: list[frozenset[UUID]] = []
    while remaining:
        root = min(remaining, key=lambda asset_id: asset_id.int)
        pending = [root]
        component: set[UUID] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(neighbors[current] - component)
        remaining -= component
        result.append(frozenset(component))
    return sorted(result, key=_member_key)


def _best_match(
    asset_id: UUID,
    group: frozenset[UUID],
    scores: dict[tuple[UUID, UUID], float],
) -> tuple[UUID | None, float | None]:
    candidates = [
        (scores[pair], other)
        for other in group
        if other != asset_id and (pair := _pair(asset_id, other)) in scores
    ]
    if not candidates:
        return None, None
    score, other = min(candidates, key=lambda item: (-item[0], item[1].int))
    return other, score


def _group_result(
    group: frozenset[UUID],
    *,
    anchor: UUID,
    mode: SimilarityValidationMode,
    parents: dict[UUID, tuple[UUID, float, int]],
    scores: dict[tuple[UUID, UUID], float],
) -> ValidatedSimilarityGroup:
    asset_ids = tuple(sorted(group, key=lambda asset_id: asset_id.int))
    known_scores = [
        scores[pair]
        for left, right in combinations(asset_ids, 2)
        if (pair := _pair(left, right)) in scores
    ]
    evidence: list[SimilarityAdmissionEvidence] = []
    for asset_id in asset_ids:
        parent = parents.get(asset_id)
        best_id, best_score = _best_match(asset_id, group, scores)
        evidence.append(
            SimilarityAdmissionEvidence(
                asset_id=asset_id,
                admitted_by_asset_id=parent[0] if parent else None,
                admission_similarity_percent=parent[1] if parent else None,
                best_group_match_asset_id=best_id,
                best_group_match_similarity_percent=best_score,
                link_depth=parent[2] if parent else 0,
            )
        )
    admission_scores = [parent[1] for parent in parents.values()]
    stable_scores = known_scores if mode == "strict" else admission_scores
    return ValidatedSimilarityGroup(
        asset_ids=asset_ids,
        anchor_asset_id=anchor,
        validation_mode=mode,
        minimum_similarity_percent=min(stable_scores),
        maximum_similarity_percent=max(known_scores),
        pair_count=len(known_scores),
        admission_evidence=tuple(evidence),
    )


def _strict_groups(scores: dict[tuple[UUID, UUID], float]) -> list[frozenset[UUID]]:
    def cohesive(asset_ids: frozenset[UUID]) -> bool:
        return all(_pair(left, right) in scores for left, right in combinations(asset_ids, 2))

    groups: list[frozenset[UUID]] = []
    memberships: dict[UUID, set[int]] = {}
    for (left, right), _score in sorted(
        scores.items(), key=lambda item: (-item[1], item[0][0].int, item[0][1].int)
    ):
        candidates: list[tuple[int, frozenset[UUID]]] = []
        for index in memberships.get(left, set()) | memberships.get(right, set()):
            proposed = groups[index] | {left, right}
            if cohesive(proposed):
                candidates.append((index, proposed))
        if candidates:
            index, proposed = min(
                candidates, key=lambda candidate: (-len(candidate[1]), _member_key(candidate[1]))
            )
            if proposed != groups[index]:
                groups[index] = proposed
                for asset_id in proposed:
                    memberships.setdefault(asset_id, set()).add(index)
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
    return sorted(maximal, key=_member_key)


def validated_similarity_groups(
    edges: tuple[SimilarityGroupingEdge, ...],
    *,
    mode: SimilarityValidationMode,
    threshold: float,
    preferred_anchor_asset_id: UUID | None = None,
) -> tuple[ValidatedSimilarityGroup, ...]:
    """Validate bounded candidate components and retain deterministic admission evidence."""

    if mode not in {"reference", "linked", "strict"}:
        raise ValueError(f"Unsupported similarity validation mode: {mode}")
    if not 0 <= threshold <= 100:
        raise ValueError("threshold must be between 0 and 100")
    scores: dict[tuple[UUID, UUID], float] = {}
    for edge in edges:
        if edge.similarity_percent >= threshold:
            key = (edge.asset_id_low, edge.asset_id_high)
            scores[key] = max(scores.get(key, 0.0), edge.similarity_percent)
    if not scores:
        return ()

    if mode == "strict":
        results: list[ValidatedSimilarityGroup] = []
        for group in _strict_groups(scores):
            anchor = (
                preferred_anchor_asset_id
                if preferred_anchor_asset_id in group
                else min(group, key=lambda asset_id: asset_id.int)
            )
            parents = {
                asset_id: (anchor, scores[_pair(anchor, asset_id)], 1)
                for asset_id in group
                if asset_id != anchor
            }
            results.append(
                _group_result(
                    group, anchor=anchor, mode=mode, parents=parents, scores=scores
                )
            )
        return tuple(results)

    results = []
    for component in _components(scores):
        anchor = (
            preferred_anchor_asset_id
            if preferred_anchor_asset_id in component
            else min(component, key=lambda asset_id: asset_id.int)
        )
        if mode == "reference":
            members = frozenset(
                {anchor}
                | {
                    asset_id
                    for asset_id in component
                    if asset_id != anchor and _pair(anchor, asset_id) in scores
                }
            )
            parents = {
                asset_id: (anchor, scores[_pair(anchor, asset_id)], 1)
                for asset_id in members
                if asset_id != anchor
            }
        else:
            accepted = {anchor}
            parents: dict[UUID, tuple[UUID, float, int]] = {}
            while accepted != set(component):
                choices = [
                    (scores[_pair(parent, candidate)], parent, candidate)
                    for parent in accepted
                    for candidate in component - accepted
                    if _pair(parent, candidate) in scores
                ]
                score, parent, candidate = min(
                    choices,
                    key=lambda item: (-item[0], item[1].int, item[2].int),
                )
                parent_depth = parents[parent][2] if parent in parents else 0
                parents[candidate] = (parent, score, parent_depth + 1)
                accepted.add(candidate)
            members = frozenset(accepted)
        if len(members) >= 2:
            results.append(
                _group_result(
                    members, anchor=anchor, mode=mode, parents=parents, scores=scores
                )
            )
    return tuple(results)


def cohesive_similarity_groups(
    edges: tuple[SimilarityGroupingEdge, ...],
) -> tuple[CohesiveSimilarityGroup, ...]:
    """Compatibility wrapper for the original strict accepted-edge behavior."""

    return validated_similarity_groups(edges, mode="strict", threshold=0)

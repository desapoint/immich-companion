"""All-pairs similarity cohesion regressions."""

from itertools import combinations
from uuid import UUID

from companion.similarity_grouping import (
    SimilarityGroupingEdge,
    cohesive_similarity_groups,
)

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
C = UUID("33333333-3333-4333-8333-333333333333")
D = UUID("44444444-4444-4444-8444-444444444444")


def edge(left: UUID, right: UUID, score: float) -> SimilarityGroupingEdge:
    return SimilarityGroupingEdge(left, right, score)


def test_fully_connected_triangle_becomes_one_cohesive_group() -> None:
    groups = cohesive_similarity_groups(
        (edge(A, B, 99), edge(B, C, 96), edge(A, C, 97))
    )

    assert len(groups) == 1
    assert groups[0].asset_ids == (A, B, C)
    assert groups[0].minimum_similarity_percent == 96
    assert groups[0].maximum_similarity_percent == 99
    assert groups[0].pair_count == 3


def test_non_transitive_chain_remains_separate_overlapping_pairs() -> None:
    groups = cohesive_similarity_groups((edge(A, B, 98), edge(B, C, 97)))

    assert [group.asset_ids for group in groups] == [(A, B), (B, C)]
    assert all(len(group.asset_ids) == 2 for group in groups)


def test_overlapping_cliques_preserve_every_edge_without_false_merge() -> None:
    edges = (
        edge(A, B, 99),
        edge(A, C, 98),
        edge(B, C, 97),
        edge(B, D, 96),
        edge(C, D, 95),
    )

    groups = cohesive_similarity_groups(edges)

    assert [group.asset_ids for group in groups] == [(A, B, C), (B, C, D)]
    accepted = {(item.asset_id_low, item.asset_id_high) for item in edges}
    covered = {
        (left, right)
        for group in groups
        for left, right in combinations(group.asset_ids, 2)
    }
    assert covered == accepted


def test_grouping_is_stable_across_edge_order_and_duplicate_edges() -> None:
    first = cohesive_similarity_groups(
        (edge(A, B, 96), edge(A, C, 97), edge(B, C, 98), edge(A, B, 99))
    )
    second = cohesive_similarity_groups(
        (edge(B, C, 98), edge(A, B, 99), edge(A, C, 97))
    )

    assert first == second
    assert first[0].minimum_similarity_percent == 97
    assert first[0].maximum_similarity_percent == 99


def test_invalid_or_noncanonical_edges_are_rejected() -> None:
    try:
        edge(B, A, 95)
    except ValueError as error:
        assert "canonical" in str(error)
    else:
        raise AssertionError("Expected noncanonical edge rejection")

    try:
        edge(A, B, 101)
    except ValueError as error:
        assert "between 0 and 100" in str(error)
    else:
        raise AssertionError("Expected invalid score rejection")

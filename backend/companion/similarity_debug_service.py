"""Read-only diagnostics for arbitrary cached similarity comparisons."""

from __future__ import annotations

import asyncio
from itertools import combinations
from uuid import UUID

from companion.discovery.similarity_candidates import (
    aspect_ratio_difference,
    perceptual_hash_distance,
)
from companion.similarity_debug_schema import (
    SimilarityDebugAdmission,
    SimilarityDebugAsset,
    SimilarityDebugGroup,
    SimilarityDebugLocalDiagnostics,
    SimilarityDebugPair,
    SimilarityDebugRequest,
    SimilarityDebugResponse,
)
from companion.similarity_detail_service import SimilarityDetailRepository
from companion.similarity_grouping import (
    SimilarityGroupingEdge,
    validated_similarity_groups,
)
from companion.similarity_repository import SimilarityRepository
from companion.similarity_search_repository import SimilaritySearchRepository


class SimilarityDebugService:
    """Explain the real cached pair scorer without running a library scan."""

    def __init__(
        self,
        features: SimilaritySearchRepository,
        similarity: SimilarityRepository,
        details: SimilarityDetailRepository | None = None,
    ) -> None:
        self._features = features
        self._similarity = similarity
        self._details = details

    async def compare(self, request: SimilarityDebugRequest) -> SimilarityDebugResponse:
        asset_ids = request.asset_ids
        current = await self._features.get_current_many(asset_ids)
        stored = await self._features.get_many(asset_ids)

        assets: list[SimilarityDebugAsset] = []
        for asset_id in asset_ids:
            feature = current.get(asset_id)
            raw = stored.get(asset_id)
            if feature is not None:
                assets.append(
                    SimilarityDebugAsset(
                        asset_id=asset_id,
                        evidence_state="current",
                        width=feature.width,
                        height=feature.height,
                        fingerprint_origin=feature.fingerprint_origin,
                        model_version=feature.model_version,
                        feature_version=feature.feature_version,
                        config_fingerprint=feature.config_fingerprint,
                    )
                )
                continue
            unavailable_reason = await self._features.unavailable_reason(asset_id)
            if unavailable_reason is not None:
                state = "unavailable"
                reason = unavailable_reason
            elif raw is not None:
                state = "missing_or_stale"
                reason = (
                    "Similarity evidence exists but is stale or incomplete for the "
                    "current source or evidence generation."
                )
            else:
                state = "missing_or_stale"
                reason = "No current complete similarity evidence is cached for this asset."
            assets.append(
                SimilarityDebugAsset(
                    asset_id=asset_id,
                    evidence_state=state,
                    reason=reason,
                    width=getattr(raw, "width", None),
                    height=getattr(raw, "height", None),
                    fingerprint_origin=getattr(raw, "fingerprint_origin", None),
                    model_version=getattr(raw, "model_version", None),
                    feature_version=getattr(raw, "feature_version", None),
                    config_fingerprint=getattr(raw, "config_fingerprint", None),
                )
            )

        requested_pairs = list(combinations(asset_ids, 2))
        scoreable_pairs = [
            (left, right)
            for left, right in requested_pairs
            if left in current and right in current
        ]
        scored = await self._similarity.reference_edges(
            [[left, right] for left, right in scoreable_pairs],
            current,
        )

        diagnostics: dict[tuple[UUID, UUID], object | None] = {}
        if self._details is not None and scoreable_pairs:
            results = await asyncio.gather(
                *(self._details.diagnostics(left, right) for left, right in scoreable_pairs)
            )
            diagnostics = dict(zip(scoreable_pairs, results, strict=True))

        pair_results: list[SimilarityDebugPair] = []
        grouping_edges: list[SimilarityGroupingEdge] = []
        for left, right in requested_pairs:
            left_feature = current.get(left)
            right_feature = current.get(right)
            evidence = scored.get((left, right))
            if left_feature is None or right_feature is None or evidence is None:
                pair_results.append(
                    SimilarityDebugPair(
                        asset_id_left=left,
                        asset_id_right=right,
                        evidence_available=False,
                        maximum_perceptual_distance=request.maximum_perceptual_distance,
                        perceptual_gate_pass=False,
                        maximum_aspect_difference=request.maximum_aspect_difference,
                        aspect_gate_pass=False,
                        candidate_pair_pass=False,
                        similarity_threshold=request.similarity_threshold,
                        similarity_threshold_pass=False,
                        would_pass_pair_pipeline=False,
                        exclusion_reason="asset_evidence_unavailable",
                    )
                )
                continue

            try:
                perceptual_distance = perceptual_hash_distance(
                    left_feature.perceptual_hash,
                    right_feature.perceptual_hash,
                )
            except ValueError:
                perceptual_distance = None
            if min(
                left_feature.width,
                left_feature.height,
                right_feature.width,
                right_feature.height,
            ) > 0:
                aspect_difference = aspect_ratio_difference(left_feature, right_feature)
            else:
                aspect_difference = None
            perceptual_pass = (
                perceptual_distance is not None
                and perceptual_distance <= request.maximum_perceptual_distance
            )
            aspect_pass = (
                aspect_difference is not None
                and aspect_difference <= request.maximum_aspect_difference
            )
            candidate_pass = perceptual_pass and aspect_pass
            threshold_pass = evidence.similarity_percent >= request.similarity_threshold
            pair_pass = candidate_pass and threshold_pass
            if perceptual_distance is None or aspect_difference is None:
                exclusion_reason = "invalid_candidate_feature"
            elif not perceptual_pass:
                exclusion_reason = "perceptual_distance"
            elif not aspect_pass:
                exclusion_reason = "aspect_ratio"
            elif not threshold_pass:
                exclusion_reason = "similarity_threshold"
            else:
                exclusion_reason = None

            stored_diagnostics = diagnostics.get((left, right))
            local = None
            if stored_diagnostics is not None:
                detail = stored_diagnostics.diagnostics
                local = SimilarityDebugLocalDiagnostics(
                    changed_percent=detail.changed_percent,
                    localized_changed_percent=detail.localized_changed_percent,
                    coherent_changed_percent=detail.coherent_changed_percent,
                    largest_changed_region_percent=detail.largest_changed_region_percent,
                    substantial_region_count=detail.substantial_region_count,
                    aligned_changed_percent=detail.aligned_changed_percent,
                    raw_similarity_percent=detail.raw_similarity_percent,
                    aligned_similarity_percent=detail.aligned_similarity_percent,
                    alignment_applied=detail.alignment_applied,
                    alignment_shift_percent=detail.alignment_shift_percent,
                    alignment_overlap_percent=detail.alignment_overlap_percent,
                    rows=detail.rows,
                    columns=detail.columns,
                    cells=[list(row) for row in detail.tile_changed_percents],
                    source=stored_diagnostics.source,
                )

            pair_results.append(
                SimilarityDebugPair(
                    asset_id_left=left,
                    asset_id_right=right,
                    evidence_available=True,
                    perceptual_distance=perceptual_distance,
                    maximum_perceptual_distance=request.maximum_perceptual_distance,
                    perceptual_gate_pass=perceptual_pass,
                    aspect_ratio_difference=aspect_difference,
                    maximum_aspect_difference=request.maximum_aspect_difference,
                    aspect_gate_pass=aspect_pass,
                    candidate_pair_pass=candidate_pass,
                    similarity_percent=evidence.similarity_percent,
                    structural_percent=evidence.structural_percent,
                    perceptual_percent=evidence.perceptual_percent,
                    color_percent=evidence.color_percent,
                    normalized_luminance_mae=evidence.normalized_luminance_mae,
                    normalized_luminance_rmse=evidence.normalized_luminance_rmse,
                    normalized_luminance_ssim=evidence.normalized_luminance_ssim,
                    dimensions_equal=evidence.dimensions_equal,
                    exact_thumbnail_match=evidence.exact_thumbnail_match,
                    detail_changed_percent=evidence.detail_changed_percent,
                    detail_source=evidence.detail_source,
                    similarity_threshold=request.similarity_threshold,
                    similarity_threshold_pass=threshold_pass,
                    would_pass_pair_pipeline=pair_pass,
                    exclusion_reason=exclusion_reason,
                    local_diagnostics=local,
                    model_version=evidence.model_version,
                    feature_version=evidence.feature_version,
                    comparison_version=evidence.comparison_version,
                )
            )
            if pair_pass:
                low, high = (left, right) if left.int < right.int else (right, left)
                grouping_edges.append(
                    SimilarityGroupingEdge(
                        asset_id_low=low,
                        asset_id_high=high,
                        similarity_percent=evidence.similarity_percent,
                    )
                )

        validated = validated_similarity_groups(
            tuple(grouping_edges),
            mode=request.validation_mode,
            threshold=request.similarity_threshold,
            preferred_anchor_asset_id=request.anchor_asset_id,
            max_link_depth=request.max_link_depth,
        )
        groups = [
            SimilarityDebugGroup(
                asset_ids=list(group.asset_ids),
                anchor_asset_id=group.anchor_asset_id,
                validation_mode=group.validation_mode,
                minimum_similarity_percent=group.minimum_similarity_percent,
                maximum_similarity_percent=group.maximum_similarity_percent,
                pair_count=group.pair_count,
                admission_evidence=[
                    SimilarityDebugAdmission(
                        asset_id=item.asset_id,
                        admitted_by_asset_id=item.admitted_by_asset_id,
                        admission_similarity_percent=item.admission_similarity_percent,
                        best_group_match_asset_id=item.best_group_match_asset_id,
                        best_group_match_similarity_percent=(
                            item.best_group_match_similarity_percent
                        ),
                        link_depth=item.link_depth,
                    )
                    for item in group.admission_evidence
                ],
            )
            for group in validated
        ]
        return SimilarityDebugResponse(
            assets=assets,
            pairs=pair_results,
            groups=groups,
            neighbor_allocation_simulated=False,
            note=(
                "All requested pairs are scored from current cached evidence. Perceptual "
                "distance, aspect ratio, score threshold, and grouping rules are evaluated "
                "with production logic. The library-wide maximum-neighbors allocation is "
                "not simulated because it depends on the complete library and processing order."
            ),
        )

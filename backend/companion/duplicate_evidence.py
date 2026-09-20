"""Duplicate discovery and evidence acquisition mixin."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Literal
from uuid import UUID

from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
)
from companion.discovery import (
    DiscoveredGroup,
)
from companion.duplicate_contracts import (
    metadata_float as _metadata_float,
)
from companion.duplicate_contracts import (
    metadata_int as _metadata_int,
)
from companion.duplicate_contracts import (
    same_normalized_pixels,
)
from companion.duplicate_schema import (
    CrossSourceDuplicateResult,
    DuplicateAdmissionEvidence,
    DuplicateAnalysisOptions,
    DuplicateMember,
    DuplicatePreservationEvidence,
    DuplicateSearchPage,
    DuplicateSimilarityEvidence,
    DuplicateSimilarityReferenceRequest,
    ExactDuplicateGroup,
)
from companion.group_decision import (
    DiscoverySource,
    GroupClassification,
)
from companion.integrity_repository import (
    preservation_feature_freshness,
)
from companion.models import (
    AssetImagePreservationFeatureRecord,
    AssetIntegrityReportRecord,
    AssetSimilaritySearchFeatureRecord,
)
from companion.similarity_generation import StaleSimilarityEvidenceEpochError
from companion.similarity_repository import (
    PairSimilarityEvidence,
    canonical_pair,
)

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"

logger = logging.getLogger(__name__)


class DuplicateEvidenceMixin:
    """Discover duplicate groups and enrich them with similarity evidence."""

    async def _live_groups(self) -> list[DiscoveredGroup]:
        return await self._discovery.discover()

    async def _groups_by_ids(self, group_ids: list[str]) -> list[DiscoveredGroup]:
        unique_ids = list(dict.fromkeys(group_ids))
        if not unique_ids:
            return []
        discover_groups = getattr(self._discovery, "discover_groups", None)
        if not callable(discover_groups):
            raise RuntimeError(
                "Targeted duplicate group lookup requires the persisted V2 projection"
            )
        return await discover_groups(unique_ids)

    async def _group_identities(
        self,
        *,
        group_ids: list[str] | None = None,
        stable_group_keys: list[str] | None = None,
    ) -> list[Any]:
        resolver = getattr(self._discovery, "resolve_identities", None)
        if not callable(resolver):
            raise RuntimeError(
                "Duplicate identity lookup requires the persisted V2 projection"
            )
        return await resolver(
            group_ids=group_ids,
            stable_group_keys=stable_group_keys,
        )

    async def result(
        self,
        options: DuplicateAnalysisOptions | None = None,
    ) -> CrossSourceDuplicateResult:
        options = await self._options(options)
        _, _, _, result = await self._snapshot(options)
        return result

    async def review(
        self,
        options: DuplicateAnalysisOptions | None = None,
    ) -> CrossSourceDuplicateResult:
        """Return live Immich groups and idempotently queue missing verification."""

        options = await self._options(options)
        groups, reports, features, result = await self._snapshot(options)
        include_preservation = self._similarity is not None
        candidates = self._verification_candidates(
            groups,
            options,
            include_preservation=include_preservation,
        )
        pending_count = len(
            self._pending_verification(
                groups,
                reports,
                features,
                options,
                include_preservation=include_preservation,
            )
        )
        task_id: UUID | None = None
        if pending_count and options.analyze_automatically:
            task_id = (await self.start(options)).task_id
        return result.model_copy(
            update={
                "analysis_task_id": task_id,
                "analysis_pending_count": pending_count,
                "analysis_candidate_count": len(candidates),
                "analysis_cached_count": len(candidates) - pending_count,
            }
        )

    async def review_page(
        self,
        options: DuplicateAnalysisOptions | None = None,
        *,
        page: int = 1,
        page_size: int = 6,
        source: Literal["both", "immich", "similarity"] = "both",
        sort: Literal[
            "reclaimable", "members", "similarity", "date", "discovered"
        ] = "reclaimable",
        direction: Literal["asc", "desc"] = "desc",
        state: Literal[
            "all",
            "needs_review",
            "auto_ready",
            "blocked",
            "actionable",
            "needs_decisions",
        ] = "all",
    ) -> DuplicateSearchPage:
        """Return one database-backed page and hydrate only its members/evidence."""

        options = await self._options(options)
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        discover_page = getattr(self._discovery, "discover_page", None)
        if not callable(discover_page):
            raise RuntimeError(
                "Paged duplicate review requires the persisted V2 projection"
            )
        discovered = await discover_page(
            page=page,
            page_size=page_size,
            source=source,
            sort=sort,
            direction=direction,
            state=state,
        )
        groups = discovered.groups
        total = discovered.total
        resolved_page = discovered.page
        resolved_page_size = discovered.page_size
        pages = discovered.pages

        _, _, _, result = await self._snapshot_groups(groups, options)
        return DuplicateSearchPage(
            items=result.groups,
            total=total,
            page=resolved_page,
            page_size=resolved_page_size,
            pages=pages,
        )

    async def review_selected_page(
        self,
        options: DuplicateAnalysisOptions | None = None,
        *,
        page: int = 1,
        page_size: int = 6,
        source: Literal["both", "immich", "similarity"] = "both",
        sort: Literal[
            "reclaimable", "members", "similarity", "date", "discovered"
        ] = "reclaimable",
        direction: Literal["asc", "desc"] = "desc",
    ) -> DuplicateSearchPage:
        """Return one page from the persisted workspace selection only."""

        resolved_options = await self._options(options)
        workspace = await self.workspace(resolved_options)
        discover_selected_page = getattr(
            self._discovery,
            "discover_selected_page",
            None,
        )
        if not callable(discover_selected_page):
            raise RuntimeError(
                "Selected duplicate paging requires the persisted V2 projection"
            )
        discovered = await discover_selected_page(
            workspace.selected_group_ids,
            page=max(1, page),
            page_size=max(1, min(page_size, 100)),
            source=source,
            sort=sort,
            direction=direction,
        )
        _, _, _, result = await self._snapshot_groups(
            discovered.groups,
            resolved_options,
        )
        return DuplicateSearchPage(
            items=result.groups,
            total=discovered.total,
            page=discovered.page,
            page_size=discovered.page_size,
            pages=discovered.pages,
        )

    async def _snapshot(
        self,
        options: DuplicateAnalysisOptions,
    ) -> tuple[
        list[DiscoveredGroup],
        dict[UUID, AssetIntegrityReportRecord],
        dict[UUID, AssetImagePreservationFeatureRecord],
        CrossSourceDuplicateResult,
    ]:
        return await self._snapshot_groups(await self._live_groups(), options)

    @staticmethod
    def _stable_similarity_source(group: DiscoveredGroup) -> DiscoveredGroup:
        """Keep the immutable scan anchor as the default comparison reference."""

        anchor = (
            group.similarity_validation.anchor_asset_id
            if group.similarity_validation is not None
            else None
        )
        return replace(
            group,
            assets=tuple(
                sorted(
                    group.assets,
                    key=lambda asset: (asset.id != anchor, asset.id.int),
                )
            ),
        )

    async def _current_reference_edges(
        self,
        groups: list[list[UUID]],
        features: dict[UUID, AssetSimilaritySearchFeatureRecord],
    ) -> dict[tuple[UUID, UUID], PairSimilarityEvidence] | None:
        """Return current live edges, or None when the evidence generation is stale."""

        if self._similarity is None:
            return {}
        try:
            return await self._similarity.reference_edges(groups, features)
        except StaleSimilarityEvidenceEpochError:
            # Code-generation changes intentionally fence durable Appearance writers until
            # rebuild. Duplicate review is read-only, so surface the page without treating
            # evidence from the incompatible generation as current.
            logger.info(
                "Similarity evidence generation is stale; serving duplicate review "
                "without Appearance evidence until rebuild."
            )
            return None

    async def _persisted_scan_edges(
        self,
        groups: list[DiscoveredGroup],
        features: dict[UUID, AssetSimilaritySearchFeatureRecord],
        live_edges: dict[tuple[UUID, UUID], PairSimilarityEvidence],
    ) -> dict[tuple[UUID, UUID], PairSimilarityEvidence]:
        """Reuse the exact pair evidence that admitted members into the current scan.

        Missing scan edges (for example a linked member below the anchor threshold)
        deliberately fall back to the live current-pipeline comparison.
        """

        if self._scan_evidence is None:
            return {}
        source_identities = {
            asset_id: feature.source_identity for asset_id, feature in features.items()
        }
        by_scan: dict[UUID, list[DiscoveredGroup]] = {}
        for group in groups:
            evidence = next(
                (
                    item
                    for item in group.evidence
                    if item.discovery_source is DiscoverySource.COMPANION_SIMILARITY
                ),
                None,
            )
            raw_scan_id = evidence.metadata.get("scan_id") if evidence is not None else None
            if raw_scan_id is None:
                continue
            try:
                scan_id = UUID(raw_scan_id)
            except (TypeError, ValueError):
                continue
            by_scan.setdefault(scan_id, []).append(group)

        exposed: dict[tuple[UUID, UUID], PairSimilarityEvidence] = {}
        for scan_id, scan_groups in by_scan.items():
            asset_ids = list(
                dict.fromkeys(
                    asset.id for group in scan_groups for asset in group.assets
                )
            )
            persisted = await self._scan_evidence.pair_evidence(
                scan_id,
                asset_ids,
                source_identities=source_identities,
            )
            for group in scan_groups:
                if len(group.assets) < 2:
                    continue
                reference_id = group.assets[0].id
                for member in group.assets[1:]:
                    key = (reference_id, member.id)
                    evidence = persisted.get(canonical_pair(*key))
                    if evidence is None:
                        continue
                    live = live_edges.get(key)
                    # Pair rows persist the validated source kind, while live detail
                    # records carry request-relative rendition dimensions. Keep the
                    # historical scan score but enrich it with those dimensions.
                    if (
                        live is not None
                        and evidence.detail_source is not None
                        and live.detail_source is not None
                        and str(live.detail_source) == evidence.detail_source
                    ):
                        evidence = replace(evidence, detail_source=live.detail_source)
                    exposed[key] = evidence
        return exposed

    async def _snapshot_groups(
        self,
        groups: list[DiscoveredGroup],
        options: DuplicateAnalysisOptions,
    ) -> tuple[
        list[DiscoveredGroup],
        dict[UUID, AssetIntegrityReportRecord],
        dict[UUID, AssetImagePreservationFeatureRecord],
        CrossSourceDuplicateResult,
    ]:
        report_ids = [
            asset.id
            for group in groups
            for asset in group.assets
            if asset.library_id is not None or options.verify_upload_streams
        ]
        reports = await self._reports.get_many(report_ids)
        image_ids = [
            asset.id
            for group in groups
            for asset in group.assets
            if asset.asset_type == "IMAGE" and not asset.is_offline
        ]
        source_assets = {asset.id: asset for group in groups for asset in group.assets}

        loaded_preservation = await self._reports.get_preservation_features(image_ids)
        preservation = {
            asset_id: feature
            for asset_id, feature in loaded_preservation.items()
            if preservation_feature_freshness(feature, source_assets[asset_id]) == "current"
        }
        search_features = (
            await self._search_features.get_current_many(image_ids)
            if self._similarity is not None and self._search_features is not None
            else {}
        )

        result = self.assemble(groups, reports, options, self._immich)
        if self._similarity is not None:
            similarity_groups = [self._stable_similarity_source(group) for group in groups]
            live_edges = await self._current_reference_edges(
                [[asset.id for asset in group.assets] for group in similarity_groups],
                search_features,
            )
            if live_edges is not None:
                scan_edges = await self._persisted_scan_edges(
                    similarity_groups,
                    search_features,
                    live_edges,
                )
                edges = {**live_edges, **scan_edges}
                result = self._apply_similarity(
                    result,
                    similarity_groups,
                    edges,
                    search_features,
                    preservation,
                )
        if self._reviews is not None:
            result = await self._apply_review_states(result)
        return groups, reports, preservation, result

    async def similarity_reference(
        self,
        group_id: str,
        request: DuplicateSimilarityReferenceRequest,
    ) -> ExactDuplicateGroup:
        """Return one live group relative to a requested member-owned reference."""

        if self._similarity is None or self._search_features is None:
            raise RuntimeError("Duplicate similarity persistence is unavailable")
        source = next(iter(await self._groups_by_ids([group_id])), None)
        if source is None:
            raise ActionPlanNotFoundError("The duplicate group is no longer available")
        members = {asset.id: asset for asset in source.assets}
        if request.reference_asset_id not in members:
            raise ActionPlanConflictError(
                "The similarity reference is not a member of this duplicate group"
            )
        options = await self._options(None)
        report_ids = [
            asset.id
            for asset in source.assets
            if asset.library_id is not None or options.verify_upload_streams
        ]
        reports = await self._reports.get_many(report_ids)
        image_assets = [
            asset
            for asset in source.assets
            if asset.asset_type == "IMAGE" and not asset.is_offline
        ]
        image_ids = [asset.id for asset in image_assets]
        features = await self._search_features.get_current_many(image_ids)
        loaded_preservation = await self._reports.get_preservation_features(image_ids)
        preservation = {
            asset.id: loaded_preservation[asset.id]
            for asset in image_assets
            if asset.id in loaded_preservation
            and preservation_feature_freshness(loaded_preservation[asset.id], asset)
            == "current"
        }

        ordered_ids = [
            request.reference_asset_id,
            *(asset.id for asset in source.assets if asset.id != request.reference_asset_id),
        ]
        result = self.assemble([source], reports, options, self._immich)

        stable_source = self._stable_similarity_source(source)
        stable_ids = [asset.id for asset in stable_source.assets]
        stable_live_edges = await self._similarity.reference_edges([stable_ids], features)
        stable_scan_edges = await self._persisted_scan_edges(
            [stable_source],
            features,
            stable_live_edges,
        )
        stable_edges = {**stable_live_edges, **stable_scan_edges}
        result = self._apply_similarity(
            result,
            [stable_source],
            stable_edges,
            features,
            preservation,
        )
        if ordered_ids == stable_ids:
            if self._reviews is not None:
                result = await self._apply_review_states(result)
            return result.groups[0]

        edges = await self._similarity.reference_edges([ordered_ids], features)
        reordered_source = replace(
            source,
            assets=tuple(members[asset_id] for asset_id in ordered_ids),
        )
        result = self._apply_similarity(
            result,
            [reordered_source],
            edges,
            features,
            preservation,
            update_group_contract=False,
        )
        if self._reviews is not None:
            result = await self._apply_review_states(result)
        return result.groups[0]

    @staticmethod
    def _apply_similarity(
        result: CrossSourceDuplicateResult,
        source_groups: list[DiscoveredGroup],
        edges: dict[tuple[UUID, UUID], PairSimilarityEvidence],
        features: dict[UUID, AssetSimilaritySearchFeatureRecord],
        preservation_features: dict[UUID, AssetImagePreservationFeatureRecord],
        *,
        update_group_contract: bool = True,
    ) -> CrossSourceDuplicateResult:
        source_by_id = {group.group_id: group for group in source_groups}
        updated_groups: list[ExactDuplicateGroup] = []
        for group in result.groups:
            source = source_by_id[group.group_id]
            if not source.assets:
                updated_groups.append(group)
                continue
            reference = source.assets[0]
            source_members = {asset.id: asset for asset in source.assets}
            similarity_source = next(
                (
                    evidence
                    for evidence in source.evidence
                    if evidence.discovery_source is DiscoverySource.COMPANION_SIMILARITY
                ),
                None,
            )
            similarity_metadata = similarity_source.metadata if similarity_source else {}
            validation = source.similarity_validation
            admission_by_id = (
                {item.asset_id: item for item in validation.admission_evidence}
                if validation is not None
                else {}
            )
            members: list[DuplicateMember] = []
            reference_preservation = preservation_features.get(reference.id)
            for member in group.members:
                source_member = source_members[member.id]
                edge = edges.get((reference.id, member.id))
                feature = features.get(member.id)
                preservation_feature = preservation_features.get(member.id)
                exact_pixel_match = same_normalized_pixels(
                    reference_preservation,
                    preservation_feature,
                )
                if member.id == reference.id:
                    similarity = DuplicateSimilarityEvidence(
                        state="reference",
                        reference_asset_id=reference.id,
                        similarity_percent=100.0,
                        structural_percent=100.0,
                        perceptual_percent=100.0,
                        color_percent=100.0,
                        normalized_luminance_mae=0.0 if feature is not None else None,
                        normalized_luminance_rmse=0.0 if feature is not None else None,
                        normalized_luminance_ssim=1.0 if feature is not None else None,
                        aspect_ratio_difference=0.0 if feature is not None else None,
                        dimensions_equal=True if feature is not None else None,
                        exact_thumbnail_match=True if feature is not None else None,
                        exact_pixel_match=(exact_pixel_match if preservation_feature else None),
                        model_version=feature.model_version if feature is not None else None,
                        feature_version=feature.feature_version if feature is not None else None,
                    )
                elif edge is not None:
                    similarity = DuplicateSimilarityEvidence(
                        state="current",
                        reference_asset_id=reference.id,
                        similarity_percent=edge.similarity_percent,
                        structural_percent=edge.structural_percent,
                        perceptual_percent=edge.perceptual_percent,
                        color_percent=edge.color_percent,
                        normalized_luminance_mae=edge.normalized_luminance_mae,
                        normalized_luminance_rmse=edge.normalized_luminance_rmse,
                        normalized_luminance_ssim=edge.normalized_luminance_ssim,
                        aspect_ratio_difference=edge.aspect_ratio_difference,
                        dimensions_equal=edge.dimensions_equal,
                        exact_thumbnail_match=edge.exact_thumbnail_match,
                        exact_pixel_match=exact_pixel_match,
                        detail_changed_percent=edge.detail_changed_percent,
                        detail_source=edge.detail_source,
                        model_version=edge.model_version,
                        feature_version=edge.feature_version,
                        comparison_version=edge.comparison_version,
                    )
                else:
                    similarity = DuplicateSimilarityEvidence(
                        state=(
                            "unavailable"
                            if source_member.is_offline or source_member.asset_type != "IMAGE"
                            else "pending"
                        ),
                        reference_asset_id=reference.id,
                    )
                preservation = (
                    DuplicatePreservationEvidence(
                        origin=preservation_feature.origin,
                        pixel_normalization_version=(
                            preservation_feature.pixel_normalization_version
                        ),
                        pixel_sha256=preservation_feature.pixel_sha256,
                        decoded_width=preservation_feature.width,
                        decoded_height=preservation_feature.height,
                        bit_depth=preservation_feature.bit_depth,
                        channel_count=preservation_feature.channel_count,
                        has_alpha=preservation_feature.has_alpha,
                        color_space=preservation_feature.color_space,
                        orientation=preservation_feature.orientation,
                        icc_profile_present=preservation_feature.icc_profile_present,
                        has_exif=preservation_feature.has_exif,
                        has_capture_time=preservation_feature.has_capture_time,
                        has_camera_info=preservation_feature.has_camera_info,
                        has_gps=preservation_feature.has_gps,
                        has_orientation_metadata=(
                            preservation_feature.has_orientation_metadata
                        ),
                        metadata_richness=preservation_feature.metadata_richness,
                    )
                    if preservation_feature is not None
                    else None
                )
                admission_source = admission_by_id.get(member.id)
                admission = (
                    DuplicateAdmissionEvidence(
                        admitted_by_asset_id=admission_source.admitted_by_asset_id,
                        admission_similarity_percent=(
                            admission_source.admission_similarity_percent
                        ),
                        best_group_match_asset_id=(admission_source.best_group_match_asset_id),
                        best_group_match_similarity_percent=(
                            admission_source.best_group_match_similarity_percent
                        ),
                        link_depth=admission_source.link_depth,
                        model_version=similarity_metadata.get("model_version", "unknown"),
                        feature_version=_metadata_int(similarity_metadata, "feature_version") or 0,
                        comparison_version=_metadata_int(similarity_metadata, "comparison_version")
                        or 0,
                        config_fingerprint=similarity_metadata.get("config_fingerprint", "unknown"),
                    )
                    if admission_source is not None
                    else None
                )
                members.append(
                    member.model_copy(
                        update={
                            "similarity": similarity,
                            "admission": admission,
                            "preservation": preservation,
                        }
                    )
                )

            def member_sort_key(
                item: DuplicateMember,
                reference_id: UUID = reference.id,
            ) -> tuple[bool, float, str]:
                similarity_percent = (
                    item.similarity.similarity_percent
                    if item.similarity is not None
                    else None
                )
                return (
                    item.id != reference_id,
                    -(
                        similarity_percent
                        if similarity_percent is not None
                        else float("-inf")
                    ),
                    str(item.id),
                )

            members.sort(key=member_sort_key)
            group_update: dict[str, object] = {
                "members": members,
                "reference_asset_id": reference.id,
            }
            pair_evidence = [
                member.similarity
                for member in members
                if member.similarity is not None and member.similarity.state == "current"
            ]
            if update_group_contract:
                score_value = similarity_metadata.get("minimum_similarity_percent")
                try:
                    stable_score = float(score_value) if score_value is not None else None
                except ValueError:
                    stable_score = None
                if stable_score is None:
                    scores = [
                        evidence.similarity_percent
                        for evidence in pair_evidence
                        if evidence.similarity_percent is not None
                    ]
                    stable_score = min(scores) if scores else None
                representative = pair_evidence[0] if pair_evidence else None

                group_update.update(
                    {
                        "group_similarity_percent": stable_score,
                        "similarity_engine": (
                            "appearance"
                            if stable_score is not None or representative is not None
                            else None
                        ),
                        "similarity_model_version": (
                            similarity_metadata.get("model_version")
                            or (representative.model_version if representative else None)
                        ),
                        "similarity_feature_version": (
                            _metadata_int(similarity_metadata, "feature_version")
                            or (representative.feature_version if representative else None)
                        ),
                        "similarity_comparison_version": (
                            _metadata_int(similarity_metadata, "comparison_version")
                            or (representative.comparison_version if representative else None)
                        ),
                        "similarity_validation_mode": (
                            validation.validation_mode if validation is not None else None
                        ),
                        "similarity_threshold_percent": (
                            _metadata_float(similarity_metadata, "scan_threshold_percent")
                        ),
                    }
                )
            if (
                update_group_contract
                and source.discovery_source is DiscoverySource.COMPANION_SIMILARITY
            ):
                threshold = similarity_metadata.get("scan_threshold_percent")
                score = group_update.get("group_similarity_percent")
                if isinstance(score, int | float):
                    classification = (
                        GroupClassification.EXACT_PIXELS.value
                        if pair_evidence
                        and all(evidence.exact_pixel_match for evidence in pair_evidence)
                        else GroupClassification.LIKELY_SAME.value
                        if score >= 98
                        else GroupClassification.SIMILAR.value
                    )
                    threshold_detail = f" at a {threshold}% scan threshold" if threshold else ""
                    group_update.update(
                        {
                            "classification": classification,
                            "reason": (
                                f"Companion found a {score:.1f}% visual match"
                                f"{threshold_detail}. Review it manually before acting."
                            ),
                        }
                    )
                group_update.update(
                    {
                        "auto_resolvable": False,
                        "auto_selected": False,
                        "recommended_action": "none",
                        "recommended_primary_asset_id": None,
                        "keeper_asset_id": None,
                        "effective_action": "none",
                        "effective_primary_asset_id": None,
                        "action_source": "none",
                        "primary_source": "none",
                        "recommendation_reason_codes": ["non_exact_match"],
                    }
                )
            updated_groups.append(group.model_copy(update=group_update))
        return result.model_copy(update={"groups": updated_groups})

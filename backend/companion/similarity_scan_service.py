"""Coordinated, bounded whole-library visual similarity scans."""

from __future__ import annotations

import asyncio
import heapq
import inspect
import json
from hashlib import sha256
from time import perf_counter
from typing import Any
from uuid import UUID

from companion.discovery import (
    CANDIDATE_INDEX_VERSION,
    BoundedSimilarityCandidateIndex,
    SimilarityCandidateStats,
)
from companion.duplicate_schema import (
    SimilarityScanRequest,
    SimilarityScanSummary,
    SimilarityScanTaskStart,
)
from companion.integrity_service import INTEGRITY_TASK_TYPE
from companion.runtime_metrics import process_memory_snapshot
from companion.similarity_grouping import (
    SIMILARITY_GROUPING_VERSION,
    SimilarityGroupingEdge,
    validated_similarity_groups,
)
from companion.similarity_index_service import SimilarityIndexMaintainer
from companion.similarity_repository import (
    SIMILARITY_COMPARISON_VERSION,
    SimilarityRepository,
    canonical_pair,
)
from companion.similarity_scan_repository import (
    SimilarityScanPair,
    SimilarityScanParameters,
    SimilarityScanRepository,
)
from companion.similarity_search_features import (
    SEARCH_CONFIG_FINGERPRINT,
    SEARCH_FEATURE_VERSION,
    SEARCH_MODEL_VERSION,
)
from companion.similarity_search_repository import SimilaritySearchRepository
from companion.task_coordinator import (
    PermanentTaskError,
    TaskCancelledError,
    TaskContext,
    TaskCoordinator,
    TaskPausedError,
)
from companion.task_schema import TaskResult

SIMILARITY_SCAN_TASK_TYPE = "similarity_scan"
SIMILARITY_INDEX_BATCH_SIZE = 1_000
SIMILARITY_SCORE_BATCH_SIZE = 500


class SimilarityScanAlreadyRunningError(RuntimeError):
    """Raised when an incompatible whole-library scan is already active."""


def _accepts_parameter(callable_object: object, parameter: str) -> bool:
    """Keep lightweight adapters compatible while real repositories carry epochs."""

    try:
        return parameter in inspect.signature(callable_object).parameters
    except (TypeError, ValueError):
        return True


def _epoch_kwargs(callable_object: object, evidence_epoch: int | None) -> dict[str, int]:
    if evidence_epoch is None or not _accepts_parameter(callable_object, "evidence_epoch"):
        return {}
    return {"evidence_epoch": evidence_epoch}


def _request_key(request: SimilarityScanRequest) -> str:
    raw = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _feature_snapshot_digest():
    digest = sha256()
    digest.update(f"candidate-index-v{CANDIDATE_INDEX_VERSION}\n".encode())
    return digest


def _update_feature_snapshot_digest(digest, feature: Any) -> None:
    digest.update(
        (
            f"{feature.asset_id}:{feature.model_version}:{feature.feature_version}:"
            f"{feature.source_identity}:{feature.width}:{feature.height}:"
            f"{feature.perceptual_hash}\n"
        ).encode()
    )


def _feature_snapshot_key(features: list[Any]) -> str:
    """Fingerprint ordered candidate inputs used by a durable scan checkpoint."""

    digest = _feature_snapshot_digest()
    for feature in sorted(features, key=lambda item: item.asset_id.int):
        _update_feature_snapshot_digest(digest, feature)
    return digest.hexdigest()


def _missing_reference_groups(
    matches: list[SimilarityScanPair],
    request: SimilarityScanRequest,
) -> list[list[UUID]]:
    """Plan only final-group members that lack a retained direct reference edge."""

    if not matches:
        return []
    validated = validated_similarity_groups(
        tuple(
            SimilarityGroupingEdge(
                match.asset_id_low,
                match.asset_id_high,
                match.evidence.similarity_percent,
            )
            for match in matches
        ),
        mode=request.validation_mode,
        threshold=request.similarity_threshold,
        preferred_anchor_asset_id=request.anchor_asset_id,
        max_link_depth=request.max_link_depth,
    )
    retained_pairs = {
        canonical_pair(match.asset_id_low, match.asset_id_high) for match in matches
    }
    missing_groups: list[list[UUID]] = []
    for group in validated:
        missing_members = [
            asset_id
            for asset_id in group.asset_ids
            if asset_id != group.anchor_asset_id
            and canonical_pair(group.anchor_asset_id, asset_id) not in retained_pairs
        ]
        if missing_members:
            missing_groups.append([group.anchor_asset_id, *missing_members])
    return missing_groups


class SimilarityScanService:
    """Submit idempotent similarity scans through the shared coordinator."""

    def __init__(
        self,
        tasks: TaskCoordinator,
        scans: SimilarityScanRepository,
    ) -> None:
        self._tasks = tasks
        self._scans = scans

    async def start(self, request: SimilarityScanRequest) -> SimilarityScanTaskStart:
        key = _request_key(request)
        task = await self._tasks.find_active(SIMILARITY_SCAN_TASK_TYPE, key)
        if task is None:
            active = await self._tasks.find_active_by_type(SIMILARITY_SCAN_TASK_TYPE)
            if active is not None:
                raise SimilarityScanAlreadyRunningError(
                    "A similarity scan with different settings is already active."
                )
            task = await self._tasks.submit(
                SIMILARITY_SCAN_TASK_TYPE,
                request.model_dump(mode="json"),
                priority=45,
                lane_key=INTEGRITY_TASK_TYPE,
                deduplication_key=key,
            )
            await self._tasks.start()
        return SimilarityScanTaskStart(task_id=task.id)

    async def latest(self) -> SimilarityScanSummary | None:
        run = await self._scans.latest_completed_summary()
        if run is None:
            return None
        return SimilarityScanSummary(
            scan_id=run.id,
            similarity_threshold=run.parameters.similarity_threshold,
            validation_mode=run.parameters.validation_mode,
            max_link_depth=run.parameters.max_link_depth,
            anchor_asset_id=run.parameters.anchor_asset_id,
            scope=run.parameters.scope,
            model_version=run.parameters.model_version,
            feature_version=run.parameters.feature_version,
            comparison_version=run.parameters.comparison_version,
            config_fingerprint=run.parameters.config_fingerprint,
            grouping_version=run.parameters.grouping_version,
            asset_count=run.asset_count,
            candidate_count=run.candidate_count,
            match_count=run.match_count,
            maximum_matches=run.parameters.maximum_matches,
            result_limit_reached=run.result_limit_reached,
            completed_at=run.completed_at,
        )


class SimilarityScanTaskHandler:
    """Discover and score pair candidates without unbounded fan-out."""

    task_type = SIMILARITY_SCAN_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1
    supports_pause = True

    def __init__(
        self,
        features: SimilaritySearchRepository,
        similarity: SimilarityRepository,
        scans: SimilarityScanRepository,
        indexer: SimilarityIndexMaintainer | None = None,
    ) -> None:
        self._features = features
        self._similarity = similarity
        self._scans = scans
        self._indexer = indexer

    async def _candidate_feature_batches(self):
        reader = getattr(self._features, "iter_current_candidates", None)
        if callable(reader):
            async for batch in reader(batch_size=SIMILARITY_INDEX_BATCH_SIZE):
                yield batch
            return
        values = sorted(
            await self._features.list_current(),
            key=lambda feature: feature.asset_id.int,
        )
        for offset in range(0, len(values), SIMILARITY_INDEX_BATCH_SIZE):
            yield values[offset : offset + SIMILARITY_INDEX_BATCH_SIZE]

    async def _candidate_snapshot(self) -> tuple[int, str]:
        digest = _feature_snapshot_digest()
        count = 0
        async for batch in self._candidate_feature_batches():
            for feature in batch:
                _update_feature_snapshot_digest(digest, feature)
                count += 1
        return count, digest.hexdigest()

    async def _current_features(self, asset_ids: list[UUID]) -> dict[UUID, Any]:
        unique_ids = list(dict.fromkeys(asset_ids))
        reader = getattr(self._features, "get_current_many", None)
        if callable(reader):
            return await reader(unique_ids)
        values = await self._features.list_current()
        requested = set(unique_ids)
        return {feature.asset_id: feature for feature in values if feature.asset_id in requested}

    async def _enrich_reference_groups(
        self,
        groups: list[list[UUID]],
        *,
        evidence_epoch: int | None,
    ) -> int:
        pair_groups = [
            [group[0], member]
            for group in groups
            for member in group[1:]
        ]
        enriched_count = 0
        for offset in range(0, len(pair_groups), SIMILARITY_SCORE_BATCH_SIZE):
            batch = pair_groups[offset : offset + SIMILARITY_SCORE_BATCH_SIZE]
            asset_ids = list(
                dict.fromkeys(asset_id for pair in batch for asset_id in pair)
            )
            features = await self._current_features(asset_ids)
            if len(features) != len(asset_ids):
                raise PermanentTaskError(
                    "Similarity scan coverage changed during reference enrichment; "
                    "retry after asset synchronization settles."
                )
            enriched = await self._similarity.reference_edges(
                batch,
                features,
                **_epoch_kwargs(self._similarity.reference_edges, evidence_epoch),
            )
            enriched_count += len(enriched)
        return enriched_count

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        started = perf_counter()
        request = SimilarityScanRequest.model_validate(payload)
        parameters = SimilarityScanParameters(
            model_version=SEARCH_MODEL_VERSION,
            feature_version=SEARCH_FEATURE_VERSION,
            comparison_version=SIMILARITY_COMPARISON_VERSION,
            config_fingerprint=SEARCH_CONFIG_FINGERPRINT,
            grouping_version=SIMILARITY_GROUPING_VERSION,
            validation_mode=request.validation_mode,
            max_link_depth=request.max_link_depth,
            anchor_asset_id=request.anchor_asset_id,
            scope=request.scope,
            similarity_threshold=request.similarity_threshold,
            maximum_perceptual_distance=request.maximum_perceptual_distance,
            maximum_aspect_difference=request.maximum_aspect_difference,
            maximum_neighbors_per_asset=request.maximum_neighbors_per_asset,
            maximum_matches=request.maximum_matches,
        )
        candidate_stats = SimilarityCandidateStats()
        scan_id = None
        evidence_epoch: int | None = None
        index_counters: dict[str, int] = {}
        excluded_ids: list[UUID] = []
        fingerprint_failure_reasons: dict[UUID, str] = {}
        candidate_discovery_milliseconds = 0
        pair_scoring_milliseconds = 0
        result_limit_reached = False

        def telemetry(**values: int) -> dict[str, int]:
            memory = process_memory_snapshot()
            return {
                **index_counters,
                **values,
                "candidate_index_nodes_visited": candidate_stats.index_nodes_visited,
                "candidate_raw_neighbor_matches": candidate_stats.raw_neighbor_matches,
                "candidate_peak_query_matches": candidate_stats.peak_query_matches,
                "candidate_peak_active_index_assets": candidate_stats.peak_active_index_assets,
                "rss_bytes": memory.rss_bytes,
                "rss_peak_bytes": memory.peak_rss_bytes,
                "elapsed_milliseconds": round((perf_counter() - started) * 1000),
                "candidate_discovery_milliseconds": candidate_discovery_milliseconds,
                "pair_scoring_milliseconds": pair_scoring_milliseconds,
            }

        try:
            await context.ensure_active()
            epoch_getter = getattr(self._scans, "current_evidence_epoch", None)
            evidence_epoch = await epoch_getter() if epoch_getter is not None else None
            task = getattr(context, "task", None)
            task_id = getattr(task, "id", None)
            scan_id = await self._scans.prepare(parameters, scan_id=task_id)
            completed = await self._scans.completed_summary(scan_id)
            if completed is not None:
                recovered_limit_reached = getattr(completed, "result_limit_reached", None)
                return TaskResult(
                    summary={
                        "scan_id": str(scan_id),
                        "similarity_threshold": request.similarity_threshold,
                        "validation_mode": request.validation_mode,
                        "anchor_asset_id": (
                            str(request.anchor_asset_id) if request.anchor_asset_id else None
                        ),
                        "scope": request.scope,
                        "result_limit_reached": recovered_limit_reached,
                        "maximum_matches": request.maximum_matches,
                        "recovered_completed_scan": True,
                    },
                    counters=telemetry(
                        assets_with_current_features=completed.asset_count,
                        candidate_pairs=completed.candidate_count,
                        pairs_scored=completed.candidate_count,
                        matches_retained=completed.match_count,
                        retained_match_limit=request.maximum_matches,
                        **(
                            {"result_limit_reached": int(recovered_limit_reached)}
                            if recovered_limit_reached is not None
                            else {}
                        ),
                    ),
                )
            if self._indexer is not None:
                (
                    coverage,
                    indexed,
                    unavailable,
                    retry_attempted,
                    fingerprint_failure_reasons,
                ) = await self._indexer.maintain(context, progress_ceiling=30)
                index_counters = {
                    "eligible_images": coverage.eligible_count,
                    "current_fingerprints": coverage.current_count,
                    "missing_fingerprints": coverage.missing_count,
                    "stale_fingerprints": coverage.stale_count,
                    "fingerprints_completed": indexed,
                    "fingerprints_unavailable": unavailable,
                    **(self._indexer.metrics() if hasattr(self._indexer, "metrics") else {}),
                }
                if not coverage.complete:
                    remaining = coverage.missing_count + coverage.stale_count
                    pending: list[UUID] = []
                    after = None
                    while len(pending) <= remaining:
                        page = await self._features.list_work(
                            after_asset_id=after,
                            limit=min(1000, remaining + 1 - len(pending)),
                        )
                        if not page:
                            break
                        pending.extend(page)
                        after = page[-1]
                    if len(pending) != remaining or not set(pending).issubset(retry_attempted):
                        raise PermanentTaskError(
                            "Similarity scan coverage changed during fingerprint retry; "
                            "retry after asset synchronization settles."
                        )
                    excluded_ids = pending
                    index_counters["fingerprints_excluded_after_retry"] = len(pending)
            asset_count, snapshot_key = await self._candidate_snapshot()
            if self._indexer is not None and asset_count != coverage.current_count:
                raise PermanentTaskError(
                    "Similarity scan coverage changed during fingerprint snapshot; "
                    "retry after asset synchronization settles."
                )
            if self._indexer is not None and coverage.eligible_count > 0 and not asset_count:
                raise PermanentTaskError(
                    "No current library fingerprints are available for candidate search."
                )

            saved = dict(getattr(task, "checkpoint", {}) or {})
            same_snapshot = saved.get("feature_snapshot") == snapshot_key
            saved_phase = str(saved.get("phase", "")) if same_snapshot else ""
            resume_index = (
                min(asset_count, int(saved.get("candidate_assets_processed", 0)))
                if saved_phase in ("candidate_index", "scoring")
                else 0
            )
            resume_scored = (
                max(0, int(saved.get("pairs_scored", 0)))
                if saved_phase == "scoring"
                else 0
            )
            candidate_pair_limit = (
                asset_count * request.maximum_neighbors_per_asset // 2
            )
            if saved_phase != "scoring":
                await context.checkpoint(
                    checkpoint={
                        "phase": "candidate_index",
                        "scan_id": str(scan_id),
                        "feature_snapshot": snapshot_key,
                        "candidate_assets_processed": resume_index,
                        "pairs_scored": 0,
                    },
                    counters=telemetry(
                        assets_with_current_features=asset_count,
                        candidate_assets_processed=resume_index,
                        candidate_pairs=0,
                        candidate_pair_limit=candidate_pair_limit,
                        pairs_scored=0,
                    ),
                    progress={
                        "phase": "similarity_candidates",
                        "completed": resume_index,
                        "total": asset_count,
                        "percent": round(
                            35 + 10 * resume_index / max(1, asset_count), 1
                        ),
                        "detail": (
                            f"Resuming candidate index after {resume_index} fingerprints…"
                            if resume_index
                            else f"Indexing {asset_count} visual fingerprints…"
                        ),
                    },
                )

            candidate_index = BoundedSimilarityCandidateIndex(
                maximum_perceptual_distance=request.maximum_perceptual_distance,
                maximum_aspect_difference=request.maximum_aspect_difference,
                maximum_neighbors_per_asset=request.maximum_neighbors_per_asset,
                stats=candidate_stats,
                retain_pairs=False,
            )
            accepted: list[tuple[float, int, int, SimilarityScanPair]] = []
            processed = 0
            scoring_snapshot_digest = _feature_snapshot_digest()
            scoring_asset_count = 0

            async for feature_batch in self._candidate_feature_batches():
                await context.ensure_active()
                for feature in feature_batch:
                    _update_feature_snapshot_digest(scoring_snapshot_digest, feature)
                    scoring_asset_count += 1
                phase_started = perf_counter()
                emitted = await asyncio.to_thread(
                    candidate_index.process_batch,
                    feature_batch,
                )
                candidate_discovery_milliseconds += round(
                    (perf_counter() - phase_started) * 1000
                )

                for offset in range(0, len(emitted), SIMILARITY_SCORE_BATCH_SIZE):
                    await context.ensure_active()
                    batch = emitted[offset : offset + SIMILARITY_SCORE_BATCH_SIZE]
                    asset_ids = list(
                        dict.fromkeys(
                            asset_id
                            for pair in batch
                            for asset_id in (pair.asset_id_low, pair.asset_id_high)
                        )
                    )
                    feature_by_id = await self._current_features(asset_ids)
                    if len(feature_by_id) != len(asset_ids):
                        raise PermanentTaskError(
                            "Similarity scan coverage changed during candidate scoring; "
                            "retry after asset synchronization settles."
                        )
                    scoring_started = perf_counter()
                    edges = await self._similarity.reference_edges(
                        [[pair.asset_id_low, pair.asset_id_high] for pair in batch],
                        feature_by_id,
                        **_epoch_kwargs(
                            self._similarity.reference_edges,
                            evidence_epoch,
                        ),
                    )
                    pair_scoring_milliseconds += round(
                        (perf_counter() - scoring_started) * 1000
                    )
                    for pair in batch:
                        evidence = edges.get((pair.asset_id_low, pair.asset_id_high))
                        if (
                            evidence is None
                            or evidence.similarity_percent
                            < request.similarity_threshold
                        ):
                            continue
                        low_feature = feature_by_id[pair.asset_id_low]
                        high_feature = feature_by_id[pair.asset_id_high]
                        match = SimilarityScanPair(
                            asset_id_low=pair.asset_id_low,
                            asset_id_high=pair.asset_id_high,
                            asset_low_source_sha256=low_feature.source_identity,
                            asset_high_source_sha256=high_feature.source_identity,
                            evidence=evidence,
                        )
                        ranked = (
                            evidence.similarity_percent,
                            -pair.asset_id_low.int,
                            -pair.asset_id_high.int,
                            match,
                        )
                        if len(accepted) < request.maximum_matches:
                            heapq.heappush(accepted, ranked)
                        else:
                            result_limit_reached = True
                            if ranked[:3] > accepted[0][:3]:
                                heapq.heapreplace(accepted, ranked)
                    processed += len(batch)

                processed_assets = candidate_index.processed
                if processed_assets < resume_index:
                    continue
                if saved_phase == "scoring" and processed < resume_scored:
                    continue
                await context.checkpoint(
                    checkpoint={
                        "phase": "scoring",
                        "scan_id": str(scan_id),
                        "feature_snapshot": snapshot_key,
                        "candidate_assets_processed": processed_assets,
                        "pairs_scored": processed,
                    },
                    counters=telemetry(
                        assets_with_current_features=asset_count,
                        candidate_assets_processed=processed_assets,
                        candidate_pairs=processed,
                        candidate_pair_limit=candidate_pair_limit,
                        pairs_scored=processed,
                        matches_retained=len(accepted),
                        retained_match_limit=request.maximum_matches,
                        result_limit_reached=int(result_limit_reached),
                    ),
                    progress={
                        "phase": "similarity_scoring",
                        "completed": processed_assets,
                        "total": asset_count,
                        "percent": round(
                            35 + 60 * processed_assets / max(1, asset_count),
                            1,
                        ),
                        "detail": (
                            f"Indexed {processed_assets} of {asset_count} fingerprints · "
                            f"scored {processed} candidate pairs"
                        ),
                    },
                )

            total = processed
            if (
                scoring_asset_count != asset_count
                or scoring_snapshot_digest.hexdigest() != snapshot_key
            ):
                raise PermanentTaskError(
                    "Similarity scan fingerprint snapshot changed during candidate scoring; "
                    "retry after asset synchronization settles."
                )
            await context.checkpoint(
                checkpoint={
                    "phase": "scoring",
                    "scan_id": str(scan_id),
                    "feature_snapshot": snapshot_key,
                    "candidate_assets_processed": asset_count,
                    "pairs_scored": total,
                },
                counters=telemetry(
                    assets_with_current_features=asset_count,
                    candidate_assets_processed=asset_count,
                    candidate_pairs=total,
                    candidate_pair_limit=candidate_pair_limit,
                    pairs_scored=total,
                    matches_retained=len(accepted),
                    retained_match_limit=request.maximum_matches,
                    result_limit_reached=int(result_limit_reached),
                ),
                progress={
                    "phase": "similarity_scoring",
                    "completed": total,
                    "total": total,
                    "percent": 95.0,
                    "detail": f"Scored {total} bounded candidate pairs",
                },
            )
            matches = [item[3] for item in accepted]
            missing_reference_groups = _missing_reference_groups(matches, request)
            reference_pairs_required = sum(
                len(group) - 1 for group in missing_reference_groups
            )
            reference_pairs_enriched = 0
            if reference_pairs_required:
                await context.checkpoint(
                    checkpoint={
                        "phase": "reference_enrichment",
                        "scan_id": str(scan_id),
                        "feature_snapshot": snapshot_key,
                        "candidate_assets_processed": asset_count,
                        "pairs_scored": total,
                    },
                    counters=telemetry(
                        assets_with_current_features=asset_count,
                        candidate_pairs=total,
                        candidate_pair_limit=(
                            candidate_pair_limit
                        ),
                        pairs_scored=total,
                        matches_retained=len(matches),
                        retained_match_limit=request.maximum_matches,
                        result_limit_reached=int(result_limit_reached),
                        reference_pairs_required=reference_pairs_required,
                        reference_pairs_enriched=0,
                    ),
                    progress={
                        "phase": "similarity_reference_enrichment",
                        "completed": 0,
                        "total": reference_pairs_required,
                        "percent": 97.0,
                        "detail": (
                            "Completing direct reference comparisons for "
                            f"{reference_pairs_required} linked group members…"
                        ),
                    },
                )
                await context.ensure_active()
                enrichment_started = perf_counter()
                reference_pairs_enriched = await self._enrich_reference_groups(
                    missing_reference_groups,
                    evidence_epoch=evidence_epoch,
                )
                pair_scoring_milliseconds += round(
                    (perf_counter() - enrichment_started) * 1000
                )
                if reference_pairs_enriched != reference_pairs_required:
                    raise PermanentTaskError(
                        "Similarity reference enrichment did not produce every "
                        "final-group reference comparison."
                    )
                await context.checkpoint(
                    checkpoint={
                        "phase": "reference_enrichment",
                        "scan_id": str(scan_id),
                        "feature_snapshot": snapshot_key,
                        "candidate_assets_processed": asset_count,
                        "pairs_scored": total,
                    },
                    counters=telemetry(
                        assets_with_current_features=asset_count,
                        candidate_pairs=total,
                        candidate_pair_limit=(
                            candidate_pair_limit
                        ),
                        pairs_scored=total,
                        matches_retained=len(matches),
                        retained_match_limit=request.maximum_matches,
                        result_limit_reached=int(result_limit_reached),
                        reference_pairs_required=reference_pairs_required,
                        reference_pairs_enriched=reference_pairs_enriched,
                    ),
                    progress={
                        "phase": "similarity_reference_enrichment",
                        "completed": reference_pairs_enriched,
                        "total": reference_pairs_required,
                        "percent": 98.0,
                        "detail": (
                            "Completed direct reference comparisons for "
                            f"{reference_pairs_enriched} linked group members"
                        ),
                    },
                )
            await context.checkpoint(
                checkpoint={
                    "phase": "finalizing",
                    "scan_id": str(scan_id),
                    "feature_snapshot": snapshot_key,
                    "candidate_assets_processed": asset_count,
                    "pairs_scored": total,
                },
                counters=telemetry(
                    assets_with_current_features=asset_count,
                    candidate_pairs=total,
                    candidate_pair_limit=(
                        candidate_pair_limit
                    ),
                    pairs_scored=total,
                    matches_retained=len(matches),
                    retained_match_limit=request.maximum_matches,
                    result_limit_reached=int(result_limit_reached),
                    reference_pairs_required=reference_pairs_required,
                    reference_pairs_enriched=reference_pairs_enriched,
                ),
                progress={
                    "phase": "similarity_finalizing",
                    "completed": total,
                    "total": total,
                    "percent": 99.0,
                    "detail": f"Publishing {len(matches)} retained review pairs…",
                },
            )
            await context.ensure_active()
            await self._scans.complete(
                scan_id,
                asset_count=asset_count,
                candidate_count=total,
                pairs=matches,
                result_limit_reached=result_limit_reached,
                **_epoch_kwargs(self._scans.complete, evidence_epoch),
            )
        except TaskCancelledError:
            if scan_id is not None:
                await self._scans.cancel(scan_id)
            raise
        except TaskPausedError:
            raise
        except Exception as error:
            if scan_id is not None:
                await self._scans.fail(scan_id, str(error))
            raise

        return TaskResult(
            summary={
                "scan_id": str(scan_id),
                "similarity_threshold": request.similarity_threshold,
                "validation_mode": request.validation_mode,
                "max_link_depth": request.max_link_depth,
                "anchor_asset_id": (
                    str(request.anchor_asset_id) if request.anchor_asset_id else None
                ),
                "scope": request.scope,
                "result_limit_reached": result_limit_reached,
                "maximum_matches": request.maximum_matches,
                "fingerprints_excluded_after_retry": len(excluded_ids),
                "excluded_asset_ids": [str(identifier) for identifier in excluded_ids[:100]],
                "excluded_asset_ids_truncated": len(excluded_ids) > 100,
                "excluded_asset_reasons": {
                    str(identifier): fingerprint_failure_reasons[identifier]
                    for identifier in excluded_ids[:100]
                    if identifier in fingerprint_failure_reasons
                },
            },
            counters=telemetry(
                assets_with_current_features=asset_count,
                candidate_pairs=total,
                candidate_pair_limit=(
                    candidate_pair_limit
                ),
                pairs_scored=total,
                matches_retained=len(matches),
                retained_match_limit=request.maximum_matches,
                result_limit_reached=int(result_limit_reached),
                reference_pairs_required=reference_pairs_required,
                reference_pairs_enriched=reference_pairs_enriched,
            ),
        )

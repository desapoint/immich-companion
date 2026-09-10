"""Coordinated, bounded whole-library visual similarity scans."""

from __future__ import annotations

import asyncio
import heapq
import json
from hashlib import sha256
from time import perf_counter
from typing import Any

from companion.discovery import BoundedSimilarityCandidateIndex, SimilarityCandidateStats
from companion.duplicate_schema import (
    SimilarityScanRequest,
    SimilarityScanSummary,
    SimilarityScanTaskStart,
)
from companion.integrity_repository import IntegrityRepository
from companion.integrity_service import INTEGRITY_TASK_TYPE
from companion.runtime_metrics import process_memory_snapshot
from companion.similarity_features import SIMILARITY_FEATURE_VERSION, SIMILARITY_MODEL_VERSION
from companion.similarity_repository import SIMILARITY_COMPARISON_VERSION, SimilarityRepository
from companion.similarity_scan_repository import (
    SimilarityScanPair,
    SimilarityScanParameters,
    SimilarityScanRepository,
)
from companion.task_coordinator import (
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


def _request_key(request: SimilarityScanRequest) -> str:
    raw = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _feature_snapshot_key(features: list[Any]) -> str:
    """Fingerprint the ordered candidate inputs used by a durable scan checkpoint."""

    digest = sha256()
    for feature in features:
        digest.update(
            (
                f"{feature.asset_id}:{feature.model_version}:{feature.feature_version}:"
                f"{feature.width}:{feature.height}:{feature.perceptual_hash}\n"
            ).encode()
        )
    return digest.hexdigest()


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
            scope=run.parameters.scope,
            model_version=run.parameters.model_version,
            feature_version=run.parameters.feature_version,
            comparison_version=run.parameters.comparison_version,
            asset_count=run.asset_count,
            candidate_count=run.candidate_count,
            match_count=run.match_count,
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
        features: IntegrityRepository,
        similarity: SimilarityRepository,
        scans: SimilarityScanRepository,
    ) -> None:
        self._features = features
        self._similarity = similarity
        self._scans = scans

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        started = perf_counter()
        request = SimilarityScanRequest.model_validate(payload)
        parameters = SimilarityScanParameters(
            model_version=SIMILARITY_MODEL_VERSION,
            feature_version=SIMILARITY_FEATURE_VERSION,
            comparison_version=SIMILARITY_COMPARISON_VERSION,
            scope=request.scope,
            similarity_threshold=request.similarity_threshold,
            maximum_perceptual_distance=request.maximum_perceptual_distance,
            maximum_aspect_difference=request.maximum_aspect_difference,
            maximum_neighbors_per_asset=request.maximum_neighbors_per_asset,
            maximum_matches=request.maximum_matches,
        )
        candidate_stats = SimilarityCandidateStats()
        scan_id = None

        def telemetry(**values: int) -> dict[str, int]:
            memory = process_memory_snapshot()
            return {
                **values,
                "candidate_index_nodes_visited": candidate_stats.index_nodes_visited,
                "candidate_raw_neighbor_matches": candidate_stats.raw_neighbor_matches,
                "candidate_peak_query_matches": candidate_stats.peak_query_matches,
                "candidate_peak_active_index_assets": candidate_stats.peak_active_index_assets,
                "rss_bytes": memory.rss_bytes,
                "rss_peak_bytes": memory.peak_rss_bytes,
                "elapsed_milliseconds": round((perf_counter() - started) * 1000),
            }

        try:
            await context.ensure_active()
            task = getattr(context, "task", None)
            task_id = getattr(task, "id", None)
            scan_id = await self._scans.prepare(parameters, scan_id=task_id)
            completed = await self._scans.completed_summary(scan_id)
            if completed is not None:
                return TaskResult(
                    summary={
                        "scan_id": str(scan_id),
                        "similarity_threshold": request.similarity_threshold,
                        "scope": request.scope,
                        "result_limit_reached": completed.match_count == request.maximum_matches,
                        "recovered_completed_scan": True,
                    },
                    counters=telemetry(
                        assets_with_current_features=completed.asset_count,
                        candidate_pairs=completed.candidate_count,
                        pairs_scored=completed.candidate_count,
                        matches_retained=completed.match_count,
                    ),
                )
            features = await self._features.list_current_similarity_features()
            feature_by_id = {feature.asset_id: feature for feature in features}
            candidate_index = BoundedSimilarityCandidateIndex(
                features,
                maximum_perceptual_distance=request.maximum_perceptual_distance,
                maximum_aspect_difference=request.maximum_aspect_difference,
                maximum_neighbors_per_asset=request.maximum_neighbors_per_asset,
                stats=candidate_stats,
            )
            ordered_features = candidate_index.ordered_features
            snapshot_key = await asyncio.to_thread(_feature_snapshot_key, ordered_features)
            saved = dict(getattr(task, "checkpoint", {}) or {})
            same_snapshot = saved.get("feature_snapshot") == snapshot_key
            saved_phase = str(saved.get("phase", "")) if same_snapshot else ""
            resume_index = (
                min(len(ordered_features), int(saved.get("candidate_assets_processed", 0)))
                if saved_phase in ("candidate_index", "scoring")
                else 0
            )
            resume_scored = (
                max(0, int(saved.get("pairs_scored", 0))) if saved_phase == "scoring" else 0
            )
            if saved_phase != "scoring":
                await context.checkpoint(
                    checkpoint={
                        "phase": "candidate_index",
                        "scan_id": str(scan_id),
                        "feature_snapshot": snapshot_key,
                        "candidate_assets_processed": resume_index,
                    },
                    counters=telemetry(
                        assets_with_current_features=len(ordered_features),
                        candidate_assets_processed=resume_index,
                        candidate_pair_limit=(
                            len(ordered_features) * request.maximum_neighbors_per_asset // 2
                        ),
                    ),
                    progress={
                        "phase": "similarity_candidates",
                        "completed": resume_index,
                        "total": len(ordered_features),
                        "percent": round(
                            5 + 10 * resume_index / max(1, len(ordered_features)), 1
                        ),
                        "detail": (
                            f"Resuming candidate index after {resume_index} fingerprints…"
                            if resume_index
                            else f"Indexing {len(ordered_features)} visual fingerprints…"
                        ),
                    },
                )
            while candidate_index.processed < len(ordered_features):
                await context.ensure_active()
                await asyncio.to_thread(candidate_index.process_next, SIMILARITY_INDEX_BATCH_SIZE)
                processed_assets = candidate_index.processed
                if processed_assets < resume_index or saved_phase == "scoring":
                    continue
                await context.checkpoint(
                    checkpoint={
                        "phase": "candidate_index",
                        "scan_id": str(scan_id),
                        "feature_snapshot": snapshot_key,
                        "candidate_assets_processed": processed_assets,
                    },
                    counters=telemetry(
                        assets_with_current_features=len(ordered_features),
                        candidate_assets_processed=processed_assets,
                        candidate_pairs=len(candidate_index.pairs),
                        candidate_pair_limit=(
                            len(ordered_features) * request.maximum_neighbors_per_asset // 2
                        ),
                    ),
                    progress={
                        "phase": "similarity_candidates",
                        "completed": processed_assets,
                        "total": len(ordered_features),
                        "percent": round(
                            5 + 10 * processed_assets / max(1, len(ordered_features)), 1
                        ),
                        "detail": (
                            f"Indexed {processed_assets} of {len(ordered_features)} fingerprints"
                        ),
                    },
                )
            candidates = candidate_index.pairs
            total = len(candidates)
            resume_scored = min(total, resume_scored)
            accepted: list[tuple[float, int, int, SimilarityScanPair]] = []
            processed = 0
            await context.checkpoint(
                checkpoint={
                    "phase": "scoring",
                    "scan_id": str(scan_id),
                    "feature_snapshot": snapshot_key,
                    "candidate_assets_processed": len(ordered_features),
                    "pairs_scored": resume_scored,
                },
                counters=telemetry(
                    assets_with_current_features=len(features),
                    candidate_pairs=total,
                    candidate_pair_limit=(
                        len(features) * request.maximum_neighbors_per_asset // 2
                    ),
                    pairs_scored=resume_scored,
                    matches_retained=0,
                ),
                progress={
                    "phase": "similarity_scoring",
                    "completed": resume_scored,
                    "total": total,
                    "percent": round(15 + 80 * resume_scored / max(1, total), 1),
                    "detail": (
                        f"Restoring scoring state after {resume_scored} candidate pairs…"
                        if resume_scored
                        else f"Scoring {total} bounded candidate pairs…"
                    ),
                },
            )
            for offset in range(0, total, SIMILARITY_SCORE_BATCH_SIZE):
                await context.ensure_active()
                batch = candidates[offset : offset + SIMILARITY_SCORE_BATCH_SIZE]
                edges = await self._similarity.reference_edges(
                    [[pair.asset_id_low, pair.asset_id_high] for pair in batch],
                    feature_by_id,
                )
                for pair in batch:
                    evidence = edges.get((pair.asset_id_low, pair.asset_id_high))
                    if (
                        evidence is None
                        or evidence.similarity_percent < request.similarity_threshold
                    ):
                        continue
                    low_feature = feature_by_id[pair.asset_id_low]
                    high_feature = feature_by_id[pair.asset_id_high]
                    match = SimilarityScanPair(
                        asset_id_low=pair.asset_id_low,
                        asset_id_high=pair.asset_id_high,
                        asset_low_source_sha256=low_feature.source_sha256,
                        asset_high_source_sha256=high_feature.source_sha256,
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
                    elif ranked[:3] > accepted[0][:3]:
                        heapq.heapreplace(accepted, ranked)
                processed += len(batch)
                if processed < resume_scored:
                    continue
                await context.checkpoint(
                    checkpoint={
                        "phase": "scoring",
                        "scan_id": str(scan_id),
                        "feature_snapshot": snapshot_key,
                        "candidate_assets_processed": len(ordered_features),
                        "pairs_scored": processed,
                    },
                    counters=telemetry(
                        assets_with_current_features=len(features),
                        candidate_pairs=total,
                        candidate_pair_limit=(
                            len(features) * request.maximum_neighbors_per_asset // 2
                        ),
                        pairs_scored=processed,
                        matches_retained=len(accepted),
                    ),
                    progress={
                        "phase": "similarity_scoring",
                        "completed": processed,
                        "total": total,
                        "percent": round(15 + 80 * processed / max(1, total), 1),
                        "detail": f"Scored {processed} of {total} candidate pairs",
                    },
                )
            matches = [item[3] for item in accepted]
            await context.checkpoint(
                checkpoint={
                    "phase": "finalizing",
                    "scan_id": str(scan_id),
                    "feature_snapshot": snapshot_key,
                    "candidate_assets_processed": len(ordered_features),
                    "pairs_scored": total,
                },
                counters=telemetry(
                    assets_with_current_features=len(features),
                    candidate_pairs=total,
                    candidate_pair_limit=(
                        len(features) * request.maximum_neighbors_per_asset // 2
                    ),
                    pairs_scored=total,
                    matches_retained=len(matches),
                ),
                progress={
                    "phase": "similarity_finalizing",
                    "completed": total,
                    "total": total,
                    "percent": 99.0,
                    "detail": f"Publishing {len(matches)} retained review pairs…",
                },
            )
            await self._scans.complete(
                scan_id,
                asset_count=len(features),
                candidate_count=total,
                pairs=matches,
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
                "scope": request.scope,
                "result_limit_reached": len(matches) == request.maximum_matches,
            },
            counters=telemetry(
                assets_with_current_features=len(features),
                candidate_pairs=total,
                candidate_pair_limit=(
                    len(features) * request.maximum_neighbors_per_asset // 2
                ),
                pairs_scored=total,
                matches_retained=len(matches),
            ),
        )

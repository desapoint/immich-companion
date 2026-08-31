"""Coordinated, bounded whole-library visual similarity scans."""

from __future__ import annotations

import asyncio
import heapq
import json
from hashlib import sha256
from typing import Any

from companion.discovery import bounded_similarity_candidates
from companion.duplicate_schema import SimilarityScanRequest, SimilarityScanTaskStart
from companion.integrity_repository import IntegrityRepository
from companion.integrity_service import INTEGRITY_TASK_TYPE
from companion.similarity_features import SIMILARITY_FEATURE_VERSION, SIMILARITY_MODEL_VERSION
from companion.similarity_repository import SIMILARITY_COMPARISON_VERSION, SimilarityRepository
from companion.similarity_scan_repository import (
    SimilarityScanPair,
    SimilarityScanParameters,
    SimilarityScanRepository,
)
from companion.task_coordinator import TaskContext, TaskCoordinator
from companion.task_schema import TaskResult

SIMILARITY_SCAN_TASK_TYPE = "similarity_scan"
SIMILARITY_SCORE_BATCH_SIZE = 500


def _request_key(request: SimilarityScanRequest) -> str:
    raw = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


class SimilarityScanService:
    """Submit idempotent similarity scans through the shared coordinator."""

    def __init__(self, tasks: TaskCoordinator) -> None:
        self._tasks = tasks

    async def start(self, request: SimilarityScanRequest) -> SimilarityScanTaskStart:
        key = _request_key(request)
        task = await self._tasks.find_active(SIMILARITY_SCAN_TASK_TYPE, key)
        if task is None:
            task = await self._tasks.submit(
                SIMILARITY_SCAN_TASK_TYPE,
                request.model_dump(mode="json"),
                priority=45,
                lane_key=INTEGRITY_TASK_TYPE,
                deduplication_key=key,
            )
            await self._tasks.start()
        return SimilarityScanTaskStart(task_id=task.id)


class SimilarityScanTaskHandler:
    """Discover and score pair candidates without unbounded fan-out."""

    task_type = SIMILARITY_SCAN_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1

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
        request = SimilarityScanRequest.model_validate(payload)
        parameters = SimilarityScanParameters(
            model_version=SIMILARITY_MODEL_VERSION,
            feature_version=SIMILARITY_FEATURE_VERSION,
            comparison_version=SIMILARITY_COMPARISON_VERSION,
            similarity_threshold=request.similarity_threshold,
            maximum_perceptual_distance=request.maximum_perceptual_distance,
            maximum_aspect_difference=request.maximum_aspect_difference,
            maximum_neighbors_per_asset=request.maximum_neighbors_per_asset,
            maximum_matches=request.maximum_matches,
        )
        scan_id = await self._scans.create(parameters)
        try:
            await context.ensure_active()
            features = await self._features.list_current_similarity_features()
            feature_by_id = {feature.asset_id: feature for feature in features}
            await context.checkpoint(
                checkpoint={"phase": "candidate_index", "scan_id": str(scan_id)},
                counters={"assets_with_current_features": len(features)},
                progress={
                    "phase": "similarity_candidates",
                    "completed": 0,
                    "total": None,
                    "percent": 5.0,
                    "detail": f"Indexing {len(features)} current visual fingerprints…",
                },
            )
            candidates = await asyncio.to_thread(
                bounded_similarity_candidates,
                features,
                maximum_perceptual_distance=request.maximum_perceptual_distance,
                maximum_aspect_difference=request.maximum_aspect_difference,
                maximum_neighbors_per_asset=request.maximum_neighbors_per_asset,
            )
            total = len(candidates)
            accepted: list[tuple[float, int, int, SimilarityScanPair]] = []
            processed = 0
            await context.checkpoint(
                checkpoint={"phase": "scoring", "scan_id": str(scan_id)},
                counters={
                    "assets_with_current_features": len(features),
                    "candidate_pairs": total,
                    "pairs_scored": 0,
                    "matches_retained": 0,
                },
                progress={
                    "phase": "similarity_scoring",
                    "completed": 0,
                    "total": total,
                    "percent": 15.0,
                    "detail": f"Scoring {total} bounded candidate pairs…",
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
                await context.checkpoint(
                    checkpoint={
                        "phase": "scoring",
                        "scan_id": str(scan_id),
                        "pairs_scored": processed,
                    },
                    counters={
                        "assets_with_current_features": len(features),
                        "candidate_pairs": total,
                        "pairs_scored": processed,
                        "matches_retained": len(accepted),
                    },
                    progress={
                        "phase": "similarity_scoring",
                        "completed": processed,
                        "total": total,
                        "percent": round(15 + 80 * processed / max(1, total), 1),
                        "detail": f"Scored {processed} of {total} candidate pairs",
                    },
                )
            matches = [item[3] for item in accepted]
            await self._scans.complete(
                scan_id,
                asset_count=len(features),
                candidate_count=total,
                pairs=matches,
            )
        except Exception as error:
            await self._scans.fail(scan_id, str(error))
            raise

        await context.checkpoint(
            checkpoint={"phase": "complete", "scan_id": str(scan_id)},
            counters={
                "assets_with_current_features": len(features),
                "candidate_pairs": total,
                "pairs_scored": total,
                "matches_retained": len(matches),
            },
            progress={
                "phase": "complete",
                "completed": total,
                "total": total,
                "percent": 100.0,
                "detail": f"Similarity scan retained {len(matches)} review pairs.",
            },
        )
        return TaskResult(
            summary={
                "scan_id": str(scan_id),
                "similarity_threshold": request.similarity_threshold,
                "result_limit_reached": len(matches) == request.maximum_matches,
            },
            counters={
                "assets_with_current_features": len(features),
                "candidate_pairs": total,
                "pairs_scored": total,
                "matches_retained": len(matches),
            },
        )

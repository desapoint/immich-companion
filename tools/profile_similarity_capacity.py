"""Profile bounded Appearance candidate discovery with synthetic metadata only.

Run from the repository root, for example:

    backend/.venv/bin/python tools/profile_similarity_capacity.py --assets 60000
"""

from __future__ import annotations

import argparse
import gc
import json
import resource
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from companion.discovery import (  # noqa: E402
    SimilarityCandidateStats,
    bounded_similarity_candidates,
)
from companion.runtime_metrics import process_memory_snapshot  # noqa: E402

Pattern = Literal["clustered", "collision", "sparse"]
MASK_64 = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class SyntheticFeature:
    asset_id: UUID
    perceptual_hash: str
    width: int = 4032
    height: int = 3024
    model_version: str = "appearance-v1"
    feature_version: int = 2


def splitmix64(value: int) -> int:
    """Return a deterministic, well-distributed synthetic 64-bit value."""

    value = (value + 0x9E3779B97F4A7C15) & MASK_64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK_64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK_64
    return value ^ (value >> 31)


def synthetic_features(
    asset_count: int,
    *,
    pattern: Pattern,
    maximum_neighbors_per_asset: int,
) -> list[SyntheticFeature]:
    """Build compact deterministic inputs without requiring media originals."""

    cluster_size = maximum_neighbors_per_asset + 1
    features: list[SyntheticFeature] = []
    for index in range(asset_count):
        if pattern == "collision":
            hash_value = 0
        elif pattern == "clustered":
            hash_value = splitmix64(index // cluster_size)
        else:
            hash_value = splitmix64(index)
        features.append(
            SyntheticFeature(
                asset_id=UUID(int=index + 1),
                perceptual_hash=f"{hash_value:016x}",
            )
        )
    return features


def memory_sample(stage: str, started: float) -> dict[str, int | float | str]:
    memory = process_memory_snapshot()
    python_bytes, python_peak_bytes = tracemalloc.get_traced_memory()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    io_values: dict[str, int] = {}
    try:
        for line in Path("/proc/self/io").read_text(encoding="utf-8").splitlines():
            name, separator, raw = line.partition(":")
            if separator and name in {"read_bytes", "write_bytes"}:
                io_values[name] = int(raw.strip())
    except (OSError, ValueError):
        pass
    return {
        "stage": stage,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "rss_bytes": memory.rss_bytes,
        "rss_peak_bytes": memory.peak_rss_bytes,
        "python_bytes": python_bytes,
        "python_peak_bytes": python_peak_bytes,
        "cpu_user_seconds": round(usage.ru_utime, 4),
        "cpu_system_seconds": round(usage.ru_stime, 4),
        "disk_read_bytes": io_values.get("read_bytes", 0),
        "disk_write_bytes": io_values.get("write_bytes", 0),
    }


def profile(
    asset_count: int,
    *,
    pattern: Pattern,
    maximum_neighbors_per_asset: int,
    maximum_perceptual_distance: int,
) -> dict[str, object]:
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    samples = [memory_sample("start", started)]
    features = synthetic_features(
        asset_count,
        pattern=pattern,
        maximum_neighbors_per_asset=maximum_neighbors_per_asset,
    )
    samples.append(memory_sample("features_ready", started))
    stats = SimilarityCandidateStats()
    candidates = bounded_similarity_candidates(
        features,
        maximum_perceptual_distance=maximum_perceptual_distance,
        maximum_neighbors_per_asset=maximum_neighbors_per_asset,
        stats=stats,
    )
    samples.append(memory_sample("candidates_ready", started))

    maximum_pair_count = asset_count * maximum_neighbors_per_asset // 2
    degrees: dict[UUID, int] = {}
    for pair in candidates:
        degrees[pair.asset_id_low] = degrees.get(pair.asset_id_low, 0) + 1
        degrees[pair.asset_id_high] = degrees.get(pair.asset_id_high, 0) + 1
    maximum_degree = max(degrees.values(), default=0)
    if len(candidates) > maximum_pair_count or maximum_degree > maximum_neighbors_per_asset:
        raise RuntimeError("Candidate discovery exceeded its configured degree bound")

    result = {
        "asset_count": asset_count,
        "pattern": pattern,
        "maximum_neighbors_per_asset": maximum_neighbors_per_asset,
        "maximum_perceptual_distance": maximum_perceptual_distance,
        "candidate_pair_limit": maximum_pair_count,
        "candidate_count": len(candidates),
        "maximum_observed_degree": maximum_degree,
        "external_api_requests": 0,
        "media_files_read": 0,
        "candidate_stats": asdict(stats),
        "samples": samples,
    }
    del candidates, degrees, features
    gc.collect()
    samples.append(memory_sample("released", started))
    tracemalloc.stop()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile bounded similarity candidate discovery without media files."
    )
    parser.add_argument("--assets", type=int, default=60_000)
    parser.add_argument(
        "--pattern",
        choices=("clustered", "collision", "sparse"),
        default="clustered",
        help="clustered exercises normal candidates; collision stresses identical hashes",
    )
    parser.add_argument("--maximum-neighbors", type=int, default=8)
    parser.add_argument("--maximum-distance", type=int, default=0)
    args = parser.parse_args()
    if args.assets < 1:
        parser.error("--assets must be positive")
    if args.maximum_neighbors < 1:
        parser.error("--maximum-neighbors must be positive")
    if not 0 <= args.maximum_distance <= 64:
        parser.error("--maximum-distance must be between 0 and 64")
    print(
        json.dumps(
            profile(
                args.assets,
                pattern=args.pattern,
                maximum_neighbors_per_asset=args.maximum_neighbors,
                maximum_perceptual_distance=args.maximum_distance,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

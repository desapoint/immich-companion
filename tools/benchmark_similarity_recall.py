"""Measure preview candidate recall for deterministic detail variants.

Run with: PYTHONPATH=backend python tools/benchmark_similarity_recall.py
"""

from io import BytesIO
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID

from benchmark_similarity_detail import scene, variants
from companion.discovery import SimilarityCandidateStats, bounded_similarity_candidates
from companion.duplicate_schema import SimilarityScanRequest
from companion.similarity_features import compare_visual_features
from companion.similarity_scan_service import DETAIL_COARSE_SCORE_MARGIN
from companion.similarity_search_features import extract_search_feature
from PIL import Image


def preview_feature(number: int, image: Image.Image) -> tuple[SimpleNamespace, object]:
    preview = image.copy()
    preview.thumbnail((256, 256), Image.Resampling.LANCZOS)
    output = BytesIO()
    preview.save(output, format="JPEG", quality=80)
    visual = extract_search_feature(output.getvalue())
    assert visual is not None
    return (
        SimpleNamespace(
            asset_id=UUID(int=number),
            model_version=visual.model_version,
            feature_version=visual.feature_version,
            width=image.width,
            height=image.height,
            perceptual_hash=visual.perceptual_hash,
        ),
        visual,
    )


def main() -> None:
    source = scene()
    reference, reference_visual = preview_feature(1, source)
    request = SimilarityScanRequest()
    detail_floor = max(50.0, request.similarity_threshold - DETAIL_COARSE_SCORE_MARGIN)
    print(f"default final threshold {request.similarity_threshold:.0f}%; detail floor {detail_floor:.0f}%")
    print(
        f"{'variant':25} {'hash distance':>13} {'coarse score':>13} "
        f"{'candidate':>10} {'detail stage':>13}"
    )
    for number, (name, image, _) in enumerate(variants()[2:], start=2):
        candidate, visual = preview_feature(number, image)
        distance = (int(reference.perceptual_hash, 16) ^ int(candidate.perceptual_hash, 16)).bit_count()
        score = compare_visual_features(reference_visual, visual).similarity_percent
        pairs = bounded_similarity_candidates([reference, candidate])
        print(
            f"{name:25} {distance:13d} {score:12.2f}% "
            f"{bool(pairs)!s:>10} {(bool(pairs) and score >= detail_floor)!s:>13}"
        )

    for crowded_count in (8, 9, 18, 24):
        crowded = [preview_feature(number, source)[0] for number in range(1, crowded_count + 1)]
        late_variant, _ = preview_feature(crowded_count + 1, variants()[3][1])
        stats = SimilarityCandidateStats()
        crowded_pairs = bounded_similarity_candidates(
            [*crowded, late_variant], stats=stats
        )
        print(
            f"crowded {crowded_count} references + late face accessory: "
            f"{sum(late_variant.asset_id in (pair.asset_id_low, pair.asset_id_high) for pair in crowded_pairs)} "
            f"variant links, {len(crowded_pairs)} total pairs, "
            f"{stats.peak_query_matches} peak matches"
        )

    dense_count = 25_000
    dense = [
        SimpleNamespace(
            asset_id=UUID(int=number),
            model_version=reference.model_version,
            feature_version=reference.feature_version,
            width=reference.width,
            height=reference.height,
            perceptual_hash=reference.perceptual_hash,
        )
        for number in range(1, dense_count + 1)
    ]
    stats = SimilarityCandidateStats()
    started = perf_counter()
    dense_pairs = bounded_similarity_candidates(dense, stats=stats)
    print(
        f"dense {dense_count:,} identical previews: {len(dense_pairs):,} pairs, "
        f"{stats.raw_neighbor_matches:,} raw matches, "
        f"{stats.peak_query_matches} peak query matches, "
        f"{perf_counter() - started:.2f}s"
    )


if __name__ == "__main__":
    main()

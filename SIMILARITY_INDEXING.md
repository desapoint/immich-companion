# Durable Library-Wide Similarity Indexing

This document records the corrective slice required before duplicate policy
classification continues. A similarity scan must cover the synchronized image
library, not only assets already encountered in Immich duplicate groups.

## Required lifecycle

1. Enumerate every active, synchronized image in stable keyset pages.
2. Classify its Appearance fingerprint as current, missing, or stale using the
   asset ID, source modification time, source size, model version, feature
   version, and configuration fingerprint.
3. Persistently process missing/stale images in finite batches. Commit each
   completed fingerprint so pause, cancellation, failure, or restart does not
   discard finished work.
4. Run bounded candidate discovery across the complete current fingerprint
   generation.
5. Build and persist similarity groups from the retained candidate pairs.

After the initial bootstrap, asset synchronization must cause only new or
changed images to require fingerprint work. Deleted, trashed, offline, and
non-image assets must not remain part of current index coverage.

## Operational contract

- Fingerprinting is a dedicated background/indexing task independent of Immich
  duplicate detection.
- Work is keyset-paged and checkpointed; no task fan-out is proportional to the
  whole library.
- Starting a similarity scan first completes or resumes required fingerprint
  maintenance, then searches a frozen current-feature snapshot.
- Coverage reports eligible, current, missing, and stale counts; task progress
  also reports unavailable assets encountered in that pass.
- A completed scan may claim `all_eligible_assets` only when missing and stale
  counts are zero for its snapshot. Incomplete coverage is reported explicitly
  and is never silently treated as a full-library result.
- Existing durable features are reused after restart and across later scans.
- Immich is accessed only through its API; all durable state is Companion-owned.

## Acceptance tests

- With a synchronized catalog of 60k metadata rows, work selection is keyset
  paged and identifies only missing/stale eligible images.
- After a completed baseline, adding 100 assets, changing 20, and removing 10
  schedules work only for the 120 new/changed assets and excludes the removals.
- Restarting midway resumes without recomputing committed fingerprints.
- A scan sees all current fingerprints, including assets never returned by
  Immich duplicate detection.
- A stale model/config generation is excluded until regenerated.
- Coverage and task progress distinguish fingerprinting from candidate search.

# Durable Library-Wide Similarity Indexing

This document records the visual-evidence contract used by v2 duplicate
discovery. A similarity scan covers the synchronized image library, not only
assets already encountered in Immich duplicate groups.

## Required lifecycle

1. Enumerate every active, synchronized image in stable keyset pages.
2. Classify its Appearance evidence as current, missing, or stale using the
   source identity and active evidence-generation versions.
3. For every missing or stale image, download the encoded original with a hard
   128 MiB source cap and pass it to the unified libvips normalizer.
4. Libvips autorotates and fits the image inside a 6000 × 6000 box while
   preserving aspect ratio and using decoder-level reduction when supported.
5. Generate both the search fingerprint and localized-detail feature from that
   same normalized representation and cache both.
6. Treat the asset as current only when the matching search and detail records
   are both current.
7. Run candidate discovery and pair scoring entirely from cached evidence.

After the initial bootstrap, asset synchronization causes only new or changed
images to require normalization. Deleted, trashed, offline, and non-image
assets do not remain part of current index coverage.

## Unified visual source contract

The normal visual path is independent of Immich's optional full-size-image
generation setting:

```text
Immich original encoded file
        |
        | hard input cap: 128 MiB
        v
libvips / pyvips
        |
        | autorotate
        | decoder-level shrink when supported
        | fit inside 6000 × 6000
        | preserve aspect ratio
        v
canonical visual image
        |
        +---- search fingerprint
        |
        +---- localized-detail feature
                    |
                    v
            complete visual cache
```

The original is streamed to a temporary encoded file. Companion does not first
create a full Python/Pillow raster just to resize it. This lets large JPEG,
HEIC/HEIF/AVIF, TIFF, and other libvips-supported sources use libvips' bounded,
demand-driven processing.

RAW also enters through libvips. A packaged libvips may expose a direct LibRaw
loader or route RAW through its ImageMagick delegate. Companion does not choose
a separate RAW normalization implementation in this Appearance pipeline.

If the original is larger than the 128 MiB source budget, unavailable, or not
decodable by the packaged libvips stack, Companion may use Immich's generated
preview as explicitly lower-grade visual evidence. Companion does not request
Immich's optional `fullsize` image for normal similarity normalization.

The runtime pins pyvips and its binary libvips package. The active pyvips and
libvips versions are included in the visual-normalization fingerprint so an
engine change invalidates incompatible cached Appearance evidence.

## Cache completeness and scoring

Search and detail evidence are generated together from one canonical visual
image. A search fingerprint without its matching current detail record is not
considered complete/current visual evidence and is re-queued for indexing.

Candidate discovery, full-library scans, incremental maintenance, duplicate
review, and Localized Changes therefore do not perform another media download
or image decode after indexing. Pair scoring combines the cached search and
localized-detail evidence. Localized Changes is a read-only cache operation.

Native Immich duplicate groups are also prepared through the same visual
indexer before review, so they do not bypass the cache-completeness invariant.

## Separate original-file evidence

The canonical visual image is Appearance evidence only. Original-byte and
preservation guarantees stay separate and continue to use the original-file
integrity pipeline for:

- checksums and byte identity;
- exact normalized-pixel identity;
- source metadata and file size;
- preservation evidence;
- destructive-action safety checks.

A visual fingerprint or localized-detail match never becomes exact-file proof.

## Resource controls and measurement

- Encoded original input is capped at 128 MiB by
  `SIMILARITY_DETAIL_MAX_BYTES`, which is also the unified visual-source
  budget.
- Canonical output is bounded to 6000 pixels on either axis.
- Fetch and decode concurrency remain independently bounded by the existing
  similarity fetch/decode slots.
- The libvips operation cache is disabled for this one-shot normalization
  workload so completed asset pipelines are not retained between images.
- Task telemetry records original/preview bytes, normalization resize counts,
  feature extraction, persistence, failures, and reuse.

## Acceptance tests

- A source with dimensions above 6000px is streamed from the original and
  reduced by libvips rather than rejected solely because of dimensions.
- A known source larger than 128 MiB is not opened and falls back to the safe
  preview path.
- JPEG, PNG, HEIF/AVIF, and a RAW-capable libvips loader path are present in the
  packaged runtime.
- Alpha survives normalization when the source representation contains alpha.
- Search and localized-detail features are written from the same normalized
  media and source identity.
- A search-only cache entry is not exposed as current.
- Full scans and incremental scoring perform one cache-only scoring pass and no
  second detail media stage.
- Localized Changes performs no media fetch, decode, or database mutation.

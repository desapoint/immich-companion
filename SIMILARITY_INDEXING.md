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
4. Libvips autorotates and fits the image inside a 2048 × 2048 box while
   preserving aspect ratio and using decoder-level reduction when supported.
5. Generate both the search fingerprint and localized-detail feature from that
   same normalized representation and cache both.
6. Treat the asset as current only when the matching search and detail records
   are both current.
7. Run candidate discovery and pair scoring entirely from cached evidence.
8. After final groups are constructed, complete any missing direct
   reference-to-member comparisons from the same cached search and detail
   evidence before publishing the scan. These enrichment scores are review
   evidence only and never change the already-finalized group membership.

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
        | fit inside 2048 × 2048
        | preserve aspect ratio
        v
canonical bounded sRGB pixels
        |
        | no JPEG/PNG re-encode or second media decode
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
demand-driven processing. After normalization, libvips exports the bounded sRGB
pixel buffer directly. Search and localized-detail extraction share one Pillow
view of those pixels; Companion does not encode a normalized JPEG/PNG and then
decode it again for each consumer.

RAW also enters through libvips. Companion explicitly recognizes common camera
RAW suffixes/MIME hints so DNG cannot be accidentally treated as ordinary TIFF
or reduced to an embedded JPEG by generic loader selection. When the packaged
libvips exposes its direct LibRaw/dcraw loader, Companion uses it; otherwise it
uses libvips' ImageMagick loader with the packaged dcraw delegate. This remains
one libvips normalization API from Companion's point of view.

If the original is larger than the 128 MiB source budget, unavailable, or not
decodable by the packaged libvips stack, Companion may use Immich's generated
preview as explicitly lower-grade visual evidence. Companion does not request
Immich's optional `fullsize` image for normal similarity normalization.

The Python binding is pinned, while libvips comes from the container's distro
package. Both the active pyvips and libvips versions are included in the
visual-normalization fingerprint so an engine change invalidates incompatible
cached Appearance evidence.

## Cache completeness and scoring

Search and detail evidence are generated together from one canonical bounded
pixel representation. A search fingerprint without its matching current detail record is not
considered complete/current visual evidence and is re-queued for indexing.

Candidate discovery, full-library scans, incremental maintenance, duplicate
review, and Localized Changes therefore do not perform another media download
or image decode after indexing. Pair scoring combines the cached search and
localized-detail evidence. Localized Changes is a read-only cache operation.

Native Immich duplicate groups are also prepared through the same visual
indexer before review, so they do not bypass the cache-completeness invariant.

### Shared original acquisition during duplicate preparation

Duplicate preparation resolves Appearance freshness and integrity/preservation
freshness before doing media work. When both evidence families are stale or
missing for the same asset, Companion streams the encoded Immich original once
to a task-local file in the decode cache. The Appearance indexer and the
integrity/preservation analyzer then consume that same caller-owned file
sequentially.

The two evidence contracts remain independent: Appearance still uses the
bounded libvips normalization path and may fall back to an Immich preview,
while integrity/preservation still hashes and validates the complete original
and performs its preservation decode. The shared file only removes duplicate
network acquisition; it is deleted after both consumers finish.

If only one evidence family needs work, its existing single-consumer path is
used. If both are already current, no original is downloaded.

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
- Canonical output is bounded to 2048 pixels on either axis.
- Fetch and decode concurrency remain independently bounded by the existing
  similarity fetch/decode slots.
- The libvips operation cache is disabled for this one-shot normalization
  workload so completed asset pipelines are not retained between images.
- Task telemetry records original/preview bytes, normalization resize counts,
  feature extraction, persistence, failures, and reuse.

## Acceptance tests

- A source with dimensions above 2048px is streamed from the original and
  reduced by libvips rather than rejected solely because of dimensions.
- A known source larger than 128 MiB is not opened and falls back to the safe
  preview path.
- JPEG, PNG, HEIF/AVIF, and a RAW-capable libvips loader path are present in the
  packaged runtime.
- DNG and other camera RAW sources are deliberately routed through that RAW path
  instead of generic TIFF/filename autodetection.
- Alpha survives normalization when the source representation contains alpha.
- Normalization hands bounded sRGB pixels directly to feature extraction without
  creating an intermediate JPEG/PNG.
- Search and localized-detail features are written from the same normalized
  pixels and source identity.
- A search-only cache entry is not exposed as current.
- Full scans and incremental scoring perform cache-only pair scoring and no
  second detail media stage.
- Linked groups receive a post-group reference-completion pass so every
  successfully indexed member has direct comparison evidence to the stable
  reference, even when membership was admitted transitively through another
  member. Below-threshold enrichment scores do not alter membership.
- Localized Changes performs no media fetch, decode, or database mutation.

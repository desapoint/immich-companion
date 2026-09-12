# Similarity indexing optimization roadmap

Status: implementation in progress on `feat/v2-shell`.

The bottleneck for a first-generation 25k-image library index is creating fingerprints, not bounded candidate generation or cached pair scoring. Keep library-wide, durable, incremental indexing: synchronized images → missing/stale search fingerprints → bounded candidate search and compact scoring → retrieve originals only for plausible groups or explicit exact-pixel/integrity verification. Never read Immich's database or files directly; use its API. A failed image must be logged with its reason where possible, retried once, then excluded without blocking a scan using the remaining current fingerprints.

## Ordered implementation steps (commit after each validated step)

1. **Preview-based search fingerprints.** Add an explicit coarse/search feature provenance or version so preview-derived features cannot be mistaken for original-derived verification. Fetch Immich-generated previews through the API, extract perceptual hash, 16×16 luminance, color histogram, and relevant dimensions, then persist them against the synchronized source identity. Preserve incremental missing/stale detection. Define a fallback for unavailable previews and verify it does not force all originals to be downloaded.
2. **Lazy full verification.** Keep candidate search and compact scoring on coarse features. Fetch originals and calculate exact-pixel/integrity evidence only for plausible groups or when the user explicitly asks for verification. Do not claim a preview feature proves exact pixels; preserve existing resolution safety gates.
3. **Single-decode extraction.** Consolidate image decode, dimension validation, visual feature extraction, and optional pixel hash so full verification does not open/decode the same original twice. Add format and oversized-image regressions.
4. **Bounded I/O–CPU pipeline.** Separate and configure Immich preview/original fetch slots from CPU decode slots; start conservatively, support weak servers, and maintain bounded memory, cancellation, pause/resume, progress, and per-item retry behavior.
5. **Remove redundant per-asset API calls.** Reuse synchronized source metadata where safe. Retain a source-change check before committing evidence, but avoid duplicate live lookups/refreshes on every indexed image. Batch or conditional validation must reject changed sources.
6. **Background sync maintenance.** Enqueue missing/stale search fingerprints after normal synchronization at low priority, without blocking sync or user actions. Keep scan-time catch-up and durable checkpoint/restart behavior.
7. **DB write tuning last.** Measure feature/report write cost after the above. Batch only if evidence shows a bottleneck; keep existing pair cache and bulk edge upsert behavior.

The search/verification split should remove full-original downloads, integrity hashing, and normalized-pixel SHA from ordinary indexing. The scan must still use the current applied library scope, retain retry reasons for excluded assets, and work with a partially indexed library after the bounded retry. Test a large catalog with a small changed subset as well as initial bootstrap, stale source changes, preview failures, and exact-verification correctness. Do not use the bundled mock service as sole evidence of production readiness.

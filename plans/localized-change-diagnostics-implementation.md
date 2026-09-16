# Localized change diagnostics implementation

This branch adds diagnostic-only localized visual evidence for duplicate review without changing automatic duplicate decisions.

## Intent

The goal is to make high global-similarity pairs explainable when localized content differs. The implementation keeps coarse candidate discovery unchanged, reuses bounded detail samples, exposes a read-only diagnostic grid, and adds a v2 comparison mode that overlays local change percentages on the selected image.

## Safety constraints

- Diagnostics are read-only and do not change deletion, stacking, keeper selection, or duplicate classification.
- Detail work remains candidate-only and bounded by the existing detail byte and concurrency limits.
- Cached detail samples remain tied to the current source identity.
- Missing detail evidence returns an unavailable diagnostic result rather than generating unbounded work from the UI request.

## Validation

The branch includes backend regression tests for local edits, transcoding tolerance, stale/incompatible samples, detail-source fallback behavior, the diagnostics API, and route registration. Frontend tests cover response parsing, unavailable results, malformed grids, and abort propagation.

## Follow-up

After the diagnostic path is validated against real screenshot-heavy false positives, the collected local-change evidence can inform a separate, fixture-tuned duplicate-validation policy. That policy should remain distinct from candidate discovery and should be introduced only with explicit regression fixtures and safety review.

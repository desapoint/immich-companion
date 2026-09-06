# Interface Behavior Standardization — Implementation Progress

**Branch:** `feat/standardize-interface-behavior`

**Baseline:** [`interface-behavior-current-state-inventory.md`](./interface-behavior-current-state-inventory.md)

**Target behavior:** [`interface-behavior-standardization-proposal.md`](./interface-behavior-standardization-proposal.md)

## Implemented in the first slice

### Shared HTTP mechanics

Added `frontend/src/lib/api/http.ts` with:

- consistent `Accept: application/json` handling;
- `json` request-body serialization;
- structured `ApiError` containing HTTP status and API detail;
- fallback HTTP error messages;
- native `AbortSignal` propagation;
- `request`, `requestJson`, and `requestVoid` helpers.

Relations now use the shared HTTP layer instead of maintaining a feature-local `fetch`/JSON/error parser.

### Normalized page contract

Added `PageResult<T>` under `frontend/src/lib/types/collection.ts`:

```ts
interface PageResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  pages: number;
  total: number;
}
```

The Relations API adapts its existing backend `page_size` response into this frontend shape. No backend API change was required.

### Generic collection state

Added `frontend/src/lib/state/collectionState.ts` with shared behavior for normal paged collections:

- initial loading;
- refreshing with existing data retained;
- loading the next page;
- request cancellation;
- stale-response generation protection;
- page clamping when the requested page no longer exists;
- retryable errors;
- page/page-size reset operations;
- optional stable-key deduplication for appended pages;
- explicit disposal/abort behavior.

The controller deliberately does not own domain mutations, forms, selection rules, background tasks, or viewer state.

### Albums / Tags migration

`RelationManagementPage.svelte` now uses the generic collection controller and shared `Pagination.svelte`.

User-facing changes:

- text search is live with a 300 ms debounce;
- Enter applies search immediately;
- clearing search reloads immediately;
- search and sort changes reset to page 1 and clear query-scoped selection;
- stale list requests are cancelled/ignored;
- an initial list failure shows a blocking Retry state;
- a refresh failure retains the existing table and shows a non-blocking Retry notice;
- refreshing keeps existing rows visible;
- numbered shared pagination replaces the feature-local Previous/Next controls;
- selection can survive page navigation within the same applied query;
- “Select all visible” adds/removes only the rendered page instead of replacing the entire selection set;
- create/update errors stay inside the editor dialog;
- create/update/delete mutation state is separate from list-loading state;
- single-item delete no longer overwrites unrelated existing selection;
- partial bulk-delete failures remain selected for retry.

Tag tree expansion/parent behavior and the rule that deleting a relation never deletes media are preserved.

## Tests added or updated

- shared HTTP client tests;
- collection state tests for:
  - initial loading versus refresh;
  - stale request cancellation;
  - retaining data on refresh failure;
  - append deduplication;
  - out-of-range page clamping;
- Relations API tests now verify normalized page results and abort-signal forwarding.

## Validation status

The repository workflow runs frontend checks/tests on pull requests, `main`, or manual dispatch, but not on ordinary pushes to this feature branch. The current execution environment also cannot resolve GitHub directly to clone the branch and run `npm ci` locally.

Therefore the implementation has been statically reviewed and test coverage has been added, but `npm run check` / `npm test` still require repository CI or another environment with the frontend dependencies installed before merge.

## Next implementation slice

1. Migrate Restore list loading to the generic collection controller while preserving viewer-detail cancellation and immediate restore semantics.
2. Migrate remaining simple feature API modules to the shared HTTP client.
3. Add reusable collection error/empty/loading presentation only after at least Relations and Restore prove the behavior is genuinely shared.
4. Adopt shared mechanics in Assets incrementally; do not rewrite its selection, task, or infinite-scroll domain behavior.

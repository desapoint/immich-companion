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

`RelationManagementPage.svelte` uses the generic collection controller and shared `Pagination.svelte`.

User-facing behavior includes:

- text search is live with a 300 ms debounce;
- Enter applies search immediately;
- clearing search reloads immediately;
- search and sort changes reset to page 1 and clear query-scoped selection;
- stale list requests are cancelled/ignored;
- an initial list failure shows a blocking Retry state;
- a refresh failure retains the existing table and shows a non-blocking Retry notice;
- refreshing keeps existing rows visible;
- numbered shared pagination replaces feature-local Previous/Next controls;
- selection can survive page navigation within the same applied query;
- “Select all visible” adds/removes only the rendered page instead of replacing the entire selection set;
- create/update/delete mutation state is separate from list-loading state;
- single-item delete does not overwrite unrelated existing selection;
- partial bulk-delete failures remain selected for retry.

Tag tree expansion/parent behavior and the rule that deleting a relation never deletes media are preserved.

## Implemented in the second slice

### Restore collection migration

`RestorePage.svelte` now uses the same collection controller as Relations and uses the generic `Pagination.svelte` directly.

Preserved Restore-specific behavior:

- fixed page size of 48;
- selection can survive page navigation within the same trash collection;
- Restore actions remain immediate because they are reversible recovery actions;
- viewer detail requests retain their own independent `AbortController`;
- opening a new viewer asset aborts the superseded detail request;
- page changes and component disposal close/abort viewer detail work.

Standardized behavior gained by Restore:

- initial loading, refresh, retry, and page clamping come from `collectionState`;
- stale list requests are automatically cancelled/ignored;
- refresh failures retain the existing grid;
- collection errors are separate from restore-action errors;
- Restore success/failure is reported as a normal status notice;
- successful restore reloads through the collection controller so final-page deletion/restoration clamps correctly.

### Shared collection presentation

Added `CollectionFeedback.svelte` and migrated both Relations and Restore to it.

It standardizes:

- initial loading presentation;
- blocking initial-load failure with Retry;
- non-blocking refresh failure with Retry while existing content remains usable;
- refresh-in-progress presentation;
- empty-state presentation;
- optional empty-state action.

Relations now distinguishes query-empty from source-empty and offers `Clear search` for query-empty results.

### Shared status / notification presentation

Added `StatusNotice.svelte` with `info`, `success`, `warning`, and `error` tones plus optional action and dismiss controls.

Relations now uses one mutation notice channel instead of separate page-level success/error paragraphs:

- successful create/update/delete -> success notice;
- partial delete -> one warning notice, with failed IDs kept selected;
- request/mutation failure -> error notice;
- tag-parent-option load failure -> warning notice.

Restore uses the same notice component for restore success/failure.

Collection loading errors remain in `CollectionFeedback`; form errors remain inside the active form. This keeps feedback scoped to the operation that produced it.

### Standard dialog-form behavior

Added `DialogFormActions.svelte` and extended `Dialog.svelte` with opt-in `initialFocus="first"` behavior.

The dialog continues to restore focus to the control that opened it and lock body scrolling. The focus trap now includes buttons, inputs, textareas, and selects.

Relations create/edit forms now standardize these rules:

- the first form control receives focus when the editor opens;
- Enter submits the owning form;
- Cancel, Escape, backdrop close, and the dialog close control all use the same close path;
- Escape/backdrop close are disabled while a mutation is running;
- Cancel/submit buttons use the shared action row and consistent busy labels;
- submit remains disabled when the trimmed required name is empty;
- API/form failures stay inside the dialog as an error notice;
- successful create/update closes the dialog and emits a success notice outside it;
- cancelling a simple relation form discards its draft immediately; no dirty-form confirmation is introduced for these simple CRUD forms.

## Tests added or updated

First slice:

- shared HTTP client tests;
- collection state tests for initial loading versus refresh, stale request cancellation, retained-data refresh failure, append deduplication, and out-of-range page clamping;
- Relations API tests for normalized page results and abort-signal forwarding.

Second slice:

- `StatusNotice` SSR tests for alert/status semantics and actions;
- `CollectionFeedback` SSR tests for blocking initial failure and non-blocking refresh/empty states;
- `DialogFormActions` SSR tests for form targeting, disabled state, and busy labels.

## Validation status

The repository workflow runs frontend checks/tests on pull requests, `main`, or manual dispatch, but not on ordinary pushes to this feature branch. The current execution environment also cannot resolve GitHub directly to clone the branch and run `npm ci` locally.

Therefore the implementation has been statically reviewed and test coverage has been added, but `npm run check` / `npm test` still require repository CI or another environment with the frontend dependencies installed before merge.

## Next implementation slice

1. Migrate remaining straightforward feature API modules to the shared HTTP client.
2. Standardize URL/query-state ownership for search, filters, sort, page, and view mode where appropriate.
3. Standardize pagination details such as page-size reset and post-page-change scrolling.
4. Adopt shared collection/status mechanics in Assets incrementally without rewriting its selection, task, viewer-navigation, or infinite-scroll guarantees.
5. Keep Duplicates domain persistence and resolution behavior specialized; only adopt generic HTTP/presentation primitives where safe.

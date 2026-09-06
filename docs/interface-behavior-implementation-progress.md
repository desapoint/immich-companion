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

## Implemented in the third slice

### Pagination details

Shared pagination now has explicit detail behavior rather than leaving each feature to interpret it differently:

- the summary reports the visible item range and total, for example `76–83 of 83 · Page 4 of 4`;
- current/total pages remain clamped before rendering;
- duplicate or invalid page-size selections do not emit page-size changes;
- page-size ownership remains with the collection using the component; the generic collection controller resets a changed page size to page 1;
- feature-local fixed page sizes, such as Restore's 48, remain supported without exposing a selector;
- Relations and Restore scroll the collection start into view only after a requested numbered page loads successfully;
- a failed page request therefore keeps both the old data and the user's current scroll position;
- the existing collection page-clamping behavior remains responsible for mutations that remove the last item from a final page.

`paginationItemRange()` and `scrollToPaginationStart()` live in the shared pagination utility so list screens do not each invent those rules.

### Viewer navigation across page boundaries

The asset viewer's existing adjacent-page request contract is now treated as the standard viewer-pagination bridge:

- left / `H` navigates to the previous loaded item;
- right / `L` navigates to the next loaded item;
- when navigation reaches a loaded-page edge, the viewer can call `onrequestprevious` / `onrequestnext` without closing;
- the caller fetches the adjacent page and returns the index that should become active;
- the viewer ignores repeated edge requests while one adjacent-page request is already running.

Assets already used this contract for numbered pages and infinite scroll, so its existing page-aware navigation is preserved rather than rewritten.

Restore now implements the same contract. Navigating forward from the final image on a Restore page fetches the next trash page and opens its first image. Navigating backward from the first image fetches the previous page and opens its final image.

Restore keeps a transition snapshot of the currently viewed asset while an adjacent numbered page is loading. This prevents a short final page from temporarily invalidating an index inherited from a fuller previous page.

### Reusable keyboard-shortcut help

Added `frontend/src/lib/components/ui/ShortcutHelp.svelte` and `ShortcutHelpItem`.

The component accepts data only:

```ts
interface ShortcutHelpItem {
  shortcut: string;
  description: string;
}
```

The component owns:

- the keyboard-icon help button;
- hover presentation;
- keyboard focus presentation;
- optional pinned-open state through the button;
- accessible expanded/controls relationships;
- rendering the shortcut/description list.

The asset viewer now uses this generic component instead of a viewer-specific shortcut-help implementation. Its existing `?` shortcut pins/unpins the help while ordinary pointer hover reveals it without requiring a click.

The viewer help reflects the keyboard controls that are actually handled, including:

- `←` / `H` — previous image, dynamically requesting the previous page at a page edge;
- `→` / `L` — next image, dynamically requesting the next page at a page edge;
- `Space` — toggle selection;
- `I` — toggle information;
- `M` — toggle fit / actual size;
- `+` / `−` — zoom;
- `0` — reset zoom;
- `Ctrl + Wheel` — zoom at the pointer;
- drag — pan a zoomed image;
- `?` — pin/unpin shortcut help;
- `Esc` / `Q` — close the viewer.

Duplicate review additionally documents `K`, `D`, `S`, `P`, held `F`, and `R` for its domain-specific comparison actions.

## Tests added or updated

First slice:

- shared HTTP client tests;
- collection state tests for initial loading versus refresh, stale request cancellation, retained-data refresh failure, append deduplication, and out-of-range page clamping;
- Relations API tests for normalized page results and abort-signal forwarding.

Second slice:

- `StatusNotice` SSR tests for alert/status semantics and actions;
- `CollectionFeedback` SSR tests for blocking initial failure and non-blocking refresh/empty states;
- `DialogFormActions` SSR tests for form targeting, disabled state, and busy labels.

Third slice:

- pagination utility tests for visible ranges, clamping, empty totals, and standard page-start scrolling;
- `Pagination` SSR tests for range/page summaries and opt-in page-size controls;
- `ShortcutHelp` SSR tests for its collapsed button and data-driven open content.

## Validation status

The repository workflow runs frontend checks/tests on pull requests, `main`, or manual dispatch, but not on ordinary pushes to this feature branch. The current execution environment also cannot resolve GitHub directly to clone the branch and run `npm ci` locally.

Therefore the implementation has been statically reviewed and test coverage has been added, but `npm run check` / `npm test` still require repository CI or another environment with the frontend dependencies installed before merge.

## Next implementation slice

1. Migrate remaining straightforward feature API modules to the shared HTTP client.
2. Standardize URL/query-state ownership for search, filters, sort, page, and view mode where appropriate.
3. Standardize search/filter control details and selection-toolbar conventions.
4. Adopt shared collection/status mechanics in Assets incrementally without rewriting its selection, task, viewer-navigation, or infinite-scroll guarantees.
5. Keep Duplicates domain persistence and resolution behavior specialized; only adopt generic HTTP/presentation primitives where safe.

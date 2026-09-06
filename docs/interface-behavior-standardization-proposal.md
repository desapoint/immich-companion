# Interface Behavior Standardization Proposal

**Status:** In progress; first shared HTTP/collection/Relations migration slice implemented.

**Branch:** `feat/standardize-interface-behavior`

**Baseline:** [`interface-behavior-current-state-inventory.md`](./interface-behavior-current-state-inventory.md)

**Implementation progress:** [`interface-behavior-implementation-progress.md`](./interface-behavior-implementation-progress.md)

## Goal

Reduce page-specific behavior and duplicated request/state logic while preserving domain-specific safety guarantees.

The standardization should make common list and CRUD screens predictable without forcing every feature into one oversized generic abstraction.

The primary rule is:

> Standardize mechanics and user expectations, not domain workflows.

Assets, Relations, Restore, Duplicates, Settings, and Status should share common request/error/loading primitives where appropriate, but Duplicates must retain its persistence/review guarantees and background tasks must remain separate from ordinary CRUD state.

## Recommended simplifications

### 1. Centralize HTTP mechanics once

Current feature APIs implement their own `fetch`, `response.ok`, JSON parsing, and error-message behavior.

Introduce a shared API client under `frontend/src/lib/api/` with a small surface such as:

- `request()` for responses where the caller needs the raw `Response`;
- `requestJson<T>()` for JSON;
- `requestVoid()` for `204`/empty responses;
- one `ApiError` shape containing at least HTTP status and user-facing detail;
- automatic `Accept: application/json`;
- automatic JSON body/content-type handling where requested;
- native `AbortSignal` support through `RequestInit`.

Feature API modules should continue describing domain endpoints. They should not repeat generic HTTP parsing/error code.

Do **not** build a generic REST repository that invents endpoint conventions. The backend endpoints are not uniform enough for that to simplify the application.

### 2. Add one reusable collection/request-state primitive

`frontend/src/lib/state/` currently does not contain generic remote-data state. Introduce a small collection controller for normal page-based lists.

It should own only mechanics common to lists:

- current data;
- page;
- page size;
- total/page count;
- query/search/filter/sort identity;
- initial loading;
- refreshing;
- loading more;
- load error;
- request cancellation;
- stale-response protection;
- reload/reset;
- change page/page size;
- optional append-next-page for infinite mode.

It should **not** own:

- duplicate decisions;
- asset action planning;
- background tasks;
- domain mutation rules;
- settings forms;
- viewer state.

A page should be able to use the same collection state with either numbered pagination or an infinite-load trigger.

### 3. Use four clearly different busy states

Instead of each page inventing combinations of `loading`, `busy`, `saving`, and `restoring`, common behavior should distinguish:

1. **Initial loading** — no usable data exists yet.
2. **Refreshing** — usable data already exists and is being revalidated/replaced.
3. **Loading more** — an additional page is being appended.
4. **Mutating** — a create/update/delete/domain action is running.

Rules:

- Initial loading can replace the collection content with a loading state.
- Refreshing should normally keep existing content visible.
- Loading more should never hide already loaded items.
- A mutation should disable only controls that conflict with that mutation unless the domain operation truly locks the workspace.

This removes the overloaded global `busy` behavior currently used by Relations while retaining specific operation scopes where Settings or Duplicates need them.

### 4. Standardize errors by operation type

Use consistent error behavior:

- **Initial list failure:** blocking collection error with Retry.
- **Refresh/page failure with existing data:** keep existing data and show a non-blocking error/retry notice.
- **Load-more failure:** keep all loaded items and put Retry at the end of the list.
- **Form/create/update failure:** keep the form/dialog open and show the error in that interaction.
- **Delete/bulk mutation failure:** keep successful state changes where the API reports them, disclose partial failures, and allow retry of failed targets when practical.
- **Background-task failure:** persistent/resumable task error, not a generic CRUD error.

Routine errors should not destroy otherwise usable content.

### 5. Standardize stale-request protection

Every list or detail request that can be superseded should follow the Assets/Restore pattern:

- abort the previous request when a new request supersedes it;
- ignore `AbortError` as a user-visible failure;
- use a request generation/token when multiple requests can compose one result or when an old result could still race the new one.

This should become automatic in the collection primitive instead of being reimplemented page-by-page.

### 6. Simplify search behavior into two supported modes

There are legitimate reasons not to make every search behave identically. Support exactly two search interaction modes:

#### Live text search

Use for simple text collections such as Albums/Tags.

Recommended behavior:

- 300 ms debounce;
- Enter executes immediately and cancels the pending debounce;
- clearing the field reloads immediately;
- a new query resets page to 1;
- sort/filter changes reset page to 1;
- stale requests are aborted/ignored.

#### Explicit/advanced search

Use for Assets, where search includes structured simple/expert filters.

Recommended behavior:

- keep draft filters separate from the applied query;
- Search/Apply explicitly commits the query;
- Reset explicitly applies the empty/default query;
- sort changes may remain immediate;
- applying a new query resets page to 1 and clears query-scoped selection.

Do not force debounce onto the structured Assets search merely for consistency.

### 7. Define one page-result shape inside the frontend

Use one normalized frontend collection result even if backend endpoints are migrated gradually:

```ts
interface PageResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  pages: number;
  total: number;
}
```

Adapters can normalize existing endpoint field names at feature API boundaries.

The first standardization pass does not need to rewrite every backend response if a frontend adapter is sufficient.

### 8. Use the existing shared Pagination component everywhere

`frontend/src/lib/components/ui/Pagination.svelte` is already a capable generic component with page numbers, boundaries, first/last, previous/next, summary, and optional page-size selection.

Recommended changes:

- Relations should stop rendering its own Previous/Next pagination and use shared `Pagination`.
- Restore can continue using the shared pagination implementation but should eventually bypass asset-specific wrapping when it does not need asset-only behavior.
- Assets may retain an adapter temporarily, but list-mode selection should not live inside the generic pagination concept.

Long term, `AssetPagination.svelte` should either become a very thin asset adapter or be removed if it no longer adds meaningful behavior.

### 9. Treat infinite scroll as a view mode over pagination

Do not create a second data model for infinite scrolling.

Infinite scrolling should:

- call the same collection `loadNextPage()` operation;
- request one additional page at a time during normal scrolling;
- prevent overlapping next-page loads;
- deduplicate by stable item ID;
- expose `loading more`, `retry`, and `end of results` states;
- preserve already loaded data on failure;
- disconnect its observer when there is no next page.

The existing Assets behavior already follows most of this model.

Do not make every screen support infinite scroll. It is a capability a collection may opt into, not a universal UI requirement.

### 10. Simplify post-mutation refresh rules

Avoid a blanket “reload everything after every mutation” rule.

Use this preference order:

1. **Patch from canonical mutation response** when the server returns the updated entity and membership in the current query is known to remain valid.
2. **Remove locally** for a confirmed delete/restore-away operation when the entity cannot remain in the current collection.
3. **Revalidate the current collection** when search/sort/filter membership may have changed.
4. **Rebuild an infinite loaded window** only when correctness requires it and a cheaper patch/revalidation cannot determine the result.

This reduces unnecessary API/load while keeping the UI correct.

For Assets specifically, preserve the current scroll-anchor restoration until an equivalent collection-level implementation exists. Do not remove that behavior merely to reduce code.

### 11. Standardize generic selection scope

For normal pageable CRUD lists:

- selection is scoped to the **applied query**;
- selection may survive changing pages inside that same query;
- changing search/filter/sort clears selection;
- “Select all visible” means the current rendered page/window only;
- “Select all matching” must be a separate explicit capability backed by server semantics when the result set is larger than loaded data;
- destructive bulk actions must always disclose their target count.

Domain exceptions:

- Assets retains server-backed all-matching selection and range/drag selection.
- Duplicates retains persisted workspace selection and its explicit warning that manually selected hidden groups remain included.

Do not force those advanced semantics into simple Relations/Restore lists.

### 12. Make confirmation rules predictable

Recommended policy:

- destructive or difficult-to-reverse operations: confirm;
- complex operations whose consequences must be reviewed: plan/preview, then confirm;
- reversible recovery (`Restore`): no confirmation required;
- ordinary create/update/settings save: no confirmation required;
- bulk operation targeting unusually many items: confirmation can be required even if the single-item equivalent does not require one.

This preserves current safety intent while making the rule explainable.

### 13. Stop using confirmation dialogs for success acknowledgement

A success message should not generally require another confirmation action.

Recommended behavior:

- routine create/update/delete/save: inline status notice or transient notification;
- background task completion: persistent status notice until the user moves on/dismisses it when important;
- confirmations remain for decisions **before** an action.

The current Assets “Synchronization completed” / “Action completed” use of `ConfirmDialog` should eventually be replaced by a normal status/notification component.

### 14. Standardize empty states into two meanings

Every searchable/filterable collection should distinguish:

- **Source empty:** there is genuinely no data.
- **Query empty:** data source exists, but nothing matches the active query/filter.

Source-empty may offer a domain action such as Sync/Create.

Query-empty should normally offer Clear search/filters rather than source initialization actions.

Duplicates already follows this distinction and Assets partially does.

### 15. Keep background tasks outside generic CRUD state

Assets and Duplicates have long-running/task semantics that include polling/live updates, cancellation, persistence, retry, and resume.

Do not add task fields to the generic collection controller.

If task behavior is standardized later, create a separate task-tracking primitive that can be used independently of collection state.

## What should deliberately remain different

Standardization should **not** make these behaviors identical:

- Assets advanced search versus simple text search.
- Assets all-matching/range/drag selection versus ordinary list selection.
- Duplicates persistent hidden selection and decision draft queues.
- Duplicates plan/resume semantics.
- Restore's reversible action semantics versus delete confirmation.
- Settings section-specific save state versus list mutation state.
- Status read-only resource loading versus pageable collection behavior.

These differences represent product/domain behavior rather than accidental duplication.

## Recommended target architecture

```text
frontend/src/lib/
  api/
    http.ts                  shared request/error handling
  state/
    collectionState.ts       generic list request state
  types/
    collection.ts            PageResult<T>
  components/ui/
    Pagination.svelte        existing generic pagination
    CollectionError.svelte   common blocking/non-blocking retry presentation
    CollectionEmpty.svelte   source-empty/query-empty presentation
    InfiniteLoadTrigger.svelte observer + loading/retry/end presentation
    StatusNotice.svelte      success/warning/error informational feedback
```

## Recommended implementation order

### Phase 1 — Shared HTTP client

1. Add `ApiError` and request helpers.
2. Migrate one small API module, preferably Relations.
3. Add tests for JSON success, empty success, structured API error, fallback HTTP error, and abort propagation.
4. Migrate remaining feature API helpers incrementally.

### Phase 2 — Generic page collection state

1. Add normalized `PageResult<T>`.
2. Add collection loading/refresh/loading-more/error/cancellation behavior.
3. Add tests for race cancellation, page reset, page clamping, retained-data refresh failure, and append deduplication.

### Phase 3 — Relations as the first migration

Use Albums/Tags as the first generic CRUD pilot because they are small and currently duplicate the most basic mechanics.

Change Relations to:

- shared HTTP client;
- collection state;
- debounced live text search;
- shared `Pagination`;
- initial vs refresh errors;
- query-scoped selection;
- operation-scoped create/update/delete state.

Do not change tag-tree domain behavior.

### Phase 4 — Restore

Adopt collection state and shared error/empty/pagination semantics while preserving:

- fixed page size if still desired;
- cross-page selection within the same query scope;
- immediate reversible restore;
- viewer detail cancellation.

### Phase 5 — Assets incremental adoption

Do **not** rewrite `AssetWorkspace` wholesale.

Move only proven shared mechanics into the common layer:

- HTTP request handling;
- normalized page result where practical;
- generic initial/refresh/load-more semantics;
- common pagination/infinite trigger presentation.

Preserve existing advanced behavior until equivalent tests exist:

- request generations;
- infinite deduplication;
- scroll-anchor restoration;
- server selection;
- viewer navigation across pages;
- task recovery/live updates;
- mutation planning.

### Phase 6 — Settings and Status

Adopt the shared HTTP/error presentation primitives where they simplify code.

Do not force either screen through pageable collection state.

### Phase 7 — Duplicates last

Only adopt generic HTTP/error/presentation helpers that do not interfere with duplicate-review persistence and safety behavior.

Do not migrate duplicate drafts, selection, task polling/resume, or plan execution into generic CRUD abstractions.

## First concrete code changes recommended

The first implementation slice is complete. See [`interface-behavior-implementation-progress.md`](./interface-behavior-implementation-progress.md).

## Acceptance principles

The standardization is successful when:

- feature API files do not repeat generic HTTP error parsing;
- ordinary pageable lists do not each implement cancellation/page/reset/loading semantics themselves;
- Pagination behavior is visually and functionally consistent;
- live text search behaves consistently where used;
- infinite scroll and numbered pages can consume the same collection contract;
- existing data remains usable during refresh and incremental-load failures;
- routine mutations do not disable unrelated parts of a page;
- destructive actions remain explicitly guarded;
- domain-specific behavior in Assets and Duplicates is preserved rather than generalized away;
- behavior is covered by unit/E2E tests before old implementations are removed.

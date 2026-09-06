# Interface Behavior Current-State Inventory

**Status:** Current-state audit complete; no standardization behavior is proposed or implemented by this document.

**Application repository:** `desapoint/immich-companion`

**Application source revision audited:** `ea7118ac6fc36e175452c99b9566d3e02c2baba9` (`main`)

**Implementation branch:** `feat/standardize-interface-behavior`

## Purpose

This document records the interface and interaction behavior that is implemented today before CRUD, API state, pagination, infinite scroll, search, loading, error, selection, and mutation behavior are standardized.

The application source is authoritative. This inventory intentionally describes current behavior, including inconsistencies. It must not be read as a target-state specification.

## Routed interface scope

`frontend/src/app/App.svelte` currently routes the application to these user-facing workspaces:

- `/assets` and `/assets/*` -> Assets
- `/albums` -> Albums
- `/tags` -> Tags
- `/restore` -> Restore
- `/duplicates` -> Duplicates
- `/settings` -> Settings
- every other path -> Status dashboard

The duplicate preview is rendered as a top-level viewer controller over the routed page.

## Current behavior matrix

| Area | Initial loading | Error and retry | Search / filtering | Refresh behavior | Pagination / infinite scroll | Selection | Mutations / CRUD / confirmation | Empty state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Assets** | Dedicated `AssetLoadingState` while the first result is absent. Subsequent loads set `loading=true` while an existing result may still exist. | Search errors are normalized to a message and shown through `AssetErrorState` with retry. Requests use `AbortController`; aborted requests are ignored. Detail and selection requests also have independent errors. | Simple and expert search modes. Search is explicitly submitted/reset rather than debounced. Sort changes execute a search immediately. Search change resets page to 1, closes viewer state, clears selection, then loads. `albumId` / `tagId` URL parameters seed filters on mount only. | Explicit result reload after search/page changes and after many mutations. Sync status is polled every 1.5 s and task updates also arrive through `TaskUpdateConnection`. After mutations, paged mode reloads; infinite mode rebuilds the loaded window and attempts to preserve scroll position. | Supports paged and infinite modes over the same search API. Paged mode supports page size changes. Infinite mode uses an `IntersectionObserver` with `640px` root margin, deduplicates appended asset IDs, prevents overlapping loads, and tracks request generation. Infinite refresh can reload prior pages in batches of four and restore a surviving scroll anchor. List mode is persisted in local storage. | Rich selection: single toggle, shift range, mouse drag range, select page, invert page, and select every matching result. All-matching selection is represented server-side. Selection membership can be synchronized with the server across pages. Search changes clear selection. | Asset actions are planned before destructive/general execution. Selection actions commonly execute as background tasks; viewer actions can execute immediately. Bulk/task progress, cancellation, failure dialogs, completion dialogs, retry of failed selection sync, synchronization, relation actions, stack actions, and post-mutation refresh are implemented. | Dedicated `AssetEmptyState`. When there is no active search, the empty state can offer sync; filtered empty results do not expose the same sync call-to-action. |
| **Albums** | `busy && !items.length` shows plain `Loading…`. | Inline `error` text; no dedicated retry control. The next user action/load can retry. | Text input executes search only when Enter is pressed. Search sets page to 1. Sorting by name or asset count reloads immediately and resets page to 1. | `load()` replaces the current page. No request cancellation or stale-response generation guard is implemented in the page. Create/update/delete all call `load()` afterward. | Previous/Next pagination only, shown when `pages > 1`. If the requested page is beyond the returned last page, it clamps to the last page and loads again. No infinite scroll or page-size control. | Checkbox selection. “Select all visible” replaces selection with IDs in the current rendered page. Individual selection can remain in the set while navigating until explicitly changed/cleared. | Create and edit use a shared dialog. Delete one and delete selected use `ConfirmDialog`; copy explicitly states media is not deleted. Successful create/update/delete reload the list. Delete results can report partial failures. | Plain `No albums found.` |
| **Tags** | Same shared relation page behavior as Albums. | Same as Albums. Loading tag options for the parent selector is best-effort; the management request is expected to surface the actionable error. | Same Enter-to-search behavior and sortable columns. Search changes tree projection: matching rows can show parent paths. | Same `load()` model as Albums. | Same Previous/Next pagination as Albums. | Same page-visible selection behavior as Albums. Tags additionally maintain expanded tree node state. | Same create/update/delete dialog/confirmation behavior. Tag create/edit supports color and parent tag. | Plain `No tags found.` |
| **Restore** | Plain `Loading trashed assets…` on first load. | Initial load failure has inline error plus explicit Retry. Later load failures are shown inline while existing items remain. List and detail requests use independent `AbortController`s. | No search/filter UI. | Loading a page replaces `items`. Restore-one, restore-selected, and restore-all reload the current page after completion. | Fixed page size `48`; shared `AssetPagination` is used with page-size changes disabled and no list-mode toggle. No infinite scroll. Page requests clamp to the last available page. | Selection uses asset IDs and is not cleared by ordinary page loads, allowing manually selected IDs to survive page navigation. “Select all” applies to loaded/current-page assets only. | Restore one, selected, or all. Restore is not guarded by a confirmation dialog. A single `restoring` state disables competing restore actions. Viewer can also invoke restore. | Plain `Immich's trash is empty.` |
| **Duplicates** | Initial `Loading Immich duplicate groups…`; when data already exists, `loading` renders `Refreshing duplicate groups…`. | Inline errors. Resolution failures can expand into per-group unfinished execution state and can offer resume. Task-progress failures are surfaced; some incomplete resolution work is explicitly resumable. | No text search. Review filters are client-side projections over the fully loaded result with counts for workflow states. Policy/library controls affect analysis/rules rather than list pagination. | `load()` retrieves duplicate groups, latest similarity scan, scan tasks, and persisted workspace state. Background task state is polled every 700 ms while active. Completed tasks call `load()` again. No request abort/generation mechanism is visible in the page. | No pagination or infinite scroll; all returned groups are rendered/filtered locally. | Persistent workspace selection. Manual selections can remain selected while hidden by a review filter and are explicitly included in bulk targets. Supports select-auto-ready, per-group select, bulk actions, clear decisions, and an active group. | Group draft changes are delayed by 250 ms and serialized per group; workspace selection saves are queued. Best-effort draft flushing occurs on unmount. Resolution is planned/reviewed before execution. Destructive batches use `ConfirmDialog`, report retained/deleted/stack counts, and can resume incomplete follow-up work. Similarity scans can be cancelled. | Distinguishes no duplicate groups from no groups matching the active review filter. |
| **Settings** | Full-page `Loading sync settings…`. | Initial `Promise.all` failure produces one shared error state. If schedules are empty, that error replaces the settings content. No explicit retry button is present. Save errors share one page-level error message. | No collection search/filter. Duplicate policy uses select/multiselect controls; schedules have preset buttons and raw cron input. | Initial settings are loaded once on mount. Each save updates its own returned state; there is no background refresh/polling. | None. | None. | Independent save flows exist for schedules (`saving` keyed by schedule name), runtime load settings (`runtimeSaving`), and duplicate policy (`duplicateSaving`). No confirmation dialog is used for settings saves. Inputs enforce some client-side numeric bounds before runtime save. | No dedicated empty state; the page expects configured schedule records after load. |
| **Status** | Explicit tagged state `{ kind: 'loading' }` rendered through `StatusLoading`. | Explicit `{ kind: 'error' }` rendered through `StatusError` with retry. | None. | `refresh()` replaces loaded content with loading state, then either loaded snapshot or error. It runs on mount and on user retry; no automatic polling is implemented in `StatusDashboard.svelte`. | None. | None. | Read-only. | No explicit collection empty state at the page-controller level. |

## Detailed current-state findings

### 1. Assets is the most complete interaction model

The Assets workspace already implements several behaviors that other screens do not:

- abortable search/detail/selection requests;
- a request generation guard for asset result loading;
- persisted paged/infinite list mode;
- reusable paged rendering through `AssetPagination` / shared `Pagination`;
- ID deduplication while appending infinite results;
- prevention of concurrent infinite loads;
- scroll-anchor preservation after mutations in infinite mode;
- server-backed all-matching selection and membership reconciliation;
- background task recovery using task IDs in local storage;
- task updates plus polling for sync/task state;
- planning/confirmation before guarded actions;
- dedicated initial loading, error/retry, and empty states.

One important current behavior is that search is **not debounced**. Simple/expert controls mutate draft state locally and call `onsearch` only on explicit search/reset; changing sort calls search immediately.

### 2. Assets pagination and infinite scroll are already coupled to the same page-based API

Infinite scrolling is currently implemented by requesting ordinary numbered pages and appending their items. It is not a separate backend pagination contract.

When infinite results need to be refreshed after a mutation, the workspace reloads page 1 and then reloads pages through the previously loaded page. Those subsequent pages are fetched in batches of four. The result items are merged/deduplicated and the viewport is restored using a surviving visible asset as an anchor when possible.

This is current behavior only; whether it becomes the standard implementation is a later design decision.

### 3. Albums and Tags share behavior but own their data lifecycle locally

Albums and Tags both use `RelationManagementPage.svelte`. The component directly owns:

- collection data;
- page and page count;
- search text;
- sort/direction;
- selection;
- create/edit form state;
- delete confirmation state;
- global `busy`, error, and success message state.

The page makes direct feature API calls for list/create/update/delete. Unlike Assets and Restore, relation list requests do not use an `AbortController` or request generation check. Rapid operations can therefore overlap at the page-controller level.

Search is Enter-driven. There is no debounce and no automatic request while typing.

Selection semantics are also page-specific: “select all visible” replaces the set with the visible row IDs, while individual selections otherwise remain in the set until changed or a successful delete clears them.

### 4. Restore reuses visual pagination but not the Assets collection controller

Restore uses the shared `AssetPagination` component, but it separately implements list state, loading, errors, selection, abort handling, page clamping, and viewer detail loading.

Its later-load error behavior differs from the Assets workspace: if already-loaded Restore items exist, a later load error is displayed while those items remain rendered. Assets currently routes an `error` result into `AssetErrorState` before rendering the result grid.

Restore uses a fixed page size and does not expose infinite scroll.

### 5. Duplicate review has a persistence-heavy workflow rather than a generic collection model

Duplicate review does not paginate. It loads groups as a complete result and filters them locally by review status.

The workspace has behavior that must not be lost during generic interface work:

- persisted selected group IDs and active group;
- distinction between manual and automatic selection;
- manually selected hidden groups remain bulk targets;
- stale persisted selections are detected and disclosed;
- per-group decision drafts carry fingerprints/staleness;
- draft writes are debounced by 250 ms and serialized per group;
- workspace writes are serialized through a queue;
- unmount performs best-effort flushing;
- destructive resolution requires a generated plan and confirmation;
- failed multi-step resolutions expose unfinished groups and resumable work;
- similarity scanning is a cancellable background task.

These are domain guarantees, not generic list behavior.

### 6. Settings uses multiple mutation scopes with one shared page error/message channel

Settings has separate busy markers for schedule, runtime, and duplicate-policy saves, allowing those sections to manage saving independently. However, success/error feedback is shared at page level.

Initial data loading uses one `Promise.all` for schedules, runtime settings, duplicate policy, and libraries. A failure in any one of those requests causes the overall initial load to enter the error path rather than partially rendering independently loaded sections.

### 7. Status already uses an explicit load-state union

Status is the smallest and clearest load-state implementation. It models `loading`, `loaded`, and `error` as mutually exclusive states and exposes a retry handler. Refresh intentionally replaces the loaded state with the loading state instead of retaining stale content during refresh.

## Cross-screen inconsistencies recorded for later standardization

These are observations, not decisions:

1. **Loading state vocabulary differs.** Assets has initial loading plus separate task/detail/loading states; Relations use one global `busy`; Restore separates list/action/detail loading; Status uses a state union; Settings has several mutation flags.
2. **Refresh-with-existing-data differs.** Restore can retain items while surfacing a later error. Assets' current top-level result branch displays its error state instead of the grid when `error` is set.
3. **Request cancellation is inconsistent.** Assets and Restore abort stale list/detail requests. Relations, Duplicates, Settings, and Status do not use abortable page-level requests in the inspected controllers.
4. **Search behavior differs.** Assets uses explicit apply/reset plus immediate sort-triggered search. Relations search only on Enter. Duplicates has client-side workflow filters but no text search. Other routed pages have no search.
5. **Pagination is inconsistent.** Assets has shared numbered pagination, page-size controls, and optional infinite scroll. Restore reuses the pagination UI with a fixed page size. Relations implement their own Previous/Next controls. Duplicates loads all groups.
6. **Selection scope differs.** Assets supports page, ranges, all matching, and server-backed cross-page membership. Restore keeps an ID set across page loads. Relations use a local set whose visible-select operation replaces it. Duplicates persists workspace selection and intentionally preserves manually selected groups hidden by filters.
7. **Confirmation rules differ by domain.** Relation deletion and duplicate resolution are confirmed. Asset actions are planned/reviewed before execution. Restore is immediate because it is a recovery action. Settings saves are immediate.
8. **Mutation refresh strategy differs.** Assets can patch, reload, or rebuild an infinite window; Relations and Restore generally reload the current page; Settings updates returned records locally; Duplicates reloads the workspace after task completion.
9. **Background-work handling differs.** Assets combines live task updates, polling, local-storage task recovery, cancellation, and overlays. Duplicates polls active tasks and supports cancellation/resume. Other screens are request/response only.
10. **Empty-state presentation differs.** Assets uses a dedicated component and can expose sync. Restore, Relations, and Duplicates use inline text; Duplicates distinguishes global-empty from filter-empty.

## Behavior that is currently shared at the component layer

Existing common UI pieces already used across feature boundaries include:

- `ConfirmDialog`
- `Dialog`
- `Checkbox`
- `SelectField`
- `MultiSelectField`
- `IconButton`
- `LayoutModeSwitch`
- shared `Pagination` underneath `AssetPagination`

The presence of shared visual components does **not** currently imply a shared request/state/CRUD contract; most routed feature controllers still own those semantics themselves.

## Source touchpoints audited

Application revision: `ea7118ac6fc36e175452c99b9566d3e02c2baba9`

Primary files:

- `frontend/src/app/App.svelte`
- `frontend/src/features/assets/components/AssetsPage.svelte`
- `frontend/src/features/assets/components/AssetWorkspace.svelte`
- `frontend/src/features/assets/components/AssetSearchToolbar.svelte`
- `frontend/src/features/assets/components/AssetPagination.svelte`
- `frontend/src/features/assets/components/RestorePage.svelte`
- `frontend/src/features/relations/components/AlbumsPage.svelte`
- `frontend/src/features/relations/components/TagsPage.svelte`
- `frontend/src/features/relations/components/RelationManagementPage.svelte`
- `frontend/src/features/duplicates/components/DuplicatesPage.svelte`
- `frontend/src/features/duplicates/components/DuplicateReviewFilters.svelte`
- `frontend/src/features/settings/components/SettingsPage.svelte`
- `frontend/src/features/status/components/StatusDashboard.svelte`

Supporting structure reviewed:

- `frontend/src/lib/api/`
- `frontend/src/lib/state/`
- `frontend/src/lib/components/ui/`
- `frontend/src/lib/components/layout/`
- `frontend/src/lib/components/domain/`

## Audit boundary

This pass documents routed frontend controller behavior and the directly observable API/state interactions required for the standardization project. It does not yet define the standard contracts, migrate code, or claim that every lower-level backend edge case has been exhaustively catalogued.

The next standardization step should use this document as the baseline and explicitly decide which differences are domain requirements versus accidental inconsistencies.
<script lang="ts">
  import { onMount } from 'svelte';

  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import CollectionFeedback from '../../../lib/components/ui/CollectionFeedback.svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import Dialog from '../../../lib/components/ui/Dialog.svelte';
  import DialogFormActions from '../../../lib/components/ui/DialogFormActions.svelte';
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import Pagination from '../../../lib/components/ui/Pagination.svelte';
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import StatusNotice from '../../../lib/components/ui/StatusNotice.svelte';
  import {
    createCollectionController,
    createCollectionState,
  } from '../../../lib/state/collectionState';
  import type { SelectOption } from '../../../lib/types/ui';
  import {
    createRelation,
    deleteRelations,
    getRelations,
    getTagOptions,
    updateRelation,
  } from '../api/relationsApi';
  import { branchParentIds, flattenTagTree } from '../state/tagTree';
  import type { ManagedRelation, RelationKind } from '../types/relations';
  import ColorPicker from './ColorPicker.svelte';

  interface Props { kind: RelationKind; }
  type Notice = { tone: 'success' | 'warning' | 'error'; message: string };

  const relationPageSize = 25;
  const searchDebounceMs = 300;

  let { kind }: Props = $props();
  let collection = $state(createCollectionState<ManagedRelation>(relationPageSize));
  let selected = $state(new Set<string>());
  let search = $state('');
  let appliedSearch = $state('');
  let name = $state('');
  let description = $state('');
  let color = $state('#6b7cff');
  let parentId = $state('');
  let editing = $state<string | null>(null);
  let notice = $state<Notice | null>(null);
  let formError = $state<string | null>(null);
  let mutationBusy = $state(false);
  let dialogOpen = $state(false);
  let deleteConfirmOpen = $state(false);
  let pendingDelete = $state<string[]>([]);
  let pendingDeleteLabel = $state('');
  let sort = $state<'name' | 'asset_count'>('name');
  let direction = $state<'asc' | 'desc'>('asc');
  let expanded = $state(new Set<string>());
  let tagOptions = $state<{ id: string; name: string }[]>([]);
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  const title = $derived(kind === 'albums' ? 'Albums' : 'Tags');
  const isAlbum = $derived(kind === 'albums');
  const parentOptions = $derived<SelectOption[]>([
    { value: '', label: 'No parent tag' },
    ...tagOptions
      .filter((item) => item.id !== editing)
      .map((item) => ({ value: item.id, label: item.name })),
  ]);
  const displayRows = $derived(
    isAlbum
      ? collection.items.map((item) => ({ item, depth: 0, hasChildren: false }))
      : flattenTagTree(collection.items, expanded, Boolean(appliedSearch)),
  );
  const allVisibleSelected = $derived(
    displayRows.length > 0 && displayRows.every((row) => selected.has(row.item.id)),
  );
  const emptyLabel = $derived(
    appliedSearch
      ? `No ${title.toLowerCase()} match “${appliedSearch}”.`
      : `No ${title.toLowerCase()} found.`,
  );

  const collectionController = createCollectionController(
    collection,
    ({ page, signal }) => getRelations(kind, page, appliedSearch, sort, direction, signal),
    { fallbackError: 'Relations could not be loaded.', getKey: (item) => item.id },
  );

  function clearSearchTimer(): void {
    if (searchTimer === null) return;
    clearTimeout(searchTimer);
    searchTimer = null;
  }

  function expandLoadedTagBranches(): void {
    if (isAlbum || appliedSearch) return;
    expanded = new Set([...expanded, ...branchParentIds(collection.items)]);
  }

  async function runCollection(operation: () => Promise<boolean>): Promise<boolean> {
    const loaded = await operation();
    if (loaded) expandLoadedTagBranches();
    return loaded;
  }

  function applySearch(nextSearch = search): void {
    clearSearchTimer();
    const next = nextSearch.trim();
    if (next === appliedSearch && collection.hasLoaded) return;
    appliedSearch = next;
    selected = new Set();
    notice = null;
    void runCollection(() => collectionController.reset());
  }

  function clearSearch(): void {
    search = '';
    applySearch('');
  }

  function scheduleSearch(): void {
    clearSearchTimer();
    if (!search.trim()) {
      applySearch('');
      return;
    }
    searchTimer = setTimeout(() => applySearch(), searchDebounceMs);
  }

  function handleSearchKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    applySearch();
  }

  function resetForm(): void {
    editing = null;
    name = '';
    description = '';
    color = '#6b7cff';
    parentId = '';
    formError = null;
  }

  function closeForm(): void {
    if (mutationBusy) return;
    dialogOpen = false;
    resetForm();
  }

  function openCreate(): void {
    resetForm();
    name = search.trim();
    dialogOpen = true;
  }

  function edit(item: ManagedRelation): void {
    editing = item.id;
    name = item.name;
    description = item.description ?? '';
    color = item.color ?? '#6b7cff';
    parentId = item.parent_id ?? '';
    formError = null;
    dialogOpen = true;
  }

  function changeSort(next: 'name' | 'asset_count'): void {
    if (sort === next) direction = direction === 'asc' ? 'desc' : 'asc';
    else {
      sort = next;
      direction = 'asc';
    }
    selected = new Set();
    notice = null;
    void runCollection(() => collectionController.reset());
  }

  function togglePageSelection(checked: boolean): void {
    const next = new Set(selected);
    for (const row of displayRows) {
      if (checked) next.add(row.item.id);
      else next.delete(row.item.id);
    }
    selected = next;
  }

  function toggleItemSelection(id: string, checked: boolean): void {
    const next = new Set(selected);
    if (checked) next.add(id);
    else next.delete(id);
    selected = next;
  }

  function sortLabel(column: 'name' | 'asset_count'): string {
    return sort === column
      ? direction === 'asc' ? ' (ascending)' : ' (descending)'
      : '';
  }

  async function save(): Promise<void> {
    if (!name.trim() || mutationBusy) return;
    mutationBusy = true;
    formError = null;
    notice = null;
    try {
      const data = isAlbum
        ? { name: name.trim(), description }
        : { name: name.trim(), color, ...(parentId ? { parent_id: parentId } : {}) };
      const wasEditing = editing !== null;
      if (editing) await updateRelation(kind, editing, data);
      else await createRelation(kind, data);
      notice = {
        tone: 'success',
        message: `${isAlbum ? 'Album' : 'Tag'} ${wasEditing ? 'updated' : 'created'}.`,
      };
      dialogOpen = false;
      resetForm();
      await runCollection(() => collectionController.reload());
    } catch (cause) {
      formError = cause instanceof Error ? cause.message : 'Relation could not be saved.';
    } finally {
      mutationBusy = false;
    }
  }

  function removeSelected(): void {
    if (!selected.size || mutationBusy) return;
    pendingDelete = [...selected];
    pendingDeleteLabel = `Delete ${selected.size} relation${selected.size === 1 ? '' : 's'}? Media will not be deleted.`;
    notice = null;
    deleteConfirmOpen = true;
  }

  async function confirmDelete(): Promise<void> {
    if (!pendingDelete.length || mutationBusy) return;
    mutationBusy = true;
    notice = null;
    try {
      const result = await deleteRelations(kind, pendingDelete);
      selected = new Set(result.failed);
      deleteConfirmOpen = false;
      pendingDelete = [];
      notice = result.failed.length
        ? {
            tone: 'warning',
            message: `${result.completed.length} deleted; ${result.failed.length} failed and remain selected.`,
          }
        : { tone: 'success', message: `${result.completed.length} deleted.` };
      await runCollection(() => collectionController.reload());
    } catch (cause) {
      notice = {
        tone: 'error',
        message: cause instanceof Error ? cause.message : 'Relations could not be deleted.',
      };
    } finally {
      mutationBusy = false;
    }
  }

  function removeOne(item: ManagedRelation): void {
    pendingDelete = [item.id];
    pendingDeleteLabel = `Delete “${item.name}”? Media will not be deleted.`;
    notice = null;
    deleteConfirmOpen = true;
  }

  function quickFilter(id: string): void {
    window.location.href = `/assets?${isAlbum ? 'albumId' : 'tagId'}=${encodeURIComponent(id)}`;
  }

  function toggleExpanded(id: string): void {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    expanded = next;
  }

  function changePage(nextPage: number): void {
    void runCollection(() => collectionController.changePage(nextPage));
  }

  onMount(() => {
    const optionsController = new AbortController();
    if (!isAlbum) {
      void getTagOptions(optionsController.signal)
        .then((options) => { tagOptions = options; })
        .catch((cause) => {
          if (!(cause instanceof DOMException && cause.name === 'AbortError')) {
            notice = {
              tone: 'warning',
              message: cause instanceof Error ? cause.message : 'Tag parent options could not be loaded.',
            };
          }
        });
    }
    void runCollection(() => collectionController.load());

    return () => {
      clearSearchTimer();
      optionsController.abort();
      collectionController.dispose();
    };
  });
</script>

<section class="relations" class:flat-relations={isAlbum}>
  <header class="intro">
    <div><span>Immich relations</span><h1>{title}</h1></div>
    <p>Manage metadata through the Immich API. Deleting a relation never deletes media.</p>
  </header>

  <div class="toolbar">
    <input
      autocomplete="off"
      data-1p-ignore
      data-bwignore="true"
      aria-label={`Search ${title}`}
      placeholder={`Search ${title.toLowerCase()}`}
      value={search}
      oninput={(event) => {
        search = event.currentTarget.value;
        scheduleSearch();
      }}
      onkeydown={handleSearchKeydown}
    />
    <IconButton icon={isAlbum ? 'album-add' : 'tag-add'} label="Create" tone="accent" disabled={mutationBusy} onclick={openCreate} />
    <IconButton icon="trash" label="Delete selected" tone="destructive" disabled={mutationBusy || selected.size === 0} onclick={removeSelected} />
  </div>

  {#if notice}
    <StatusNotice tone={notice.tone} message={notice.message} ondismiss={() => (notice = null)} />
  {/if}

  <CollectionFeedback
    hasLoaded={collection.hasLoaded}
    initialLoading={collection.initialLoading}
    refreshing={collection.refreshing}
    error={collection.error}
    empty={collection.hasLoaded && collection.items.length === 0}
    loadingLabel={`Loading ${title.toLowerCase()}…`}
    refreshingLabel={`Refreshing ${title.toLowerCase()}…`}
    {emptyLabel}
    emptyActionLabel={appliedSearch ? 'Clear search' : undefined}
    onemptyaction={appliedSearch ? clearSearch : undefined}
    onretry={() => void runCollection(() => collectionController.reload())}
  />

  {#if collection.hasLoaded && collection.items.length > 0}
    <div class="table-wrap">
      <table>
        <colgroup>
          <col class="selection-column" />
          <col />
          <col class="count-column" />
          <col class="actions-column" />
        </colgroup>
        <thead>
          <tr>
            <th class="selection-cell">
              <div class="styled-checkbox">
                <Checkbox
                  checked={allVisibleSelected}
                  label={`Select all visible ${title.toLowerCase()}`}
                  hiddenLabel
                  onchange={togglePageSelection}
                />
              </div>
            </th>
            <th>
              <button class="sort-heading" onclick={() => changeSort('name')} aria-label={`Sort by name${sortLabel('name')}`}>
                Name <span>{sort === 'name' ? direction === 'asc' ? '↑' : '↓' : '↕'}</span>
              </button>
            </th>
            <th>
              <button class="sort-heading" onclick={() => changeSort('asset_count')} aria-label={`Sort by asset count${sortLabel('asset_count')}`}>
                Assets <span>{sort === 'asset_count' ? direction === 'asc' ? '↑' : '↓' : '↕'}</span>
              </button>
            </th>
            <th class="actions-heading">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each displayRows as row (row.item.id)}
            {@const item = row.item}
            <tr>
              <td class="selection-cell">
                <div class="styled-checkbox">
                  <Checkbox checked={selected.has(item.id)} label={`Select ${item.name}`} hiddenLabel onchange={(checked) => toggleItemSelection(item.id, checked)} />
                </div>
              </td>
              <td>
                <div class="tag-name" style={`--depth:${row.depth}`}>
                  {#if !isAlbum && row.hasChildren}
                    <button class="tag-title" type="button" aria-expanded={expanded.has(item.id)} aria-label={`${expanded.has(item.id) ? 'Collapse' : 'Expand'} ${item.name}`} onclick={() => toggleExpanded(item.id)}>
                      <span>
                        <strong>{item.name}</strong>
                        {#if appliedSearch && item.parent_path?.length}<small>{[...item.parent_path, item.name].join(' / ')}</small>{/if}
                      </span>
                      <Icon name="chevron" size=".95rem" />
                    </button>
                  {:else}
                    <span class="tag-title-static">
                      <strong>{item.name}</strong>
                      {#if !isAlbum && appliedSearch && item.parent_path?.length}<small>{[...item.parent_path, item.name].join(' / ')}</small>{/if}
                    </span>
                  {/if}
                </div>
              </td>
              <td>{item.asset_count}</td>
              <td class="actions">
                <div class="action-buttons">
                  <IconButton icon="edit" label={`Edit ${item.name}`} disabled={mutationBusy} onclick={() => edit(item)} size="compact" />
                  <IconButton icon="filter" label={`Filter assets by ${item.name}`} onclick={() => quickFilter(item.id)} size="compact" />
                  <IconButton icon="trash" label={`Delete ${item.name}`} tone="destructive" disabled={mutationBusy} onclick={() => removeOne(item)} size="compact" />
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <Pagination
      currentPage={collection.page}
      totalPages={collection.pages}
      totalItems={collection.total}
      pageSize={collection.pageSize}
      allowPageSizeChange={false}
      hideWhenSinglePage
      disabled={collection.refreshing || mutationBusy}
      label={`${title} pagination`}
      onpagechange={changePage}
    />
  {/if}
</section>

{#if dialogOpen}
  <Dialog
    title={`${editing ? 'Edit' : 'Create'} ${isAlbum ? 'album' : 'tag'}`}
    description={editing ? `Update this ${isAlbum ? 'album' : 'tag'} in Immich.` : `Set the ${isAlbum ? 'album' : 'tag'} data before creating it.`}
    size="small"
    initialFocus="first"
    closeOnBackdrop={!mutationBusy}
    closeOnEscape={!mutationBusy}
    onclose={closeForm}
  >
    <form id="relation-editor" class="dialog-form" autocomplete="off" onsubmit={(event) => { event.preventDefault(); void save(); }}>
      <label>
        Name
        <input autofocus autocomplete="off" data-1p-ignore data-bwignore="true" name="relation-name" bind:value={name} required maxlength="255" />
      </label>
      {#if isAlbum}
        <label>Description<textarea autocomplete="off" name="relation-description" bind:value={description} maxlength="2000"></textarea></label>
      {:else}
        <div class="color-field"><span>Color</span><ColorPicker value={color} onchange={(next) => (color = next)} /></div>
        <SelectField id="parent-tag" label="Parent tag" value={parentId} options={parentOptions} onchange={(next) => (parentId = next)} />
      {/if}
      {#if formError}<StatusNotice compact tone="error" message={formError} />{/if}
    </form>
    {#snippet footer()}
      <DialogFormActions
        formId="relation-editor"
        submitLabel={editing ? 'Save changes' : 'Create'}
        busyLabel={editing ? 'Saving…' : 'Creating…'}
        busy={mutationBusy}
        disabled={!name.trim()}
        oncancel={closeForm}
      />
    {/snippet}
  </Dialog>
{/if}

{#if deleteConfirmOpen}
  <ConfirmDialog
    title="Delete relation"
    message={pendingDeleteLabel}
    confirmLabel="Delete"
    icon="trash"
    destructive
    busy={mutationBusy}
    onconfirm={() => void confirmDelete()}
    onclose={() => {
      if (!mutationBusy) {
        deleteConfirmOpen = false;
        pendingDelete = [];
      }
    }}
  />
{/if}

<style>
  .relations { display: grid; gap: 1.4rem; }
  .intro { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; align-items: end; }
  .intro span { color: var(--color-accent-strong); font-size: .7rem; text-transform: uppercase; font-weight: 800; }
  h1 { margin: .3rem 0 0; font-size: clamp(2rem, 5vw, 3.6rem); letter-spacing: -.05em; }
  p { color: var(--color-ink-muted); line-height: 1.55; }
  .toolbar { display: flex; gap: .7rem; flex-wrap: wrap; align-items: center; }
  input, textarea { border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); padding: .65rem .75rem; font: inherit; background: var(--color-surface-raised); color: inherit; }
  .toolbar input { flex: 1; min-width: 14rem; }
  :global(.toolbar .icon-button-wrap button) { width: 2.75rem; height: 2.75rem; }
  .dialog-form { display: grid; gap: 1rem; }
  label { display: grid; gap: .3rem; color: var(--color-ink-muted); font-size: .8rem; font-weight: 700; }
  textarea { min-height: 5rem; }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; background: var(--color-surface-raised); }
  .selection-column { width: 3.5rem; }
  .count-column { width: 8rem; }
  .actions-column { width: 13rem; }
  th, td { padding: .85rem; border-bottom: 1px solid var(--color-border-subtle); text-align: left; vertical-align: middle; }
  th { color: var(--color-ink-muted); font-size: .75rem; text-transform: uppercase; }
  .selection-cell { text-align: center; }
  .actions-heading, td.actions { text-align: right; }
  .sort-heading { padding: 0; border: 0; color: inherit; background: transparent; cursor: pointer; font: inherit; font-size: inherit; font-weight: 800; text-transform: uppercase; }
  .sort-heading span { color: var(--color-accent-strong); }
  .styled-checkbox { width: 1.15rem; height: 1.15rem; margin: 0; accent-color: var(--color-accent-strong); vertical-align: middle; cursor: pointer; }
  .action-buttons { display: flex; justify-content: flex-end; gap: .4rem; }
  .tag-name { display: flex; min-width: 0; min-height: 2.75rem; gap: .45rem; align-items: center; padding-left: calc(var(--depth, 0) * 1.35rem); }
  .tag-title, .tag-title-static { display: flex; min-width: 0; flex: 1; gap: .55rem; align-items: center; text-align: left; }
  .tag-title { justify-content: space-between; padding: .3rem 0; border: 0; color: inherit; background: transparent; cursor: pointer; font: inherit; }
  .tag-title > span:first-child, .tag-title-static { display: flex; min-width: 0; gap: .35rem; align-items: baseline; }
  .tag-title > span:first-child strong, .tag-title-static strong { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  :global(.tag-title svg) { flex: 0 0 auto; transition: transform .16s ease; }
  :global(.tag-title[aria-expanded='true'] svg) { transform: rotate(180deg); }
  .tag-title:hover strong, .tag-title:focus-visible strong { color: var(--color-accent-strong); }
  .tag-name small { min-width: 0; overflow: hidden; color: var(--color-ink-muted); font-size: .68rem; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
  .flat-relations .tag-name { min-height: 0; gap: 0; padding-left: 0; }
  .flat-relations .tag-title-static { display: block; flex: none; }
  .color-field { display: grid; gap: .4rem; }
  .color-field > span { color: var(--color-ink-muted); font-size: .8rem; font-weight: 700; }

  @media (max-width: 46rem) {
    .intro { grid-template-columns: 1fr; }
    .actions-column { width: 10rem; }
  }
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import { createRelation, deleteRelations, getRelations, getTagOptions, updateRelation } from '../api/relationsApi';
  import type { ManagedRelation, RelationKind } from '../types/relations';
  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import Dialog from '../../../lib/components/ui/Dialog.svelte';
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import ColorPicker from './ColorPicker.svelte';
  import type { SelectOption } from '../../../lib/types/ui';
  import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import { branchParentIds, flattenTagTree } from '../state/tagTree';

  interface Props { kind: RelationKind; }
  let { kind }: Props = $props();
  let items = $state<ManagedRelation[]>([]);
  let selected = $state(new Set<string>());
  let page = $state(1);
  let pages = $state(0);
  let search = $state('');
  let name = $state('');
  let description = $state('');
  let color = $state('#6b7cff');
  let parentId = $state('');
  let editing = $state<string | null>(null);
  let error = $state<string | null>(null);
  let message = $state<string | null>(null);
  let busy = $state(false);
  let dialogOpen = $state(false);
  let deleteConfirmOpen = $state(false);
  let pendingDelete = $state<string[]>([]);
  let pendingDeleteLabel = $state('');
  let sort = $state<'name' | 'asset_count'>('name');
  let direction = $state<'asc' | 'desc'>('asc');
  let expanded = $state(new Set<string>());
  let tagOptions = $state<{ id: string; name: string }[]>([]);

  const title = $derived(kind === 'albums' ? 'Albums' : 'Tags');
  const isAlbum = $derived(kind === 'albums');
  const parentOptions = $derived<SelectOption[]>([
    { value: '', label: 'No parent tag' },
    ...tagOptions.filter((item) => item.id !== editing).map((item) => ({ value: item.id, label: item.name })),
  ]);
  const displayRows = $derived(isAlbum ? items.map((item) => ({ item, depth: 0, hasChildren: false })) : flattenTagTree(items, expanded, Boolean(search.trim())));

  async function load() {
    busy = true; error = null;
    try { const result = await getRelations(kind, page, search, sort, direction); items = result.items; if (!search.trim()) expanded = new Set([...expanded, ...(isAlbum ? [] : branchParentIds(result.items))]); pages = result.pages; if (pages && page > pages) { page = pages; await load(); } }
    catch (cause) { error = cause instanceof Error ? cause.message : 'Relations could not be loaded.'; }
    finally { busy = false; }
  }
  function resetForm() { editing = null; name = ''; description = ''; color = '#6b7cff'; parentId = ''; }
  function openCreate() { resetForm(); name = search.trim(); dialogOpen = true; }
  function changeSort(next: 'name' | 'asset_count') { if (sort === next) direction = direction === 'asc' ? 'desc' : 'asc'; else { sort = next; direction = 'asc'; } page = 1; void load(); }
  function togglePageSelection(checked: boolean) { selected = checked ? new Set(displayRows.map((row) => row.item.id)) : new Set(); }
  function toggleItemSelection(id: string, checked: boolean) { const next = new Set(selected); checked ? next.add(id) : next.delete(id); selected = next; }
  function sortLabel(column: 'name' | 'asset_count') { return sort === column ? direction === 'asc' ? ' (ascending)' : ' (descending)' : ''; }
  async function save() {
    if (!name.trim()) return;
    busy = true; error = null;
    try {
      const data = isAlbum ? { name: name.trim(), description } : { name: name.trim(), color, ...(parentId ? { parent_id: parentId } : {}) };
      if (editing) await updateRelation(kind, editing, data); else await createRelation(kind, data);
      message = `${isAlbum ? 'Album' : 'Tag'} ${editing ? 'updated' : 'created'}.`; dialogOpen = false; resetForm(); await load();
    } catch (cause) { error = cause instanceof Error ? cause.message : 'Relation could not be saved.'; }
    finally { busy = false; }
  }
  function edit(item: ManagedRelation) { editing = item.id; name = item.name; description = item.description ?? ''; color = item.color ?? '#6b7cff'; parentId = item.parent_id ?? ''; dialogOpen = true; }
  function removeSelected() {
    if (!selected.size || busy) return;
    pendingDelete = [...selected];
    pendingDeleteLabel = `Delete ${selected.size} relation${selected.size === 1 ? '' : 's'}? Media will not be deleted.`;
    deleteConfirmOpen = true;
  }
  async function confirmDelete() {
    if (!pendingDelete.length) return;
    busy = true; error = null;
    try { const result = await deleteRelations(kind, pendingDelete); selected = new Set(); deleteConfirmOpen = false; pendingDelete = []; message = result.failed.length ? `${result.completed.length} deleted; ${result.failed.length} failed.` : `${result.completed.length} deleted.`; await load(); }
    catch (cause) { error = cause instanceof Error ? cause.message : 'Relations could not be deleted.'; }
    finally { busy = false; }
  }
  async function removeOne(item: ManagedRelation) {
    selected = new Set([item.id]);
    pendingDelete = [item.id];
    pendingDeleteLabel = `Delete “${item.name}”? Media will not be deleted.`;
    deleteConfirmOpen = true;
  }
  function quickFilter(id: string) { window.location.href = `/assets?${isAlbum ? 'albumId' : 'tagId'}=${encodeURIComponent(id)}`; }
  function toggleExpanded(id: string) { const next = new Set(expanded); next.has(id) ? next.delete(id) : next.add(id); expanded = next; }
  onMount(async () => {
    if (!isAlbum) {
      try { tagOptions = await getTagOptions(); } catch { /* The management request reports the actionable error. */ }
    }
    await load();
  });
</script>

<section class="relations" class:flat-relations={isAlbum}>
  <header class="intro"><div><span>Immich relations</span><h1>{title}</h1></div><p>Manage metadata through the Immich API. Deleting a relation never deletes media.</p></header>
  <div class="toolbar"><input autocomplete="off" data-1p-ignore data-bwignore="true" aria-label={`Search ${title}`} placeholder={`Search ${title.toLowerCase()}`} bind:value={search} onkeydown={(event) => event.key === 'Enter' && (page = 1, load())} /><IconButton icon={isAlbum ? 'album-add' : 'tag-add'} label="Create" tone="accent" onclick={openCreate} /><IconButton icon="trash" label="Delete selected" tone="destructive" disabled={busy || selected.size === 0} onclick={removeSelected} /></div>
  {#if error}<p class="error" role="alert">{error}</p>{/if}{#if message}<p class="message" role="status">{message}</p>{/if}
  {#if busy && !items.length}<p>Loading…</p>{:else if !items.length}<p class="empty">No {title.toLowerCase()} found.</p>{:else}<div class="table-wrap"><table><colgroup><col class="selection-column" /><col /><col class="count-column" /><col class="actions-column" /></colgroup><thead><tr><th class="selection-cell"><div class="styled-checkbox"><Checkbox checked={displayRows.length > 0 && displayRows.every((row) => selected.has(row.item.id))} label={`Select all visible ${title.toLowerCase()}`} hiddenLabel onchange={togglePageSelection} /></div></th><th><button class="sort-heading" onclick={() => changeSort('name')} aria-label={`Sort by name${sortLabel('name')}`}>Name <span>{sort === 'name' ? direction === 'asc' ? '↑' : '↓' : '↕'}</span></button></th><th><button class="sort-heading" onclick={() => changeSort('asset_count')} aria-label={`Sort by asset count${sortLabel('asset_count')}`}>Assets <span>{sort === 'asset_count' ? direction === 'asc' ? '↑' : '↓' : '↕'}</span></button></th><th class="actions-heading">Actions</th></tr></thead><tbody>{#each displayRows as row (row.item.id)}{@const item = row.item}<tr><td class="selection-cell"><div class="styled-checkbox"><Checkbox checked={selected.has(item.id)} label={`Select ${item.name}`} hiddenLabel onchange={(checked) => toggleItemSelection(item.id, checked)} /></div></td><td><div class="tag-name" style={`--depth:${row.depth}`}>
        {#if !isAlbum && row.hasChildren}<button class="tag-title" type="button" aria-expanded={expanded.has(item.id)} aria-label={`${expanded.has(item.id) ? 'Collapse' : 'Expand'} ${item.name}`} onclick={() => toggleExpanded(item.id)}><span><strong>{item.name}</strong>{#if search.trim() && item.parent_path?.length}<small>{[...item.parent_path, item.name].join(' / ')}</small>{/if}</span><Icon name="chevron" size=".95rem" /></button>{:else}<span class="tag-title-static"><strong>{item.name}</strong>{#if !isAlbum && search.trim() && item.parent_path?.length}<small>{[...item.parent_path, item.name].join(' / ')}</small>{/if}</span>{/if}
      </div></td><td>{item.asset_count}</td><td class="actions"><div class="action-buttons"><IconButton icon="edit" label={`Edit ${item.name}`} onclick={() => edit(item)} size="compact" /><IconButton icon="filter" label={`Filter assets by ${item.name}`} onclick={() => quickFilter(item.id)} size="compact" /><IconButton icon="trash" label={`Delete ${item.name}`} tone="destructive" onclick={() => removeOne(item)} size="compact" /></div></td></tr>{/each}</tbody></table></div>{/if}
  {#if pages > 1}<nav class="pagination" aria-label={`${title} pagination`}><button onclick={() => { page -= 1; load(); }} disabled={page === 1}>Previous</button><span>Page {page} of {pages}</span><button onclick={() => { page += 1; load(); }} disabled={page === pages}>Next</button></nav>{/if}
</section>

  {#if dialogOpen}
  <Dialog
    title={`${editing ? 'Edit' : 'Create'} ${isAlbum ? 'album' : 'tag'}`}
    description={editing ? `Update this ${isAlbum ? 'album' : 'tag'} in Immich.` : `Set the ${isAlbum ? 'album' : 'tag'} data before creating it.`}
    size="small"
    closeOnBackdrop={!busy}
    closeOnEscape={!busy}
    onclose={() => { if (!busy) { dialogOpen = false; resetForm(); } }}
  >
    <form id="relation-editor" class="dialog-form" autocomplete="off" onsubmit={(event) => { event.preventDefault(); save(); }}>
      <label>Name<input autocomplete="off" data-1p-ignore data-bwignore="true" name="relation-name" bind:value={name} required maxlength="255" /></label>
      {#if isAlbum}
        <label>Description<textarea autocomplete="off" name="relation-description" bind:value={description} maxlength="2000"></textarea></label>
      {:else}
        <div class="color-field"><span>Color</span><ColorPicker value={color} onchange={(next) => (color = next)} /></div>
        <SelectField id="parent-tag" label="Parent tag" value={parentId} options={parentOptions} onchange={(next) => (parentId = next)} />
      {/if}
    </form>
    {#snippet footer()}
      <div class="dialog-actions"><button type="button" onclick={() => { dialogOpen = false; resetForm(); }} disabled={busy}>Cancel</button><button class="confirm" type="submit" form="relation-editor" disabled={busy || !name.trim()}>{busy ? 'Applying…' : editing ? 'Save changes' : 'Create'}</button></div>
    {/snippet}
  </Dialog>
{/if}

{#if deleteConfirmOpen}
  <ConfirmDialog title="Delete relation" message={pendingDeleteLabel} confirmLabel="Delete" icon="trash" destructive busy={busy} onconfirm={confirmDelete} onclose={() => { if (!busy) { deleteConfirmOpen = false; pendingDelete = []; } }} />
{/if}

<style>
  .relations { display: grid; gap: 1.4rem; } .intro { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; align-items: end; } .intro span { color: var(--color-accent-strong); font-size: .7rem; text-transform: uppercase; font-weight: 800; } h1 { margin: .3rem 0 0; font-size: clamp(2rem, 5vw, 3.6rem); letter-spacing: -.05em; } p { color: var(--color-ink-muted); line-height: 1.55; } .toolbar { display: flex; gap: .7rem; flex-wrap: wrap; align-items: center; } input, textarea { border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); padding: .65rem .75rem; font: inherit; background: var(--color-surface-raised); color: inherit; } .toolbar input { flex: 1; min-width: 14rem; } :global(.toolbar .icon-button-wrap button) { width: 2.75rem; height: 2.75rem; } .dialog-form { display: grid; gap: 1rem; } label { display: grid; gap: .3rem; color: var(--color-ink-muted); font-size: .8rem; font-weight: 700; } textarea { min-height: 5rem; } .table-wrap { overflow-x: auto; } table { width: 100%; border-collapse: collapse; background: var(--color-surface-raised); } .selection-column { width: 3.5rem; } .count-column { width: 8rem; } .actions-column { width: 13rem; } th, td { padding: .85rem; border-bottom: 1px solid var(--color-border-subtle); text-align: left; vertical-align: middle; } th { color: var(--color-ink-muted); font-size: .75rem; text-transform: uppercase; } .selection-cell { text-align: center; } .actions-heading, td.actions { text-align: right; } .sort-heading { padding: 0; border: 0; color: inherit; background: transparent; cursor: pointer; font: inherit; font-size: inherit; font-weight: 800; text-transform: uppercase; } .sort-heading span { color: var(--color-accent-strong); } .styled-checkbox { width: 1.15rem; height: 1.15rem; margin: 0; accent-color: var(--color-accent-strong); vertical-align: middle; cursor: pointer; } .action-buttons { display: flex; justify-content: flex-end; gap: .4rem; } .tag-name { display: flex; min-width: 0; min-height: 2.75rem; gap: .45rem; align-items: center; padding-left: calc(var(--depth, 0) * 1.35rem); } .tag-title, .tag-title-static { display: flex; min-width: 0; flex: 1; gap: .55rem; align-items: center; text-align: left; } .tag-title { justify-content: space-between; padding: .3rem 0; border: 0; color: inherit; background: transparent; cursor: pointer; font: inherit; } .tag-title > span:first-child, .tag-title-static { display: flex; min-width: 0; gap: .35rem; align-items: baseline; } .tag-title > span:first-child strong, .tag-title-static strong { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } :global(.tag-title svg) { flex: 0 0 auto; transition: transform .16s ease; } :global(.tag-title[aria-expanded='true'] svg) { transform: rotate(180deg); } .tag-title:hover strong, .tag-title:focus-visible strong { color: var(--color-accent-strong); } .tag-name small { min-width: 0; overflow: hidden; color: var(--color-ink-muted); font-size: .68rem; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; } .flat-relations .tag-name { min-height: 0; gap: 0; padding-left: 0; } .flat-relations .tag-title-static { display: block; flex: none; } .error { color: #a33d45; } .message { color: var(--color-accent-strong); } .pagination { display: flex; gap: .8rem; align-items: center; } .dialog-actions { display: flex; justify-content: flex-end; gap: .5rem; } .dialog-actions button { min-height: 2.4rem; padding: .5rem .8rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); cursor: pointer; font: inherit; font-size: .72rem; font-weight: 780; } .dialog-actions .confirm { border-color: var(--color-accent-strong); color: var(--color-accent-strong); } .dialog-actions button:disabled { cursor: wait; opacity: .5; } .color-field { display: grid; gap: .4rem; } .color-field > span { color: var(--color-ink-muted); font-size: .8rem; font-weight: 700; } @media (max-width: 46rem) { .intro { grid-template-columns: 1fr; } .actions-column { width: 10rem; } }
</style>

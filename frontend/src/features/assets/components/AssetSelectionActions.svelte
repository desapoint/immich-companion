<script lang="ts">
  import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import type { IconName, SelectOption } from '../../../lib/types/ui';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetActionPlan,
    AssetSelectionSummary,
    TagOption,
  } from '../types/assets';
  import AssetActionConfirmDialog from './AssetActionConfirmDialog.svelte';
  import AssetRelationActionDialog from './AssetRelationActionDialog.svelte';

  type RelationAction = Extract<
    AssetActionIntent,
    'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'
  >;

  interface Props {
    selectedCount: number;
    matchingTotal: number;
    currentPageCount: number;
    allMatching: boolean;
    summary: AssetSelectionSummary | null;
    albums: AlbumOption[];
    tags: TagOption[];
    plan: AssetActionPlan | null;
    busy?: boolean;
    error?: string | null;
    onselectpage: () => void;
    onselectall: () => void;
    oninvertpage: () => void;
    onclear: () => void;
    onplan: (action: AssetActionIntent, relationIds?: string[]) => void;
    onconfirm: () => void;
    oncancel: () => void;
  }

  let {
    selectedCount,
    matchingTotal,
    currentPageCount,
    allMatching,
    summary,
    albums,
    tags,
    plan,
    busy = false,
    error = null,
    onselectpage,
    onselectall,
    oninvertpage,
    onclear,
    onplan,
    onconfirm,
    oncancel,
  }: Props = $props();

  let relationAction = $state<RelationAction | null>(null);
  const albumOptions = $derived<SelectOption[]>(albums.map((album) => ({
    value: album.id,
    label: `${album.name} (${album.asset_count})`,
  })));
  const tagOptions = $derived<SelectOption[]>(tags.map((tag) => ({
    value: tag.id,
    label: `${tag.name} (${tag.asset_count})`,
  })));
  const relationOptions = $derived(
    relationAction?.endsWith('album') ? albumOptions : tagOptions,
  );

  function titleCase(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function stateIcon(action: 'archive' | 'unarchive' | 'favorite' | 'unfavorite'): IconName {
    return action;
  }

  function applyRelation(relationIds: string[]): void {
    if (!relationAction || relationIds.length === 0) return;
    onplan(relationAction, relationIds);
    relationAction = null;
  }
</script>

<section class="selection-actions" aria-label="Selected asset actions">
  <div class="selection-summary">
    <span>Selection</span>
    <strong>{selectedCount} selected</strong>
    {#if allMatching}<small>All matching results except unchecked assets</small>{/if}
  </div>

  <div class="toolbar-group" aria-label="Selection controls">
    <span class="group-label">Select</span>
    <div>
      <IconButton
        icon="select-page"
        label="Select current page"
        disabled={busy || currentPageCount === 0}
        onclick={onselectpage}
      />
      <IconButton
        icon="select-all"
        label={`Select all ${matchingTotal} matching assets`}
        disabled={busy || matchingTotal === 0}
        onclick={onselectall}
      />
      <IconButton
        icon="invert-selection"
        label="Invert current page selection"
        disabled={busy || currentPageCount === 0}
        onclick={oninvertpage}
      />
      <IconButton
        icon="clear-selection"
        label="Clear selection"
        disabled={busy}
        onclick={onclear}
      />
    </div>
  </div>

  <div class="toolbar-group" aria-label="Asset state actions">
    <span class="group-label">State</span>
    <div>
      {#if summary?.archive_action}
        <IconButton
          icon={stateIcon(summary.archive_action)}
          label={`${titleCase(summary.archive_action)} selected assets`}
          disabled={busy}
          tone="accent"
          onclick={() => onplan('archive_toggle')}
        />
      {/if}
      {#if summary?.favorite_action}
        <IconButton
          icon={stateIcon(summary.favorite_action)}
          label={`${titleCase(summary.favorite_action)} selected assets`}
          disabled={busy}
          tone="accent"
          onclick={() => onplan('favorite_toggle')}
        />
      {/if}
      {#if summary?.can_trash}
        <IconButton
          icon="trash"
          label="Trash applicable selected assets"
          disabled={busy}
          tone="destructive"
          onclick={() => onplan('trash')}
        />
      {/if}
      {#if summary?.can_restore}
        <IconButton
          icon="restore"
          label="Restore applicable selected assets"
          disabled={busy}
          onclick={() => onplan('restore')}
        />
      {/if}
      {#if !summary}<small>Resolving…</small>{/if}
    </div>
  </div>

  <div class="toolbar-group" aria-label="Album actions">
    <span class="group-label">Albums</span>
    <div>
      <IconButton
        icon="album-add"
        label="Add selected assets to albums"
        disabled={busy || albums.length === 0}
        onclick={() => (relationAction = 'add_album')}
      />
      <IconButton
        icon="album-remove"
        label="Remove selected assets from albums"
        disabled={busy || albums.length === 0}
        onclick={() => (relationAction = 'remove_album')}
      />
    </div>
  </div>

  <div class="toolbar-group" aria-label="Tag actions">
    <span class="group-label">Tags</span>
    <div>
      <IconButton
        icon="tag-add"
        label="Add tags to selected assets"
        disabled={busy || tags.length === 0}
        onclick={() => (relationAction = 'add_tag')}
      />
      <IconButton
        icon="tag-remove"
        label="Remove tags from selected assets"
        disabled={busy || tags.length === 0}
        onclick={() => (relationAction = 'remove_tag')}
      />
    </div>
  </div>

  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

{#if relationAction}
  <AssetRelationActionDialog
    action={relationAction}
    options={relationOptions}
    {selectedCount}
    {busy}
    onapply={applyRelation}
    onclose={() => (relationAction = null)}
  />
{/if}

{#if plan}
  <AssetActionConfirmDialog
    {plan}
    {albums}
    {tags}
    {busy}
    {onconfirm}
    onclose={oncancel}
  />
{/if}

<style>
  .selection-actions {
    position: sticky;
    z-index: 80;
    top: calc(var(--app-header-height, 4.8rem) + 0.5rem);
    display: flex;
    align-items: end;
    gap: 0.8rem;
    padding: 0.72rem 0.8rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-surface-raised) 94%, transparent);
    box-shadow: 0 0.55rem 1.6rem rgb(17 24 19 / 15%);
    backdrop-filter: blur(0.75rem);
  }

  .selection-summary {
    display: grid;
    min-width: 8.5rem;
    gap: 0.1rem;
  }

  .selection-summary > span,
  .group-label {
    color: var(--color-accent-strong);
    font-size: 0.6rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .selection-summary small,
  .toolbar-group small {
    color: var(--color-ink-muted);
    font-size: 0.62rem;
  }

  .toolbar-group {
    display: grid;
    gap: 0.28rem;
  }

  .toolbar-group > div {
    display: flex;
    gap: 0.32rem;
  }

  .error {
    min-width: 8rem;
    margin: 0;
    color: #b42318;
    font-size: 0.68rem;
  }

  @media (max-width: 62rem) {
    .selection-actions {
      align-items: center;
      flex-wrap: wrap;
    }
  }
</style>

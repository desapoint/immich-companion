<script lang="ts">
import IconButton from '../../../lib/components/ui/IconButton.svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetActionPlan,
    AssetSelectionSummary,
    TagOption,
  } from '../types/assets';
  import AssetActionConfirmDialog from './AssetActionConfirmDialog.svelte';
  import AssetActionControls from './AssetActionControls.svelte';

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
    onrelationconfirm: (
      action: Extract<AssetActionIntent, 'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'>,
      relationIds: string[],
    ) => void;
    onconfirm: () => void;
    oncancel: () => void;
    syncBusy?: boolean;
    syncError?: string | null;
    onsync?: () => void;
  }

  const LARGE_SYNC_THRESHOLD = 50;

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
    onrelationconfirm,
    onconfirm,
    oncancel,
    syncBusy = false,
    syncError = null,
    onsync = () => undefined,
  }: Props = $props();
  let syncConfirmOpen = $state(false);

  function requestSync(): void {
    if (selectedCount >= LARGE_SYNC_THRESHOLD) {
      syncConfirmOpen = true;
      return;
    }
    onsync();
  }
</script>

<section class="selection-actions" aria-label="Selected asset controls and actions">
  <div class="selection-summary">
    <strong>{selectedCount} selected</strong>
    {#if allMatching}<small>All matching results except unchecked assets</small>{/if}
    {#if error}<small class="error" role="alert">{error}</small>{/if}
    {#if syncError}<small class="error" role="alert">{syncError}</small>{/if}
  </div>

  <div class="right-controls">
    <div class="selection-controls" aria-label="Selection controls">
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

    <span class="control-separator" aria-hidden="true"></span>

    <IconButton
      icon="sync"
      label={`Sync ${selectedCount} selected ${selectedCount === 1 ? 'asset' : 'assets'}`}
      disabled={busy || syncBusy || selectedCount === 0}
      onclick={requestSync}
    />

    <AssetActionControls
      {summary}
      {albums}
      {tags}
      targetCount={selectedCount}
      targetLabel={selectedCount === 1 ? 'selected asset' : 'selected assets'}
      {busy}
      {onplan}
      {onrelationconfirm}
    />
  </div>
</section>

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

{#if syncConfirmOpen}
  <ConfirmDialog
    title="Sync selected assets?"
    message={`Syncing ${selectedCount} assets may take a while.`}
    confirmLabel="Sync assets"
    icon="sync"
    busy={syncBusy}
    onconfirm={() => {
      syncConfirmOpen = false;
      onsync();
    }}
    onclose={() => (syncConfirmOpen = false)}
  >
    {#snippet detail()}
      <p>All selected metadata, state, albums, and tags will be refreshed from Immich.</p>
    {/snippet}
  </ConfirmDialog>
{/if}

<style>
  .selection-actions {
    position: sticky;
    z-index: 80;
    top: calc(var(--app-header-height, 4.8rem) + 0.5rem);
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 1.25rem;
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
    gap: 0.12rem;
  }

  .selection-summary small {
    color: var(--color-ink-muted);
    font-size: 0.62rem;
  }

  .selection-summary .error { color: #b42318; }

  .right-controls {
    display: flex;
    min-width: 0;
    margin-left: auto;
    align-items: center;
    justify-content: flex-end;
    gap: 0.85rem;
  }

  .selection-controls {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.32rem;
  }

  .control-separator {
    width: 1px;
    height: 2.35rem;
    flex: 0 0 auto;
    background: var(--color-border-strong);
  }

  @media (max-width: 58rem) {
    .selection-actions {
      align-items: stretch;
      flex-direction: column;
    }

    .right-controls {
      width: 100%;
      margin-left: 0;
    }

    .selection-controls {
      margin-left: auto;
    }
  }

  @media (max-width: 38rem) {
    .right-controls {
      flex-wrap: wrap;
    }
  }
</style>

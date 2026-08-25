<script lang="ts">
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetActionPlan,
    AssetSelectionSummary,
    TagOption,
  } from '../types/assets';
  import AssetActionReview from './AssetActionReview.svelte';

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
    message?: string | null;
    error?: string | null;
    onselectpage: () => void;
    onselectall: () => void;
    oninvertpage: () => void;
    onclear: () => void;
    onplan: (action: AssetActionIntent, relationId?: string | null) => void;
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
    message = null,
    error = null,
    onselectpage,
    onselectall,
    oninvertpage,
    onclear,
    onplan,
    onconfirm,
    oncancel,
  }: Props = $props();

  let albumId = $state('');
  let tagId = $state('');
  const albumOptions = $derived(albums.map((album) => ({
    value: album.id,
    label: `${album.name} (${album.asset_count})`,
  })));
  const tagOptions = $derived(tags.map((tag) => ({
    value: tag.id,
    label: `${tag.name} (${tag.asset_count})`,
  })));
  const relationLabel = $derived(
    plan?.operation === 'remove_album'
      ? albums.find((album) => album.id === plan.relation_id)?.name ?? null
      : plan?.operation === 'remove_tag'
        ? tags.find((tag) => tag.id === plan.relation_id)?.name ?? null
        : null,
  );

  function titleCase(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }
</script>

<section class="selection-actions" aria-label="Selected asset actions">
  <div class="selection-tools">
    <div>
      <span>Selection</span>
      <strong>{selectedCount} selected</strong>
      {#if allMatching}<small>All matching results, excluding unchecked assets</small>{/if}
    </div>
    <div class="button-row">
      <button type="button" onclick={onselectpage} disabled={busy || currentPageCount === 0}>
        Select page
      </button>
      <button type="button" onclick={onselectall} disabled={busy || matchingTotal === 0}>
        Select all {matchingTotal}
      </button>
      <button type="button" onclick={oninvertpage} disabled={busy || currentPageCount === 0}>
        Invert page
      </button>
      <button type="button" onclick={onclear} disabled={busy || selectedCount === 0}>
        Clear
      </button>
    </div>
  </div>

  {#if selectedCount > 0}
    <div class="action-tools">
      <div class="state-actions">
        {#if summary?.archive_action}
          <button type="button" onclick={() => onplan('archive_toggle')} disabled={busy}>
            {titleCase(summary.archive_action)}
          </button>
        {/if}
        {#if summary?.favorite_action}
          <button type="button" onclick={() => onplan('favorite_toggle')} disabled={busy}>
            {titleCase(summary.favorite_action)}
          </button>
        {/if}
        {#if summary?.can_trash}
          <button class="destructive" type="button" onclick={() => onplan('trash')} disabled={busy}>
            Trash
          </button>
        {/if}
        {#if summary?.can_restore}
          <button type="button" onclick={() => onplan('restore')} disabled={busy}>
            Restore
          </button>
        {/if}
        {#if !summary}<small>Resolving selected asset state…</small>{/if}
      </div>

      <div class="relation-actions">
        <div>
          <SelectField
            id="remove-selection-album"
            label="Remove from album"
            value={albumId}
            options={albumOptions}
            disabled={busy}
            compact
            onchange={(value) => (albumId = value)}
          />
          <button
            type="button"
            onclick={() => onplan('remove_album', albumId)}
            disabled={busy || !albumId}
          >Remove album</button>
        </div>
        <div>
          <SelectField
            id="remove-selection-tag"
            label="Remove tag"
            value={tagId}
            options={tagOptions}
            disabled={busy}
            compact
            onchange={(value) => (tagId = value)}
          />
          <button
            type="button"
            onclick={() => onplan('remove_tag', tagId)}
            disabled={busy || !tagId}
          >Remove tag</button>
        </div>
      </div>
    </div>
  {/if}

  {#if plan}
    <AssetActionReview
      {plan}
      {relationLabel}
      {busy}
      {onconfirm}
      oncancel={oncancel}
    />
  {/if}

  {#if message}<p class="message" role="status">{message}</p>{/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .selection-actions {
    display: grid;
    gap: 0.75rem;
    padding: 0.8rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
  }

  .selection-tools,
  .action-tools,
  .button-row,
  .state-actions,
  .relation-actions,
  .relation-actions > div {
    display: flex;
    align-items: end;
    gap: 0.55rem;
  }

  .selection-tools,
  .action-tools {
    justify-content: space-between;
  }

  .selection-tools > div:first-child {
    display: grid;
    gap: 0.15rem;
  }

  span,
  small {
    color: var(--color-ink-muted);
    font-size: 0.66rem;
  }

  span {
    color: var(--color-accent-strong);
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .button-row,
  .state-actions,
  .relation-actions {
    flex-wrap: wrap;
  }

  .relation-actions > div {
    min-width: min(18rem, 100%);
  }

  .relation-actions :global(.select-field) {
    min-width: 11rem;
    flex: 1;
  }

  button {
    min-height: 2.3rem;
    padding: 0.48rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    font-size: 0.7rem;
    font-weight: 760;
  }

  button:hover:not(:disabled) {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  button.destructive {
    border-color: color-mix(in srgb, #b45309 55%, var(--color-border-strong));
    color: #b45309;
  }

  button:disabled {
    cursor: default;
    opacity: 0.48;
  }

  .message,
  .error {
    margin: 0;
    font-size: 0.72rem;
  }

  .message {
    color: var(--color-accent-strong);
  }

  .error {
    color: #b42318;
  }

  @media (max-width: 70rem) {
    .selection-tools,
    .action-tools {
      align-items: stretch;
      flex-direction: column;
    }
  }

  @media (max-width: 42rem) {
    .button-row,
    .state-actions,
    .relation-actions,
    .relation-actions > div {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>

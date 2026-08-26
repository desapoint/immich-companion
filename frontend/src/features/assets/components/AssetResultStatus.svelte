<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';

  interface Props {
    total: number;
    shown: number;
    selected: number;
    syncing: boolean;
    syncMessage: string | null;
    onsync: () => void;
    onfullsync: () => void;
  }

  let {
    total,
    shown,
    selected,
    syncing,
    syncMessage,
    onsync,
    onfullsync,
  }: Props = $props();
  let fullSyncConfirmation = $state(false);
</script>

<div class="result-status">
  <div>
    <span>Search results</span>
    <strong>{total} matching assets</strong>
    <small>{shown} on this page · {selected} selected</small>
  </div>
  <div class="sync-area">
    {#if syncMessage}<small role="status">{syncMessage}</small>{/if}
    <button type="button" onclick={onsync} disabled={syncing}>
      {syncing ? 'Syncing Immich…' : 'Incremental sync'}
    </button>
    <button
      class="full-sync"
      type="button"
      onclick={() => (fullSyncConfirmation = true)}
    >Full sync</button>
  </div>
</div>

{#if fullSyncConfirmation}
  <ConfirmDialog
    title="Force a global synchronization?"
    message="This checks every album, tag, image, stack, and membership before safely removing anything absent. It runs in bounded batches and cannot overlap another sync."
    confirmLabel="Start full sync"
    icon="info"
    onconfirm={() => {
      fullSyncConfirmation = false;
      onfullsync();
    }}
    onclose={() => (fullSyncConfirmation = false)}
  />
{/if}

<style>
  .result-status {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 1rem;
  }

  .result-status > div:first-child {
    display: grid;
    gap: 0.18rem;
  }

  span {
    color: var(--color-accent-strong);
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  strong {
    font-size: 1.1rem;
  }

  small {
    color: var(--color-ink-muted);
    font-size: 0.7rem;
  }

  .sync-area {
    display: flex;
    align-items: end;
    gap: 0.65rem;
  }

  button {
    min-height: 2.45rem;
    padding: 0.55rem 0.8rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-accent-strong);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.74rem;
    font-weight: 780;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  .full-sync { color: var(--color-ink-muted); }

  @media (max-width: 42rem) {
    .result-status,
    .sync-area {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>

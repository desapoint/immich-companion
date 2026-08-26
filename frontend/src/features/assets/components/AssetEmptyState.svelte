<script lang="ts">
  interface Props {
    syncing: boolean;
    showSync?: boolean;
    onsync: () => void;
  }

  let { syncing, showSync = true, onsync }: Props = $props();
</script>

<div class="empty-state">
  <span aria-hidden="true">▧</span>
  <strong>No synchronized assets match</strong>
  {#if showSync}
    <p>Sync Immich to refresh the companion index, or clear filters to widen this search.</p>
    <button type="button" onclick={onsync} disabled={syncing}>
      {syncing ? 'Syncing Immich…' : 'Sync Immich now'}
    </button>
  {:else}
    <p>Try changing the search or clearing the filters.</p>
  {/if}
</div>

<style>
  .empty-state {
    display: grid;
    min-height: 14rem;
    place-items: center;
    align-content: center;
    gap: 0.45rem;
    padding: 2rem;
    border: 1px dashed var(--color-border-strong);
    border-radius: var(--radius-md);
    text-align: center;
    background: var(--color-surface-raised);
  }

  .empty-state > span {
    color: var(--color-accent-strong);
    font-size: 2rem;
  }

  strong {
    font-size: 0.95rem;
  }

  p {
    max-width: 34rem;
    margin: 0;
    color: var(--color-ink-muted);
    font-size: 0.75rem;
  }

  button {
    min-height: 2.45rem;
    margin-top: 0.45rem;
    padding: 0.55rem 0.8rem;
    border: 1px solid var(--color-accent-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
    cursor: pointer;
    font: inherit;
    font-size: 0.74rem;
    font-weight: 780;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.58;
  }
</style>

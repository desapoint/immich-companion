<script lang="ts">
  import LoadingSpinner from '../../../lib/components/ui/LoadingSpinner.svelte';
</script>

<div class="loading-state" role="status" aria-live="polite">
  <LoadingSpinner />
  <div>
    <strong>Loading asset index</strong>
    <p>Searching synchronized Immich metadata…</p>
  </div>
</div>

<style>
  .loading-state {
    display: flex;
    min-height: 12rem;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 2rem;
    border: 1px dashed var(--color-border-strong);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
  }

  strong,
  p {
    display: block;
    margin: 0;
  }

  strong {
    font-size: 0.86rem;
  }

  p {
    margin-top: 0.2rem;
    color: var(--color-ink-muted);
    font-size: 0.72rem;
  }
</style>

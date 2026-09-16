<script lang="ts">
  import LoadingSpinner from './LoadingSpinner.svelte';

  let { label }: { label: string } = $props();
</script>

<div class="loading-overlay" role="status" aria-live="polite">
  <div class="loading-overlay-content">
    <LoadingSpinner size="2rem" />
    <strong>{label}</strong>
  </div>
</div>

<style>
  .loading-overlay {
    position: fixed;
    z-index: 90;
    inset: var(--app-header-height, 0px) 0 0;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--color-canvas) 72%, transparent);
    backdrop-filter: blur(2px);
  }

  .loading-overlay-content {
    display: flex;
    align-items: center;
    gap: .8rem;
    padding: 1rem 1.25rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
    font-size: .85rem;
  }
</style>

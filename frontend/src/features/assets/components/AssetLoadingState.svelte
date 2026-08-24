<script lang="ts">
</script>

<div class="loading-state" role="status" aria-live="polite">
  <span class="spinner" aria-hidden="true"></span>
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

  .spinner {
    width: 1.4rem;
    height: 1.4rem;
    border: 0.16rem solid var(--color-border-strong);
    border-top-color: var(--color-accent-strong);
    border-radius: 50%;
    animation: spin 800ms linear infinite;
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

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner { animation: none; }
  }
</style>

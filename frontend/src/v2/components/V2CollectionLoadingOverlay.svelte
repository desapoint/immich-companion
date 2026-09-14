<script lang="ts">
  let { label }: { label: string } = $props();
</script>

<div class="collection-loading" role="status" aria-live="polite">
  <div class="loading-message">
    <span class="spinner" aria-hidden="true"></span>
    <strong>{label}</strong>
  </div>
</div>

<style>
  .collection-loading {
    position: fixed;
    z-index: 70;
    inset: var(--v2-topbar-height) 0 0 var(--v2-sidebar-width);
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--v2-bg) 70%, transparent);
    backdrop-filter: blur(2px);
  }

  .loading-message {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    border: 1px solid var(--v2-line);
    border-radius: var(--v2-radius);
    color: var(--v2-text);
    background: var(--v2-surface-2);
    box-shadow: 0 12px 32px rgb(0 0 0 / 35%);
    font-size: 13px;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 3px solid var(--v2-line);
    border-top-color: var(--v2-accent);
    border-radius: 50%;
    animation: spin 800ms linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner { animation: none; }
  }
</style>

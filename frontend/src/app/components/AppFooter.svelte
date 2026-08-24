<script lang="ts">
  const safetyMessage = 'Immich remains the source of truth. Companion actions are disabled by default.';
</script>

<footer class="app-footer">
  <p>{safetyMessage}</p>
</footer>

<style>
  .app-footer {
    width: min(72rem, calc(100% - 2rem));
    margin: 0 auto;
    padding: 1.25rem 0 2rem;
    border-top: 1px solid var(--color-border-subtle);
    color: var(--color-ink-muted);
    font-size: 0.78rem;
  }

  p {
    margin: 0;
  }
</style>

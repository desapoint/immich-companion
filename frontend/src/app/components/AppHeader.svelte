<script lang="ts">
  const homePath = '/';
</script>

<header class="app-header">
  <a class="brand" href={homePath} aria-label="Immich Companion home">
    <span class="brand-mark" aria-hidden="true">IC</span>
    <span>
      <strong>Immich Companion</strong>
      <small>Operational workspace</small>
    </span>
  </a>
  <a class="api-link" href="/api/docs">API documentation</a>
</header>

<style>
  .app-header {
    width: min(72rem, calc(100% - 2rem));
    margin: 0 auto;
    padding: 1rem 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    border-bottom: 1px solid var(--color-border-subtle);
  }

  .brand {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    color: var(--color-ink-strong);
    text-decoration: none;
  }

  .brand-mark {
    display: grid;
    width: 2.5rem;
    height: 2.5rem;
    place-items: center;
    border: 1px solid var(--color-border-strong);
    border-radius: 0.75rem;
    color: var(--color-accent-strong);
    background: var(--color-surface-raised);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.08em;
  }

  strong,
  small {
    display: block;
  }

  strong {
    font-size: 0.95rem;
    letter-spacing: -0.01em;
  }

  small {
    margin-top: 0.1rem;
    color: var(--color-ink-muted);
    font-size: 0.72rem;
  }

  .api-link {
    color: var(--color-ink-muted);
    font-size: 0.82rem;
    font-weight: 700;
    text-underline-offset: 0.25rem;
  }

  .api-link:hover {
    color: var(--color-accent-strong);
  }

  @media (max-width: 34rem) {
    .app-header {
      align-items: flex-start;
    }

    .api-link {
      padding-top: 0.35rem;
    }

    small {
      display: none;
    }
  }
</style>

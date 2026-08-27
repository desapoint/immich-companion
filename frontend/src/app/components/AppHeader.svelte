<script lang="ts">
  const homePath = '/';

  interface Props {
    activePath?: string;
  }

  let { activePath = '/' }: Props = $props();
</script>

<header class="app-header">
  <div class="header-inner">
    <a class="brand" href={homePath} aria-label="Immich Companion home">
      <span class="brand-mark" aria-hidden="true">IC</span>
      <span>
        <strong>Immich Companion</strong>
        <small>Operational workspace</small>
      </span>
    </a>
    <nav aria-label="Primary navigation">
      <a class:active={activePath === '/'} href="/">Status</a>
      <a class:active={activePath.startsWith('/assets')} href="/assets">Assets</a>
      <a class:active={activePath === '/albums'} href="/albums">Albums</a>
      <a class:active={activePath === '/tags'} href="/tags">Tags</a>
      <a class:active={activePath === '/settings'} href="/settings">Settings</a>
      <a href="/api/docs">API docs</a>
    </nav>
  </div>
</header>

<style>
  .app-header {
    position: sticky;
    z-index: 90;
    top: 0;
    width: 100%;
    min-height: var(--app-header-height, 4.8rem);
    padding: 0 1rem;
    border-bottom: 1px solid var(--color-border-subtle);
    background: color-mix(in srgb, var(--color-canvas) 94%, transparent);
    backdrop-filter: blur(0.8rem);
  }

  .header-inner {
    width: min(96rem, 100%);
    min-height: inherit;
    margin: 0 auto;
    padding: 1rem 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
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

  nav {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  nav a {
    padding: 0.5rem 0.65rem;
    border-radius: var(--radius-sm);
    color: var(--color-ink-muted);
    text-decoration: none;
    font-size: 0.82rem;
    font-weight: 700;
  }

  nav a:hover,
  nav a.active {
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  @media (max-width: 34rem) {
    .header-inner {
      align-items: flex-start;
    }

    nav {
      overflow-x: auto;
    }

    small {
      display: none;
    }
  }
</style>

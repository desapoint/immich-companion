<script lang="ts">
  import type { Snippet } from 'svelte';

  import AppFooter from './AppFooter.svelte';
  import AppHeader from './AppHeader.svelte';

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<a class="skip-link" href="#main-content">Skip to companion status</a>
<div class="app-shell">
  <AppHeader />
  <main id="main-content" class="app-main">
    {@render children()}
  </main>
  <AppFooter />
</div>

<style>
  .skip-link {
    position: fixed;
    z-index: 100;
    top: 0.75rem;
    left: 0.75rem;
    padding: 0.7rem 1rem;
    border-radius: var(--radius-sm);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
    transform: translateY(-160%);
    transition: transform 120ms ease;
  }

  .skip-link:focus {
    transform: translateY(0);
  }

  .app-shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto 1fr auto;
  }

  .app-main {
    width: min(72rem, calc(100% - 2rem));
    margin: 0 auto;
    padding: clamp(2.5rem, 6vw, 5.5rem) 0;
  }
</style>

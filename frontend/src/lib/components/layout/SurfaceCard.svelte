<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    eyebrow?: string;
    children: Snippet;
  }

  const titleId = $props.id();
  let { title, eyebrow, children }: Props = $props();
</script>

<article class="surface-card" aria-labelledby={titleId}>
  <header>
    {#if eyebrow}
      <p>{eyebrow}</p>
    {/if}
    <h2 id={titleId}>{title}</h2>
  </header>
  <div class="content">
    {@render children()}
  </div>
</article>

<style>
  .surface-card {
    min-width: 0;
    padding: clamp(1.1rem, 3vw, 1.45rem);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
  }

  header {
    margin-bottom: 1rem;
  }

  p {
    margin: 0 0 0.35rem;
    color: var(--color-accent-strong);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0;
    color: var(--color-ink-strong);
    font-size: 1rem;
    letter-spacing: -0.01em;
  }

  .content {
    color: var(--color-ink-muted);
  }
</style>

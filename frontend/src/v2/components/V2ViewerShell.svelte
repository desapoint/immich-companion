<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    open = false,
    title = 'Viewer',
    kind = 'viewer',
    onclose,
    header,
    children,
    footer,
  }: {
    open?: boolean;
    title?: string;
    kind?: 'viewer' | 'compare';
    onclose: () => void;
    header?: Snippet;
    children?: Snippet;
    footer?: Snippet;
  } = $props();

  const rootClass = $derived(kind === 'compare' ? 'v2-compare-viewer' : 'v2-viewer');
  const headerClass = $derived(kind === 'compare' ? 'v2-compare-top' : 'v2-viewer-top');
  const footerClass = $derived(kind === 'compare' ? 'v2-compare-actions' : 'v2-viewer-bottom');

  $effect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  });
</script>

<svelte:window onkeydown={(event) => { if (event.key === 'Escape' && open) onclose(); }} />
<svelte:body class:v2-overlay-open={open} />

{#if open}
  <div class={rootClass} role="dialog" aria-modal="true" aria-label={title}>
    {#if header}
      <div class={headerClass}>{@render header()}</div>
    {/if}
    {#if children}{@render children()}{/if}
    {#if footer}
      <div class={footerClass}>{@render footer()}</div>
    {/if}
  </div>
{/if}

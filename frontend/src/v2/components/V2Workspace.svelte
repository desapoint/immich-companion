<script lang="ts">
  let {
    context,
    children,
    inspector,
  }: {
    context?: import('svelte').Snippet;
    children: import('svelte').Snippet;
    inspector?: import('svelte').Snippet;
  } = $props();

  const layout = $derived(
    context && inspector
      ? 'three-column'
      : context
        ? 'context-only'
        : inspector
          ? 'inspector-only'
          : 'content-only',
  );
</script>

<section class="v2-workspace" data-layout={layout}>
  {#if context}<aside class="v2-context">{@render context()}</aside>{/if}
  <main class="v2-content">{@render children()}</main>
  {#if inspector}<aside class="v2-inspector">{@render inspector()}</aside>{/if}
</section>

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

  const layoutClass = $derived(
    context && inspector
      ? 'v2-workspace'
      : context
        ? 'v2-workspace v2-workspace-context-only'
        : inspector
          ? 'v2-workspace v2-workspace-inspector-only'
          : 'v2-workspace v2-workspace-content-only',
  );
</script>

<section class={layoutClass}>
  {#if context}<aside class="v2-context">{@render context()}</aside>{/if}
  <main class="v2-content">{@render children()}</main>
  {#if inspector}<aside class="v2-inspector">{@render inspector()}</aside>{/if}
</section>

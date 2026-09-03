<script lang="ts">
  let {
    title,
    description = '',
    eyebrow = 'Page identity',
    headerActions,
    context,
    children,
    content,
    inspector,
  }: {
    title: string;
    description?: string;
    eyebrow?: string;
    headerActions?: import('svelte').Snippet;
    context?: import('svelte').Snippet;
    children?: import('svelte').Snippet;
    content?: import('svelte').Snippet;
    inspector?: import('svelte').Snippet;
  } = $props();

  const workspaceClass = $derived(
    context && inspector
      ? 'v2-workspace'
      : context
        ? 'v2-workspace v2-workspace-context-only'
        : inspector
          ? 'v2-workspace v2-workspace-inspector-only'
          : 'v2-workspace v2-workspace-content-only',
  );
</script>

<div class="v2-page-host">
  <section class="v2-page-head">
    <div class="v2-head-row">
      <div>
        {#if eyebrow}<span class="v2-zone">{eyebrow}</span>{/if}
        <h1 class="v2-page-title">{title}</h1>
        {#if description}<p class="v2-page-description">{description}</p>{/if}
      </div>
      {#if headerActions}{@render headerActions()}{/if}
    </div>
  </section>

  <section class={workspaceClass}>
    {#if context}<aside class="v2-context">{@render context()}</aside>{/if}
    <main class="v2-content">
      {#if children}{@render children()}{:else if content}{@render content()}{/if}
    </main>
    {#if inspector}<aside class="v2-inspector">{@render inspector()}</aside>{/if}
  </section>
</div>

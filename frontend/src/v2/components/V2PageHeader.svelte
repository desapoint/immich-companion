<script lang="ts">
  let {
    title,
    description = '',
    eyebrow = 'Page identity',
    actions,
  }: {
    title: string;
    description?: string;
    eyebrow?: string;
    actions?: import('svelte').Snippet;
  } = $props();
</script>

<header class="v2-page-head">
  <div class="v2-head-row">
    <div class="v2-page-heading">
      {#if eyebrow}<span class="v2-zone">{eyebrow}</span>{/if}
      <h1 class="v2-page-title">{title}</h1>
      {#if description}<p class="v2-page-description">{description}</p>{/if}
    </div>
    {#if actions}<div class="v2-page-actions">{@render actions()}</div>{/if}
  </div>
</header>

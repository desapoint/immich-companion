<script lang="ts">
  import V2ZoneLabel from './V2ZoneLabel.svelte';

  let {
    title,
    description = '',
    eyebrow = '',
    actions,
    tabs,
  }: {
    title: string;
    description?: string;
    eyebrow?: string;
    actions?: import('svelte').Snippet;
    tabs?: import('svelte').Snippet;
  } = $props();
</script>

<header class="v2-page-head">
  <div class="v2-head-row">
    <div class="v2-page-heading">
      {#if eyebrow}<V2ZoneLabel text={eyebrow} />{/if}
      <h1 class="v2-page-title">{title}</h1>
      {#if description}<p class="v2-page-description">{description}</p>{/if}
    </div>
    {#if actions}<div class="v2-page-actions">{@render actions()}</div>{/if}
  </div>
  {#if tabs}<div class="v2-page-tabs">{@render tabs()}</div>{/if}
</header>

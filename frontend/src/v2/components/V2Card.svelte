<script lang="ts">
  let {
    title,
    actions,
    children,
    class: className = '',
  }: {
    title?: string;
    actions?: import('svelte').Snippet;
    children?: import('svelte').Snippet;
    class?: string;
  } = $props();
</script>

<div class={`v2-card ${className}`.trim()}>
  {#if title || actions}
    <div class="v2-card-header">
      {#if title}<h3 class="v2-card-heading">{title}</h3>{/if}
      {#if actions}{@render actions()}{/if}
    </div>
  {/if}
  {#if children}{@render children()}{/if}
</div>

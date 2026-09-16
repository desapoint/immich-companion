<script lang="ts">
  let {
    title = '',
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

<section class={`v2-section ${className}`.trim()}>
  {#if title || actions}
    <div class="v2-section-header">
      {#if title}<h3 class="v2-section-heading">{title}</h3>{/if}
      {#if actions}{@render actions()}{/if}
    </div>
  {/if}
  {#if children}{@render children()}{/if}
</section>

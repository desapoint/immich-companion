<script lang="ts">
  import V2ZoneLabel from './V2ZoneLabel.svelte';

  let {
    label,
    children,
    actions,
    sticky = true,
    class: className = '',
  }: {
    label?: string;
    children?: import('svelte').Snippet;
    actions?: import('svelte').Snippet;
    sticky?: boolean;
    class?: string;
  } = $props();
</script>

<div class={`v2-toolbar ${className}`.trim()} data-sticky={sticky || undefined}>
  <div class="v2-toolbar-group">
    {#if label}<V2ZoneLabel text={label} />{/if}
    {#if children}{@render children()}{/if}
  </div>
  {#if actions}<div class="v2-toolbar-group" data-align="end">{@render actions()}</div>{/if}
</div>

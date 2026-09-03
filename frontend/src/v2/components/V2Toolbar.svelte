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

<div class={`v2-toolbar${sticky ? ' v2-toolbar-sticky' : ''} ${className}`.trim()}>
  <div class="v2-toolbar-group">
    {#if label}<V2ZoneLabel text={label} />{/if}
    {#if children}{@render children()}{/if}
  </div>
  {#if actions}<div class="v2-toolbar-group v2-toolbar-actions">{@render actions()}</div>{/if}
</div>

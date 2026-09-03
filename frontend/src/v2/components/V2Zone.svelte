<script lang="ts">
  import V2Stack from './V2Stack.svelte';
  import V2ZoneLabel from './V2ZoneLabel.svelte';

  let {
    label,
    gap = 'md',
    children,
    class: className = '',
  }: {
    label?: string;
    gap?: 'xs' | 'sm' | 'md' | 'lg';
    children: import('svelte').Snippet;
    class?: string;
  } = $props();
</script>

<div class={`v2-zone-container ${className}`.trim()}>
  <V2Stack {gap}>
    {#if label}<V2ZoneLabel text={label} />{/if}
    {@render children()}
  </V2Stack>
</div>

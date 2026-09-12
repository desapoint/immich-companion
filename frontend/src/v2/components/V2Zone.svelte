<script lang="ts">
  import V2ZoneLabel from './V2ZoneLabel.svelte';

  let {
    label,
    children,
    class: className = '',
  }: {
    label?: string;
    children: import('svelte').Snippet;
    class?: string;
  } = $props();
</script>

<div class={`v2-zone-container ${className}`.trim()}>
  {#if label}
    <div class="v2-zone-label-slot"><V2ZoneLabel text={label} /></div>
  {/if}
  <div class="v2-zone-body">{@render children()}</div>
</div>

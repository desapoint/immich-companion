<script lang="ts">
  let { columns = 4, children, element = $bindable<HTMLElement | null>(null) }: { columns?: number; children: import('svelte').Snippet; element?: HTMLElement | null } = $props();
</script>

<div class="v2-asset-grid" data-fixed-columns="true" style={`--v2-asset-columns:${columns}`} bind:this={element}>
  {@render children()}
</div>

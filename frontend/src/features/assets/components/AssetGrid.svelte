<script lang="ts">
  let { columns = 4, children, element = $bindable<HTMLElement | null>(null) }: { columns?: number; children: import('svelte').Snippet; element?: HTMLElement | null } = $props();
</script>

<div class="v2-asset-grid" data-fixed-columns="true" style={`--v2-asset-columns:${columns};--v2-mobile-asset-columns:${Math.min(columns, 3)}`} bind:this={element}>
  {@render children()}
</div>

<style>
	@media (max-width: 380px) {
		.v2-asset-grid[data-fixed-columns='true'] {
			grid-template-columns: repeat(var(--v2-mobile-asset-columns), minmax(0, 1fr));
		}
	}
</style>

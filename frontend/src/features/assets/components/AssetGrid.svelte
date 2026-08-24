<script lang="ts">
  import type { AssetSummary } from '../types/assets';
  import AssetCard from './AssetCard.svelte';

  interface Props {
    assets: AssetSummary[];
    selectedIds: Set<string>;
    onopen: (index: number) => void;
    ontoggle: (assetId: string) => void;
  }

  let { assets, selectedIds, onopen, ontoggle }: Props = $props();
</script>

<div class="asset-grid" aria-label="Asset search results">
  {#each assets as asset, index (asset.id)}
    <AssetCard
      {asset}
      selected={selectedIds.has(asset.id)}
      onopen={() => onopen(index)}
      ontoggle={() => ontoggle(asset.id)}
    />
  {/each}
</div>

<style>
  .asset-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 17.5rem), 1fr));
    gap: 0.9rem;
    align-items: start;
  }
</style>

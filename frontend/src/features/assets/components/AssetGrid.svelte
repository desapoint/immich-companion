<script lang="ts">
  import type {
    AssetCardIndicatorConfig,
    AssetCardInlineTagMode,
    AssetSummary,
  } from '../types/assets';
  import AssetCard from './AssetCard.svelte';

  interface Props {
    assets: AssetSummary[];
    selectedIds: Set<string>;
    indicatorConfig: AssetCardIndicatorConfig;
    inlineTagMode: AssetCardInlineTagMode;
    matchingTagIds: ReadonlySet<string>;
    onopen: (index: number) => void;
    ontoggle: (assetId: string) => void;
  }

  let {
    assets,
    selectedIds,
    indicatorConfig,
    inlineTagMode,
    matchingTagIds,
    onopen,
    ontoggle,
  }: Props = $props();
</script>

<div class="asset-grid" aria-label="Asset search results">
  {#each assets as asset, index (asset.id)}
    <AssetCard
      {asset}
      {indicatorConfig}
      {inlineTagMode}
      {matchingTagIds}
      selected={selectedIds.has(asset.id)}
      onopen={() => onopen(index)}
      ontoggle={() => ontoggle(asset.id)}
    />
  {/each}
</div>

<style>
  .asset-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.9rem;
    align-items: start;
  }

  @media (max-width: 72rem) {
    .asset-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  @media (max-width: 52rem) {
    .asset-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 31rem) {
    .asset-grid {
      grid-template-columns: 1fr;
    }
  }
</style>

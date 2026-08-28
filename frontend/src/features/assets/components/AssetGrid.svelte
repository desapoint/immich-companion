<script lang="ts">
  import type {
    AssetCardIndicatorConfig,
    AssetLayoutMode,
    AssetSummary,
  } from '../types/assets';
  import AssetCard from './AssetCard.svelte';

  interface Props {
    assets: AssetSummary[];
    selectedIds: Set<string>;
    selectionActive: boolean;
    indicatorConfig: AssetCardIndicatorConfig;
    matchingTagIds: ReadonlySet<string>;
    layout: AssetLayoutMode;
    onopen: (index: number) => void;
    onselect: (index: number, shiftKey: boolean) => void;
    ondragstart: (index: number, event: PointerEvent) => void;
    ondragenter: (index: number, event: PointerEvent) => void;
  }

  let {
    assets,
    selectedIds,
    selectionActive,
    indicatorConfig,
    matchingTagIds,
    layout,
    onopen,
    onselect,
    ondragstart,
    ondragenter,
  }: Props = $props();
</script>

<div
  class={['asset-grid', { condensed: layout === 'condensed' }]}
  data-layout={layout}
  aria-label="Asset search results"
>
  {#each assets as asset, index (asset.id)}
    <AssetCard
      {asset}
      {indicatorConfig}
      {matchingTagIds}
      {selectionActive}
      condensed={layout === 'condensed'}
      selected={selectedIds.has(asset.id)}
      onopen={() => onopen(index)}
      onselect={(shiftKey) => onselect(index, shiftKey)}
      ondragstart={(event) => ondragstart(index, event)}
      ondragenter={(event) => ondragenter(index, event)}
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

  .asset-grid.condensed {
    grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
    gap: 0.55rem;
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

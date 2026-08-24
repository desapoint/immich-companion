<script lang="ts">
  import {
    copySearchGroup,
    createSearchGroup,
    createSimpleAssetSearchFilters,
    simpleFiltersToSearchGroup,
  } from '../state/assetViewModel';
  import type {
    AlbumOption,
    SearchGroup,
    SearchMode,
    SimpleAssetSearchFilters,
  } from '../types/assets';
  import AdvancedAssetSearch from './AdvancedAssetSearch.svelte';
  import AssetSearchModeSwitch from './AssetSearchModeSwitch.svelte';
  import SimpleAssetSearch from './SimpleAssetSearch.svelte';

  interface Props {
    albums: AlbumOption[];
    disabled?: boolean;
    onsearch: (expression: SearchGroup) => void;
  }

  let { albums, disabled = false, onsearch }: Props = $props();
  let mode = $state<SearchMode>('simple');
  let simpleFilters = $state<SimpleAssetSearchFilters>(createSimpleAssetSearchFilters());
  let advancedExpression = $state<SearchGroup>(createSearchGroup());

  function searchSimple(): void {
    onsearch(simpleFiltersToSearchGroup(simpleFilters));
  }

  function resetSimple(): void {
    simpleFilters = createSimpleAssetSearchFilters();
    onsearch(createSearchGroup());
  }

  function searchAdvanced(): void {
    onsearch(copySearchGroup(advancedExpression));
  }

  function resetAdvanced(): void {
    advancedExpression = createSearchGroup();
    onsearch(copySearchGroup(advancedExpression));
  }
</script>

<section class="search-toolbar" aria-label="Immich asset search">
  <AssetSearchModeSwitch {mode} onchange={(nextMode) => (mode = nextMode)} />

  {#if mode === 'simple'}
    <SimpleAssetSearch
      filters={simpleFilters}
      {disabled}
      onchange={(filters) => (simpleFilters = filters)}
      onsearch={searchSimple}
      onreset={resetSimple}
    />
  {:else}
    <AdvancedAssetSearch
      expression={advancedExpression}
      {albums}
      {disabled}
      onsearch={searchAdvanced}
      onreset={resetAdvanced}
    />
  {/if}
</section>

<style>
  .search-toolbar {
    display: grid;
    gap: 0.95rem;
    padding: clamp(0.9rem, 2vw, 1.2rem);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
  }

</style>

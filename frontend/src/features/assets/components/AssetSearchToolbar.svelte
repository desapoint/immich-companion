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
  import AssetSearchModeSwitch from './AssetSearchModeSwitch.svelte';
  import ExpertAssetSearch from './ExpertAssetSearch.svelte';
  import SimpleAssetSearch from './SimpleAssetSearch.svelte';

  interface Props {
    albums: AlbumOption[];
    disabled?: boolean;
    onsearch: (expression: SearchGroup) => void;
  }

  let { albums, disabled = false, onsearch }: Props = $props();
  let mode = $state<SearchMode>('simple');
  let simpleFilters = $state<SimpleAssetSearchFilters>(createSimpleAssetSearchFilters());
  let expertExpression = $state<SearchGroup>(createSearchGroup());

  function searchSimple(): void {
    onsearch(simpleFiltersToSearchGroup(simpleFilters));
  }

  function resetSimple(): void {
    const defaultFilters = createSimpleAssetSearchFilters();
    simpleFilters = defaultFilters;
    onsearch(simpleFiltersToSearchGroup(defaultFilters));
  }

  function searchExpert(): void {
    onsearch(copySearchGroup(expertExpression));
  }

  function resetExpert(): void {
    expertExpression = createSearchGroup();
    onsearch(copySearchGroup(expertExpression));
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
    <ExpertAssetSearch
      expression={expertExpression}
      {albums}
      {disabled}
      onsearch={searchExpert}
      onreset={resetExpert}
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

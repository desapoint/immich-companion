<script lang="ts">
  import {
    copySearchGroup,
    createSearchGroup,
    createSimpleAssetSearchFilters,
    simpleFiltersToSearchGroup,
  } from '../state/assetViewModel';
  import { createDefaultAssetSort } from '../state/assetSort';
  import type {
    AlbumOption,
    AssetSort,
    SearchGroup,
    SearchMode,
    SimpleAssetSearchFilters,
  } from '../types/assets';
  import AssetSearchModeSwitch from './AssetSearchModeSwitch.svelte';
  import AssetSortControls from './AssetSortControls.svelte';
  import ExpertAssetSearch from './ExpertAssetSearch.svelte';
  import SimpleAssetSearch from './SimpleAssetSearch.svelte';

  interface Props {
    albums: AlbumOption[];
    disabled?: boolean;
    onsearch: (expression: SearchGroup, sort: AssetSort) => void;
  }

  let { albums, disabled = false, onsearch }: Props = $props();
  let mode = $state<SearchMode>('simple');
  let simpleFilters = $state<SimpleAssetSearchFilters>(createSimpleAssetSearchFilters());
  let expertExpression = $state<SearchGroup>(createSearchGroup());
  let sort = $state<AssetSort>(createDefaultAssetSort());

  function changeSort(nextSort: AssetSort): void {
    sort = { ...nextSort };
    if (mode === 'simple') {
      onsearch(simpleFiltersToSearchGroup(simpleFilters), { ...sort });
    } else {
      onsearch(copySearchGroup(expertExpression), { ...sort });
    }
  }

  function searchSimple(): void {
    onsearch(simpleFiltersToSearchGroup(simpleFilters), { ...sort });
  }

  function resetSimple(): void {
    const defaultFilters = createSimpleAssetSearchFilters();
    simpleFilters = defaultFilters;
    onsearch(simpleFiltersToSearchGroup(defaultFilters), { ...sort });
  }

  function searchExpert(): void {
    onsearch(copySearchGroup(expertExpression), { ...sort });
  }

  function resetExpert(): void {
    expertExpression = createSearchGroup();
    onsearch(copySearchGroup(expertExpression), { ...sort });
  }
</script>

<section class="search-toolbar" aria-label="Immich asset search">
  <AssetSearchModeSwitch {mode} onchange={(nextMode) => (mode = nextMode)} />
  <AssetSortControls {sort} {disabled} onchange={changeSort} />

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

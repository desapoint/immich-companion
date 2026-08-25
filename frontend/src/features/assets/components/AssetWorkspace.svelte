<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import {
    getAlbumOptions,
    getAssetDetail,
    getTagOptions,
    searchAssets,
    synchronizeAssets,
  } from '../api/assetApi';
  import { createDefaultAssetSort } from '../state/assetSort';
  import {
    copySearchGroup,
    createSimpleAssetSearchFilters,
    simpleFiltersToSearchGroup,
    searchedTagIds,
    toggleSelectedAsset,
  } from '../state/assetViewModel';
  import { DEFAULT_ASSET_PAGE_SIZE } from '../state/assetPagination';
  import type {
    AlbumOption,
    AssetCardIndicatorConfig,
    AssetCardInlineTagMode,
    AssetComparisonActivation,
    AssetComparisonSource,
    AssetDetail,
    AssetSearchResponse,
    AssetSort,
    SearchGroup,
    TagOption,
  } from '../types/assets';
  import AssetEmptyState from './AssetEmptyState.svelte';
  import AssetErrorState from './AssetErrorState.svelte';
  import AssetGrid from './AssetGrid.svelte';
  import AssetLoadingState from './AssetLoadingState.svelte';
  import AssetPagination from './AssetPagination.svelte';
  import AssetResultStatus from './AssetResultStatus.svelte';
  import AssetSearchToolbar from './AssetSearchToolbar.svelte';
  import AssetViewerDialog from './AssetViewerDialog.svelte';

  let expression = $state<SearchGroup>(
    simpleFiltersToSearchGroup(createSimpleAssetSearchFilters()),
  );
  let albums = $state<AlbumOption[]>([]);
  let tags = $state<TagOption[]>([]);
  let results = $state<AssetSearchResponse | null>(null);
  let page = $state(1);
  let pageSize = $state(DEFAULT_ASSET_PAGE_SIZE);
  let sort = $state<AssetSort>(createDefaultAssetSort());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let syncing = $state(false);
  let syncMessage = $state<string | null>(null);
  let selectedIds = $state<Set<string>>(new Set());
  let viewerIndex = $state<number | null>(null);
  let detail = $state<AssetDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let inlineTagMode = $state<AssetCardInlineTagMode>('hidden');
  let searchController: AbortController | null = null;
  let detailController: AbortController | null = null;
  const detailCache = new Map<string, AssetDetail>();
  const cardIndicatorConfig: AssetCardIndicatorConfig = {
    albums: true,
    tags: true,
    stack: true,
    external: true,
    immich: true,
  };
  const viewerComparisonSource: AssetComparisonSource = 'stack';
  const viewerComparisonActivation: AssetComparisonActivation = 'click';
  const matchingTagIds = $derived(new Set(searchedTagIds(expression)));

  async function loadRelationOptions(): Promise<void> {
    const [albumResult, tagResult] = await Promise.allSettled([
      getAlbumOptions(),
      getTagOptions(),
    ]);
    albums = albumResult.status === 'fulfilled' ? albumResult.value : [];
    tags = tagResult.status === 'fulfilled' ? tagResult.value : [];
  }

  async function loadAssets(): Promise<void> {
    searchController?.abort();
    searchController = new AbortController();
    loading = true;
    error = null;
    try {
      results = await searchAssets(expression, page, pageSize, sort, searchController.signal);
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return;
      error = requestError instanceof Error ? requestError.message : 'Asset search failed.';
    } finally {
      if (!searchController.signal.aborted) loading = false;
    }
  }

  async function loadDetail(index: number): Promise<void> {
    const asset = results?.items[index];
    if (!asset) return;
    const cached = detailCache.get(asset.id);
    if (cached) {
      detail = cached;
      detailError = null;
      detailLoading = false;
      return;
    }

    detailController?.abort();
    const controller = new AbortController();
    detailController = controller;
    detail = null;
    detailError = null;
    detailLoading = true;
    try {
      const loaded = await getAssetDetail(asset.id, controller.signal);
      detailCache.set(asset.id, loaded);
      if (!controller.signal.aborted) detail = loaded;
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return;
      detailError = requestError instanceof Error ? requestError.message : 'Image details failed to load.';
    } finally {
      if (!controller.signal.aborted) detailLoading = false;
    }
  }

  function applySearch(nextExpression: SearchGroup, nextSort: AssetSort): void {
    expression = copySearchGroup(nextExpression);
    sort = { ...nextSort };
    page = 1;
    viewerIndex = null;
    void loadAssets();
  }

  function changePage(nextPage: number): void {
    page = nextPage;
    viewerIndex = null;
    void loadAssets();
    document.querySelector('.asset-workspace')?.scrollIntoView({ behavior: 'smooth' });
  }

  function changePageSize(nextPageSize: number): void {
    if (nextPageSize === pageSize) return;
    pageSize = nextPageSize;
    page = 1;
    viewerIndex = null;
    void loadAssets();
    document.querySelector('.asset-workspace')?.scrollIntoView({ behavior: 'smooth' });
  }

  function openViewer(index: number): void {
    viewerIndex = index;
    void loadDetail(index);
  }

  function navigateViewer(index: number): void {
    viewerIndex = index;
    void loadDetail(index);
  }

  function toggleSelection(assetId: string): void {
    selectedIds = toggleSelectedAsset(selectedIds, assetId);
  }

  async function syncAssets(): Promise<void> {
    syncing = true;
    syncMessage = null;
    error = null;
    try {
      const result = await synchronizeAssets();
      syncMessage = `Synced ${result.seen} assets · ${result.created} new · ${result.removed} removed`;
      detailCache.clear();
      await loadRelationOptions();
      await loadAssets();
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'Immich sync failed.';
    } finally {
      syncing = false;
    }
  }

  onMount(() => {
    void loadRelationOptions();
    void loadAssets();
  });

  onDestroy(() => {
    searchController?.abort();
    detailController?.abort();
  });
</script>

<section class="asset-workspace" aria-label="Asset search workspace">
  <AssetSearchToolbar {albums} {tags} disabled={loading || syncing} onsearch={applySearch} />

  <AssetResultStatus
    total={results?.total ?? 0}
    shown={results?.items.length ?? 0}
    selected={selectedIds.size}
    {syncing}
    {syncMessage}
    {inlineTagMode}
    searchedTagCount={matchingTagIds.size}
    onsync={syncAssets}
    oninlinetagmodechange={(mode) => (inlineTagMode = mode)}
  />

  {#if loading && !results}
    <AssetLoadingState />
  {:else if error}
    <AssetErrorState message={error} onretry={loadAssets} />
  {:else if results && results.items.length === 0}
    <AssetEmptyState {syncing} onsync={syncAssets} />
  {:else if results}
    <AssetGrid
      assets={results.items}
      {selectedIds}
      indicatorConfig={cardIndicatorConfig}
      {inlineTagMode}
      {matchingTagIds}
      onopen={openViewer}
      ontoggle={toggleSelection}
    />
    <AssetPagination
      page={results.page}
      pages={results.pages}
      total={results.total}
      pageSize={results.page_size}
      disabled={loading}
      onpage={changePage}
      onpagesizechange={changePageSize}
    />
  {/if}
</section>

{#if viewerIndex !== null && results?.items[viewerIndex]}
  <AssetViewerDialog
    assets={results.items}
    initialIndex={viewerIndex}
    {selectedIds}
    {detail}
    {detailLoading}
    {detailError}
    comparisonSource={viewerComparisonSource}
    comparisonActivation={viewerComparisonActivation}
    onnavigate={navigateViewer}
    ontoggleselection={toggleSelection}
    onclose={() => (viewerIndex = null)}
  />
{/if}

<style>
  .asset-workspace {
    display: grid;
    gap: 1.1rem;
  }
</style>

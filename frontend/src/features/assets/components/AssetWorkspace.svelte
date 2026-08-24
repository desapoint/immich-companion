<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import {
    getAlbumOptions,
    getAssetDetail,
    searchAssets,
    synchronizeAssets,
  } from '../api/assetApi';
  import {
    copySearchGroup,
    createSearchGroup,
    toggleSelectedAsset,
  } from '../state/assetViewModel';
  import type {
    AlbumOption,
    AssetDetail,
    AssetSearchResponse,
    SearchGroup,
  } from '../types/assets';
  import AssetEmptyState from './AssetEmptyState.svelte';
  import AssetErrorState from './AssetErrorState.svelte';
  import AssetGrid from './AssetGrid.svelte';
  import AssetLoadingState from './AssetLoadingState.svelte';
  import AssetPagination from './AssetPagination.svelte';
  import AssetResultStatus from './AssetResultStatus.svelte';
  import AssetSearchToolbar from './AssetSearchToolbar.svelte';
  import AssetViewerDialog from './AssetViewerDialog.svelte';

  let expression = $state<SearchGroup>(createSearchGroup());
  let albums = $state<AlbumOption[]>([]);
  let results = $state<AssetSearchResponse | null>(null);
  let page = $state(1);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let syncing = $state(false);
  let syncMessage = $state<string | null>(null);
  let selectedIds = $state<Set<string>>(new Set());
  let viewerIndex = $state<number | null>(null);
  let detail = $state<AssetDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let searchController: AbortController | null = null;
  let detailController: AbortController | null = null;
  const detailCache = new Map<string, AssetDetail>();

  async function loadAssets(): Promise<void> {
    searchController?.abort();
    searchController = new AbortController();
    loading = true;
    error = null;
    try {
      results = await searchAssets(expression, page, searchController.signal);
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

  function applySearch(nextExpression: SearchGroup): void {
    expression = copySearchGroup(nextExpression);
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
      await loadAssets();
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'Immich sync failed.';
    } finally {
      syncing = false;
    }
  }

  onMount(() => {
    void getAlbumOptions().then((loaded) => (albums = loaded)).catch(() => {
      albums = [];
    });
    void loadAssets();
  });

  onDestroy(() => {
    searchController?.abort();
    detailController?.abort();
  });
</script>

<section class="asset-workspace" aria-label="Asset search workspace">
  <AssetSearchToolbar {expression} {albums} disabled={loading || syncing} onsearch={applySearch} />

  <AssetResultStatus
    total={results?.total ?? 0}
    shown={results?.items.length ?? 0}
    selected={selectedIds.size}
    {syncing}
    {syncMessage}
    onsync={syncAssets}
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
      onopen={openViewer}
      ontoggle={toggleSelection}
    />
    <AssetPagination page={results.page} pages={results.pages} disabled={loading} onpage={changePage} />
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

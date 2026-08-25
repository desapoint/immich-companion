<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import {
    getAlbumOptions,
    getAssetDetail,
    getTagOptions,
    executeAssetAction,
    planAssetAction,
    resolveAssetSelection,
    searchAssets,
    synchronizeAssets,
  } from '../api/assetApi';
  import { createDefaultAssetSort } from '../state/assetSort';
  import {
    buildSelectionRequest,
    createAssetSelectionState,
    invertCurrentPage,
    isAssetSelected,
    selectAllMatching,
    selectCurrentPage,
    selectedAssetCount,
    toggleAssetSelection,
  } from '../state/assetSelection';
  import {
    copySearchGroup,
    createSimpleAssetSearchFilters,
    simpleFiltersToSearchGroup,
    searchedTagIds,
  } from '../state/assetViewModel';
  import { DEFAULT_ASSET_PAGE_SIZE } from '../state/assetPagination';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetActionPlan,
    AssetCardIndicatorConfig,
    AssetComparisonActivation,
    AssetComparisonSource,
    AssetDetail,
    AssetSearchResponse,
    AssetSelectionResolution,
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
  import AssetSelectionActions from './AssetSelectionActions.svelte';
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
  let selection = $state(createAssetSelectionState());
  let selectionResolution = $state<AssetSelectionResolution | null>(null);
  let selectionLoading = $state(false);
  let actionPlan = $state<AssetActionPlan | null>(null);
  let actionBusy = $state(false);
  let actionMessage = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let viewerIndex = $state<number | null>(null);
  let detail = $state<AssetDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let searchController: AbortController | null = null;
  let detailController: AbortController | null = null;
  let selectionController: AbortController | null = null;
  const detailCache = new Map<string, AssetDetail>();
  const cardIndicatorConfig: AssetCardIndicatorConfig = {
    albums: true,
    tags: true,
    stack: true,
    external: true,
    immich: true,
    inlineTags: 'hidden',
  };
  const viewerComparisonSource: AssetComparisonSource = 'stack';
  const viewerComparisonActivation: AssetComparisonActivation = 'click';
  const matchingTagIds = $derived(new Set(searchedTagIds(expression)));
  const selectedCount = $derived(selectedAssetCount(selection, results?.total ?? 0));
  const visibleSelectedIds = $derived(new Set(
    results?.items
      .filter((asset) => isAssetSelected(selection, asset.id))
      .map((asset) => asset.id) ?? [],
  ));

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
    clearSelection();
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
    selection = toggleAssetSelection(selection, assetId);
    actionPlan = null;
    void refreshSelection();
  }

  function clearSelection(): void {
    selection = createAssetSelectionState();
    selectionResolution = null;
    actionPlan = null;
    selectionController?.abort();
    selectionLoading = false;
  }

  function selectPage(): void {
    selection = selectCurrentPage(
      selection,
      results?.items.map((asset) => asset.id) ?? [],
    );
    actionPlan = null;
    void refreshSelection();
  }

  function selectEveryMatch(): void {
    selection = selectAllMatching();
    actionPlan = null;
    void refreshSelection();
  }

  function invertPage(): void {
    selection = invertCurrentPage(
      selection,
      results?.items.map((asset) => asset.id) ?? [],
    );
    actionPlan = null;
    void refreshSelection();
  }

  async function refreshSelection(): Promise<void> {
    selectionController?.abort();
    if (selectedAssetCount(selection, results?.total ?? 0) === 0) {
      selectionResolution = null;
      return;
    }
    const controller = new AbortController();
    selectionController = controller;
    selectionLoading = true;
    actionError = null;
    try {
      const resolved = await resolveAssetSelection(
        buildSelectionRequest(selection, expression),
        controller.signal,
      );
      if (!controller.signal.aborted) selectionResolution = resolved;
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return;
      if (!controller.signal.aborted) {
        actionError = requestError instanceof Error
          ? requestError.message
          : 'Selection resolution failed.';
      }
    } finally {
      if (!controller.signal.aborted) selectionLoading = false;
    }
  }

  async function previewAction(
    action: AssetActionIntent,
    relationId: string | null = null,
  ): Promise<void> {
    actionBusy = true;
    actionError = null;
    actionMessage = null;
    actionPlan = null;
    try {
      actionPlan = await planAssetAction(
        buildSelectionRequest(selection, expression),
        action,
        relationId,
      );
    } catch (requestError) {
      actionError = requestError instanceof Error
        ? requestError.message
        : 'Action planning failed.';
    } finally {
      actionBusy = false;
    }
  }

  async function confirmAction(): Promise<void> {
    if (!actionPlan) return;
    actionBusy = true;
    actionError = null;
    try {
      const result = await executeAssetAction(actionPlan.id);
      actionMessage = `${result.applied_count} changed · ${result.skipped_count} skipped`;
      actionPlan = null;
      clearSelection();
      detailCache.clear();
      page = 1;
      await Promise.all([loadRelationOptions(), loadAssets()]);
    } catch (requestError) {
      actionError = requestError instanceof Error
        ? requestError.message
        : 'Action execution failed.';
    } finally {
      actionBusy = false;
    }
  }

  async function syncAssets(): Promise<void> {
    syncing = true;
    syncMessage = null;
    error = null;
    try {
      const result = await synchronizeAssets();
      syncMessage = `Synced ${result.seen} assets · ${result.created} new · ${result.removed} removed`;
      detailCache.clear();
      clearSelection();
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
    selectionController?.abort();
  });
</script>

<section class="asset-workspace" aria-label="Asset search workspace">
  <AssetSearchToolbar {albums} {tags} disabled={loading || syncing} onsearch={applySearch} />

  <AssetResultStatus
    total={results?.total ?? 0}
    shown={results?.items.length ?? 0}
    selected={selectedCount}
    {syncing}
    {syncMessage}
    onsync={syncAssets}
  />

  {#if results}
    <AssetSelectionActions
      {selectedCount}
      matchingTotal={results.total}
      currentPageCount={results.items.length}
      allMatching={selection.mode === 'all_matching'}
      summary={selectionResolution?.summary ?? null}
      {albums}
      {tags}
      plan={actionPlan}
      busy={selectionLoading || actionBusy || syncing}
      message={actionMessage}
      error={actionError}
      onselectpage={selectPage}
      onselectall={selectEveryMatch}
      oninvertpage={invertPage}
      onclear={clearSelection}
      onplan={previewAction}
      onconfirm={confirmAction}
      oncancel={() => (actionPlan = null)}
    />
  {/if}

  {#if loading && !results}
    <AssetLoadingState />
  {:else if error}
    <AssetErrorState message={error} onretry={loadAssets} />
  {:else if results && results.items.length === 0}
    <AssetEmptyState {syncing} onsync={syncAssets} />
  {:else if results}
    <AssetGrid
      assets={results.items}
      selectedIds={visibleSelectedIds}
      indicatorConfig={cardIndicatorConfig}
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
    selectedIds={visibleSelectedIds}
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

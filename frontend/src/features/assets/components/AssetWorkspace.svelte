<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import {
    getAlbumOptions,
    getAssetDetail,
    getAssetSyncStatus,
    getTagOptions,
    executeAssetAction,
    matchAssetSearch,
    planAssetAction,
    resolveAssetSelection,
    searchAssets,
    startAssetSync,
  } from '../api/assetApi';
  import { createDefaultAssetSort } from '../state/assetSort';
  import {
    buildSelectionRequest,
    buildExplicitAssetSelectionRequest,
    createAssetSelectionState,
    invertCurrentPage,
    isAssetSelected,
    selectAllMatching,
    selectCurrentPage,
    selectedAssetCount,
    setSelectionRange,
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
    AssetActionResult,
    AssetCardIndicatorConfig,
    AssetComparisonActivation,
    AssetComparisonSource,
    AssetDetail,
    AssetSearchResponse,
    AssetSummary,
    AssetSyncCoordinatorStatus,
    AssetSyncMode,
    AssetSelectionResolution,
    AssetSelectionRequest,
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
  let syncProgress = $state<import('../types/assets').AssetSyncProgress | null>(null);
  let selection = $state(createAssetSelectionState());
  let selectionResolution = $state<AssetSelectionResolution | null>(null);
  let selectionLoading = $state(false);
  let actionPlan = $state<AssetActionPlan | null>(null);
  let actionBusy = $state(false);
  let actionMessage = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let actionContext = $state<'selection' | 'viewer'>('selection');
  let actionTargetIds = $state<string[]>([]);
  let viewerIndex = $state<number | null>(null);
  let detail = $state<AssetDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let searchController: AbortController | null = null;
  let detailController: AbortController | null = null;
  let selectionController: AbortController | null = null;
  let viewerActionController: AbortController | null = null;
  let viewerActionAssetId = $state<string | null>(null);
  let viewerActionResolution = $state<AssetSelectionResolution | null>(null);
  let viewerActionError = $state<string | null>(null);
  let selectionAnchorIndex: number | null = null;
  let dragSelecting = false;
  let dragSelectionValue = true;
  let dragLastIndex: number | null = null;
  let syncPollTimer: ReturnType<typeof setInterval> | null = null;
  let syncStatusInitialized = false;
  let handledSyncSuccessId: string | null = null;
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

  async function refreshDetail(assetId: string): Promise<void> {
    detailController?.abort();
    const controller = new AbortController();
    detailController = controller;
    detailError = null;
    detailLoading = true;
    try {
      const loaded = await getAssetDetail(assetId, controller.signal);
      detailCache.set(assetId, loaded);
      if (!controller.signal.aborted) detail = loaded;
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return;
      if (!controller.signal.aborted) {
        detailError = requestError instanceof Error
          ? requestError.message
          : 'Image details failed to load.';
      }
    } finally {
      if (!controller.signal.aborted) detailLoading = false;
    }
  }

  function patchResultAsset(asset: AssetSummary): number {
    if (!results) return -1;
    const index = results.items.findIndex((item) => item.id === asset.id);
    if (index < 0) return -1;
    results = {
      ...results,
      items: results.items.map((item) => item.id === asset.id ? asset : item),
    };
    return index;
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
    selectionAnchorIndex = null;
    void loadAssets();
    document.querySelector('.asset-workspace')?.scrollIntoView({ behavior: 'smooth' });
  }

  function changePageSize(nextPageSize: number): void {
    if (nextPageSize === pageSize) return;
    pageSize = nextPageSize;
    page = 1;
    viewerIndex = null;
    selectionAnchorIndex = null;
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

  function selectAtIndex(index: number, shiftKey: boolean): void {
    const items = results?.items ?? [];
    const asset = items[index];
    if (!asset) return;
    const shouldSelect = !isAssetSelected(selection, asset.id);
    selection = shiftKey && selectionAnchorIndex !== null
      ? setSelectionRange(
          selection,
          items.map((item) => item.id),
          selectionAnchorIndex,
          index,
          shouldSelect,
        )
      : setSelectionRange(selection, items.map((item) => item.id), index, index, shouldSelect);
    selectionAnchorIndex = index;
    actionPlan = null;
    void refreshSelection();
  }

  function beginDragSelection(index: number, event: PointerEvent): void {
    if (event.shiftKey) {
      selectAtIndex(index, true);
      return;
    }
    const items = results?.items ?? [];
    const asset = items[index];
    if (!asset) return;
    dragSelectionValue = !isAssetSelected(selection, asset.id);
    dragSelecting = true;
    dragLastIndex = index;
    selection = setSelectionRange(
      selection,
      items.map((item) => item.id),
      index,
      index,
      dragSelectionValue,
    );
    actionPlan = null;
  }

  function continueDragSelection(index: number, event: PointerEvent): void {
    if (!dragSelecting || event.pointerType !== 'mouse') return;
    if ((event.buttons & 1) === 0) {
      finishDragSelection();
      return;
    }
    if (dragLastIndex === null || dragLastIndex === index) return;
    const ids = results?.items.map((item) => item.id) ?? [];
    selection = setSelectionRange(
      selection,
      ids,
      dragLastIndex,
      index,
      dragSelectionValue,
    );
    dragLastIndex = index;
    actionPlan = null;
  }

  function finishDragSelection(): void {
    if (!dragSelecting) return;
    dragSelecting = false;
    selectionAnchorIndex = dragLastIndex;
    dragLastIndex = null;
    void refreshSelection();
  }

  function clearSelection(): void {
    selection = createAssetSelectionState();
    selectionResolution = null;
    actionPlan = null;
    selectionController?.abort();
    selectionLoading = false;
    selectionAnchorIndex = null;
    dragSelecting = false;
    dragLastIndex = null;
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

  async function createActionPlan(
    request: AssetSelectionRequest,
    context: 'selection' | 'viewer',
    action: AssetActionIntent,
    relationIds: string[] = [],
  ): Promise<void> {
    actionBusy = true;
    actionError = null;
    actionMessage = null;
    actionPlan = null;
    actionContext = context;
    actionTargetIds = request.mode === 'explicit' ? [...request.ids] : [];
    try {
      actionPlan = await planAssetAction(
        request,
        action,
        relationIds,
      );
    } catch (requestError) {
      actionError = requestError instanceof Error
        ? requestError.message
        : 'Action planning failed.';
    } finally {
      actionBusy = false;
    }
  }

  function previewSelectionAction(
    action: AssetActionIntent,
    relationIds: string[] = [],
  ): void {
    void createActionPlan(
      buildSelectionRequest(selection, expression),
      'selection',
      action,
      relationIds,
    );
  }

  function previewViewerAction(
    assetId: string,
    action: AssetActionIntent,
    relationIds: string[] = [],
  ): void {
    void createActionPlan(
      buildExplicitAssetSelectionRequest(assetId),
      'viewer',
      action,
      relationIds,
    );
  }

  async function applyActionResult(
    result: AssetActionResult,
    confirmedContext: 'selection' | 'viewer',
    confirmedTargetIds: string[],
  ): Promise<void> {
    const confirmedTargetId = confirmedTargetIds[0] ?? null;
    actionMessage = `${result.applied_count} changed · ${result.skipped_count} skipped${
      result.failed_ids.length ? ` · ${result.failed_ids.length} assets failed verification` : ''
    }`;
    actionPlan = null;
    if (confirmedContext === 'selection') {
      detailCache.clear();
      clearSelection();
      page = 1;
      await Promise.all([loadRelationOptions(), loadAssets()]);
    } else {
      if (!confirmedTargetId) {
        closeViewer();
        await Promise.all([loadRelationOptions(), loadAssets()]);
      } else {
        const [refreshedAsset] = await Promise.all([
          matchAssetSearch(confirmedTargetId, expression),
          loadRelationOptions(),
        ]);
        if (!refreshedAsset) {
          closeViewer();
          await loadAssets();
        } else {
          const refreshedIndex = patchResultAsset(refreshedAsset);
          if (refreshedIndex >= 0) viewerIndex = refreshedIndex;
          detailCache.delete(confirmedTargetId);
          await Promise.all([
            refreshDetail(confirmedTargetId),
            resolveViewerActionState(confirmedTargetId, true),
          ]);
        }
        if (selectedCount > 0) void refreshSelection();
      }
    }
    actionTargetIds = [];
  }

  async function createAndExecuteRelationAction(
    request: AssetSelectionRequest,
    context: 'selection' | 'viewer',
    action: Extract<AssetActionIntent, 'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'>,
    relationIds: string[],
  ): Promise<void> {
    actionBusy = true;
    actionError = null;
    actionMessage = null;
    actionPlan = null;
    actionContext = context;
    actionTargetIds = request.mode === 'explicit' ? [...request.ids] : [];
    try {
      const plan = await planAssetAction(request, action, relationIds);
      const result = await executeAssetAction(plan.id);
      await applyActionResult(result, context, actionTargetIds);
    } catch (requestError) {
      actionError = requestError instanceof Error
        ? requestError.message
        : 'Relation action failed.';
    } finally {
      actionBusy = false;
    }
  }

  function confirmSelectionRelationAction(
    action: Extract<AssetActionIntent, 'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'>,
    relationIds: string[],
  ): void {
    void createAndExecuteRelationAction(
      buildSelectionRequest(selection, expression),
      'selection',
      action,
      relationIds,
    );
  }

  function confirmViewerRelationAction(
    assetId: string,
    action: Extract<AssetActionIntent, 'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'>,
    relationIds: string[],
  ): void {
    void createAndExecuteRelationAction(
      buildExplicitAssetSelectionRequest(assetId),
      'viewer',
      action,
      relationIds,
    );
  }

  async function resolveViewerActionState(assetId: string, force = false): Promise<void> {
    if (!force && viewerActionAssetId === assetId && viewerActionResolution) return;
    viewerActionController?.abort();
    const controller = new AbortController();
    viewerActionController = controller;
    viewerActionAssetId = assetId;
    viewerActionResolution = null;
    viewerActionError = null;
    try {
      const resolved = await resolveAssetSelection(
        buildExplicitAssetSelectionRequest(assetId),
        controller.signal,
      );
      if (!controller.signal.aborted) viewerActionResolution = resolved;
    } catch (requestError) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return;
      if (!controller.signal.aborted) {
        viewerActionError = requestError instanceof Error
          ? requestError.message
          : 'Image action state could not be resolved.';
      }
    }
  }

  function closeViewer(): void {
    viewerIndex = null;
    viewerActionController?.abort();
    viewerActionAssetId = null;
    viewerActionResolution = null;
    viewerActionError = null;
    if (actionContext === 'viewer') {
      actionPlan = null;
      actionError = null;
      actionTargetIds = [];
    }
  }

  async function confirmAction(): Promise<void> {
    if (!actionPlan) return;
    const confirmedContext = actionContext;
    const confirmedTargetIds = [...actionTargetIds];
    actionBusy = true;
    actionError = null;
    try {
      const result = await executeAssetAction(actionPlan.id);
      await applyActionResult(result, confirmedContext, confirmedTargetIds);
    } catch (requestError) {
      actionError = requestError instanceof Error
        ? requestError.message
        : 'Action execution failed.';
    } finally {
      actionBusy = false;
    }
  }

  function describeSync(status: AssetSyncCoordinatorStatus): string | null {
    const active = status.active;
    if (active) {
      const label = active.mode === 'full' ? 'Full sync' : 'Incremental sync';
      const assetsSeen = active.counters.assets_seen ?? 0;
      const albumsSeen = active.counters.albums_seen ?? 0;
      const tagsSeen = active.counters.tags_seen ?? 0;
      const pending = status.pending ? ' · follow-up queued' : '';
      return `${label} · ${active.phase} · ${albumsSeen} albums · ${tagsSeen} tags · ${assetsSeen} assets${pending}`;
    }
    if (status.pending) return `${status.pending.mode === 'full' ? 'Full' : 'Incremental'} sync queued`;
    if (status.last_success) {
      const counters = status.last_success.counters;
      return `Last ${status.last_success.mode} sync · ${counters.assets_seen ?? 0} assets · ${counters.assets_removed ?? 0} removed`;
    }
    return null;
  }

  async function refreshSyncStatus(): Promise<void> {
    try {
      const next = await getAssetSyncStatus();
      const nextSuccessId = next.last_success?.id ?? null;
      const completedSinceLastCheck = syncStatusInitialized
        && nextSuccessId !== null
        && nextSuccessId !== handledSyncSuccessId;
      syncing = next.active !== null || next.pending !== null;
      syncMessage = next.active || next.pending ? describeSync(next) : null;
      syncProgress = next.active?.progress ?? null;
      if (!syncStatusInitialized) {
        syncStatusInitialized = true;
        handledSyncSuccessId = nextSuccessId;
      } else if (completedSinceLastCheck) {
        handledSyncSuccessId = nextSuccessId;
        detailCache.clear();
        clearSelection();
        await Promise.all([loadRelationOptions(), loadAssets()]);
      }
    } catch (requestError) {
      if (!syncStatusInitialized) {
        syncMessage = requestError instanceof Error
          ? requestError.message
          : 'Sync status is unavailable.';
      }
    }
  }

  async function syncAssets(mode: AssetSyncMode = 'incremental'): Promise<void> {
    syncing = true;
    syncMessage = mode === 'full' ? 'Queueing full sync…' : 'Queueing incremental sync…';
    error = null;
    try {
      await startAssetSync(mode);
      await refreshSyncStatus();
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'Immich sync failed.';
      syncing = false;
    }
  }

  onMount(() => {
    window.addEventListener('pointerup', finishDragSelection);
    window.addEventListener('pointercancel', finishDragSelection);
    void loadRelationOptions();
    void loadAssets();
    void refreshSyncStatus();
    syncPollTimer = setInterval(() => void refreshSyncStatus(), 1500);
    return () => {
      window.removeEventListener('pointerup', finishDragSelection);
      window.removeEventListener('pointercancel', finishDragSelection);
      if (syncPollTimer !== null) clearInterval(syncPollTimer);
    };
  });

  onDestroy(() => {
    searchController?.abort();
    detailController?.abort();
    selectionController?.abort();
    viewerActionController?.abort();
    if (syncPollTimer !== null) clearInterval(syncPollTimer);
  });
</script>

<section class="asset-workspace" aria-label="Asset search workspace">
  <AssetSearchToolbar {albums} {tags} disabled={loading} onsearch={applySearch} />

  <AssetResultStatus
    total={results?.total ?? 0}
    shown={results?.items.length ?? 0}
    selected={selectedCount}
    {syncing}
    {syncMessage}
    {syncProgress}
    onsync={() => void syncAssets('incremental')}
    onfullsync={() => void syncAssets('full')}
  />

  {#if results && selectedCount > 0}
    <AssetSelectionActions
      {selectedCount}
      matchingTotal={results.total}
      currentPageCount={results.items.length}
      allMatching={selection.mode === 'all_matching'}
      summary={selectionResolution?.summary ?? null}
      {albums}
      {tags}
      plan={actionContext === 'selection' ? actionPlan : null}
      busy={selectionLoading || actionBusy}
      error={actionContext === 'selection' ? actionError : null}
      onselectpage={selectPage}
      onselectall={selectEveryMatch}
      oninvertpage={invertPage}
      onclear={clearSelection}
      onplan={previewSelectionAction}
      onrelationconfirm={confirmSelectionRelationAction}
      onconfirm={confirmAction}
      oncancel={() => (actionPlan = null)}
    />
  {/if}

  {#if actionMessage}<p class="action-message" role="status">{actionMessage}</p>{/if}

  {#if loading && !results}
    <AssetLoadingState />
  {:else if error}
    <AssetErrorState message={error} onretry={loadAssets} />
  {:else if results && results.items.length === 0}
    <AssetEmptyState {syncing} onsync={() => void syncAssets('incremental')} />
  {:else if results}
    <AssetGrid
      assets={results.items}
      selectedIds={visibleSelectedIds}
      selectionActive={selectedCount > 0}
      indicatorConfig={cardIndicatorConfig}
      {matchingTagIds}
      onopen={openViewer}
      onselect={selectAtIndex}
      ondragstart={beginDragSelection}
      ondragenter={continueDragSelection}
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
    {albums}
    {tags}
    actionPlan={actionContext === 'viewer' ? actionPlan : null}
    actionSummary={viewerActionAssetId ? viewerActionResolution?.summary ?? null : null}
    {actionBusy}
    actionError={actionContext === 'viewer' ? actionError ?? viewerActionError : viewerActionError}
    comparisonSource={viewerComparisonSource}
    comparisonActivation={viewerComparisonActivation}
    onnavigate={navigateViewer}
    ontoggleselection={toggleSelection}
    onvisiblechange={(assetId) => void resolveViewerActionState(assetId)}
    onaction={previewViewerAction}
    onrelationconfirm={confirmViewerRelationAction}
    onconfirmaction={confirmAction}
    oncancelaction={() => (actionPlan = null)}
    onclose={closeViewer}
  />
{/if}

<style>
  .asset-workspace {
    display: grid;
    gap: 1.1rem;
  }

  .action-message {
    margin: 0;
    color: var(--color-accent-strong);
    font-size: 0.74rem;
    font-weight: 720;
  }
</style>

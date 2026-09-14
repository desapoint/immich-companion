<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';

  import {
    getAlbumOptions,
    getAssetDetail,
    getAssetSummary,
    getAssetSyncRunStatus,
    getAssetSyncStatus,
    cancelTask,
    listTasks,
    getTaskStatus,
    openTaskUpdates,
    createAssetSelection,
    getAssetSelectionMembership,
    getTagOptions,
    executeAssetAction,
    executeAssetActionTask,
    isAssetSelectionUnavailableError,
    isTaskUnavailableError,
    matchAssetSearch,
    selectAllAssetSelection,
    updateAssetSelectionMembers,
    planAssetAction,
    resolveAssetSelection,
    searchAssets,
    startAssetSync,
    synchronizeAsset,
    synchronizeAssetSelection,
  } from '../api/assetApi';
  import { createDefaultAssetSort } from '../state/assetSort';
  import {
    buildSelectionRequest,
    buildExplicitAssetSelectionRequest,
    canMergeServerSelectionPages,
    createAssetSelectionState,
    invertCurrentPage,
    isAssetSelected,
    mergeServerSelectionPage,
    mergeServerSelectionPages,
    patchServerSelectionMembership,
    selectCurrentPage,
    selectedAssetCount,
    setSelectionRange,
    setExplicitAssetIds,
    setServerSelection,
    toggleAssetSelection,
  } from '../state/assetSelection';
  import {
    copySearchGroup,
    createSimpleAssetSearchFilters,
    simpleFiltersToSearchGroup,
    searchedTagIds,
  } from '../state/assetViewModel';
  import { DEFAULT_ASSET_PAGE_SIZE } from '../state/assetPagination';
  import {
    ASSET_LIST_MODE_STORAGE_KEY,
    decodeAssetListMode,
    firstSurvivingScrollAnchor,
    infiniteWindowPages,
    mergeInfiniteWindowItems,
    type AssetListMode,
    type InfiniteScrollAnchor,
  } from '../state/assetInfiniteWindow';
  import { BoundedCache } from '../state/boundedCache';
  import { CoalescedPoller } from '../state/coalescedPoller';
  import { LatestRequest, isAbortError, requestErrorMessage } from '../state/latestRequest';
  import { SelectionOwnership } from '../state/selectionOwnership';
  import { isTaskTerminal, shouldApplyTaskStatus } from '../state/taskStatus';
  import { TaskUpdateConnection } from '../state/taskUpdateConnection';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetActionPlan,
    AssetActionResult,
    AssetCardIndicatorConfig,
    AssetLayoutMode,
    AssetComparisonActivation,
    AssetComparisonSource,
    AssetDetail,
    AssetSearchResponse,
    AssetSummary,
    AssetSyncCoordinatorStatus,
    AssetSyncMode,
    AssetTaskStatus,
    AssetSelectionResolution,
    AssetSelectionRequest,
    AssetSort,
    SearchGroup,
    StackResolution,
    TagOption,
  } from '../types/assets';
  import AssetEmptyState from './AssetEmptyState.svelte';
  import AssetErrorState from './AssetErrorState.svelte';
  import AssetGrid from './AssetGrid.svelte';
  import LayoutModeSwitch from '../../../lib/components/ui/LayoutModeSwitch.svelte';
  import StatusNotice from '../../../lib/components/ui/StatusNotice.svelte';
  import AssetLoadingState from './AssetLoadingState.svelte';
  import AssetPagination from './AssetPagination.svelte';
  import AssetResultStatus from './AssetResultStatus.svelte';
  import AssetSearchToolbar from './AssetSearchToolbar.svelte';
  import AssetSelectionActions from './AssetSelectionActions.svelte';
  import AssetTaskErrorDialog from './AssetTaskErrorDialog.svelte';
  import AssetActionErrorDialog from './AssetActionErrorDialog.svelte';
  import AssetActionTaskHistory from './AssetActionTaskHistory.svelte';
  import AssetTaskProgress from './AssetTaskProgress.svelte';
  import AssetViewerDialog from './AssetViewerDialog.svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';

  const activeSyncPollMs = 1500;
  const idleSyncPollMs = 10000;
  const hiddenSyncPollMs = 30000;
  const taskFallbackPollMs = 1000;
  const detailCacheSize = 24;
  const selectionSyncTaskStorageKey = 'immich-companion:selected-sync-task';
  const selectionSyncOwnerStorageKey = 'immich-companion:selected-sync-task-owner';
  const actionTaskStorageKey = 'immich-companion:asset-action-task';
  const actionTaskOwnerStorageKey = 'immich-companion:asset-action-task-owner';
  const expiredSelectionMessage = 'The server-backed selection expired. Select the assets again.';

  let expression = $state<SearchGroup>(
    simpleFiltersToSearchGroup(createSimpleAssetSearchFilters()),
  );
  let albums = $state<AlbumOption[]>([]);
  let tags = $state<TagOption[]>([]);
  let results = $state<AssetSearchResponse | null>(null);
  let page = $state(1);
  let pageSize = $state(DEFAULT_ASSET_PAGE_SIZE);
  let listMode = $state<AssetListMode>('paged');
  let layoutMode = $state<AssetLayoutMode>('normal');
  let infiniteLoading = $state(false);
  let infiniteSentinel = $state<HTMLDivElement | undefined>(undefined);
  let assetLoadGeneration = 0;
  let sort = $state<AssetSort>(createDefaultAssetSort());
  let loading = $state(true);
  let error = $state<string | null>(null);
  let syncing = $state(false);
  let syncMessage = $state<string | null>(null);
  let syncError = $state<string | null>(null);
  let syncCompletionMessage = $state<string | null>(null);
  let syncProgress = $state<import('../types/assets').AssetSyncProgress | null>(null);
  let selection = $state(createAssetSelectionState());
  let stackPrimaryAssetId = $state<string | null>(null);
  let selectionResolution = $state<AssetSelectionResolution | null>(null);
  let selectionLoading = $state(false);
  let actionPlan = $state<AssetActionPlan | null>(null);
  let actionBusy = $state(false);
  let actionMessage = $state<string | null>(null);
  let actionCompletionMessage = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let actionContext = $state<'selection' | 'viewer'>('selection');
  let actionTargetIds = $state<string[]>([]);
  let viewerIndex = $state<number | null>(null);
  let viewerSelectedAsset = $state<AssetSummary | null>(null);
  let detail = $state<AssetDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let viewerSyncing = $state(false);
  let viewerSyncError = $state<string | null>(null);
  let selectionSyncing = $state(false);
  let selectionSyncError = $state<string | null>(null);
  let selectionTask = $state<AssetTaskStatus | null>(null);
  let selectionTaskErrorOpen = $state(false);
  let searchController: AbortController | null = null;
  let viewerActionAssetId = $state<string | null>(null);
  let viewerActionResolution = $state<AssetSelectionResolution | null>(null);
  let viewerActionError = $state<string | null>(null);
  let selectionAnchorIndex: number | null = null;
  let dragSelecting = false;
  let dragSelectionValue = true;
  let dragLastIndex: number | null = null;
  let dragChangedIds = new Set<string>();
  let actionTask = $state<AssetTaskStatus | null>(null);
  let actionTaskHistory = $state<AssetTaskStatus[]>([]);
  let taskUpdateConnection: TaskUpdateConnection | null = null;
  let selectionTaskOwner: string | null = null;
  let actionTaskOwner: string | null = null;
  let syncStatusInitialized = false;
  let handledSyncSuccessId: string | null = null;
  let handledSyncFailureId: string | null = null;
  let manualSyncRunId: string | null = null;
  const selectionOwnership = new SelectionOwnership();
  const detailCache = new BoundedCache<string, AssetDetail>(detailCacheSize);
  const detailRequest = new LatestRequest();
  const selectionRequest = new LatestRequest();
  const selectAllRequest = new LatestRequest();
  const viewerActionRequest = new LatestRequest();
  const actionPlanRequest = new LatestRequest();
  const selectionTaskPoller = new CoalescedPoller(pollSelectionTask, () => taskFallbackPollMs);
  const actionTaskPoller = new CoalescedPoller(pollActionTask, () => taskFallbackPollMs);
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

  interface InfiniteRefreshSnapshot {
    anchors: InfiniteScrollAnchor[];
    loadedThroughPage: number;
    scrollY: number;
  }

  function markSelectionChanged(abortSelectAll = true): void {
    if (abortSelectAll) selectAllRequest.abort();
    selectionRequest.abort();
    selectionResolution = null;
    selectionLoading = false;
    selectionOwnership.changed();
  }

  function selectionReadIsCurrent(owner: string, selectionId: string | null): boolean {
    return selectionOwnership.owns(owner) && selection.selectionId === selectionId;
  }

  function registerSelectionTask(taskId: string, owner: string): void {
    selectionTaskOwner = owner;
    selectionSyncing = true;
    localStorage.setItem(selectionSyncTaskStorageKey, taskId);
    localStorage.setItem(selectionSyncOwnerStorageKey, owner);
    if (!taskUpdateConnection?.connected) startSelectionTaskPolling();
  }

  function clearSelectionTaskTracking(): void {
    selectionTaskOwner = null;
    localStorage.removeItem(selectionSyncTaskStorageKey);
    localStorage.removeItem(selectionSyncOwnerStorageKey);
  }

  function registerActionTask(taskId: string, owner: string): void {
    actionTaskOwner = owner;
    actionBusy = true;
    localStorage.setItem(actionTaskStorageKey, taskId);
    localStorage.setItem(actionTaskOwnerStorageKey, owner);
    if (!taskUpdateConnection?.connected) startActionTaskPolling();
  }

  function clearActionTaskTracking(): void {
    actionTaskOwner = null;
    localStorage.removeItem(actionTaskStorageKey);
    localStorage.removeItem(actionTaskOwnerStorageKey);
  }

  function rememberActionTask(task: AssetTaskStatus): void {
    actionTaskHistory = [task, ...actionTaskHistory.filter((item) => item.id !== task.id)].slice(0, 10);
  }

  function stopSelectionTaskPolling(): void {
    selectionTaskPoller.stop();
  }

  function stopActionTaskPolling(): void {
    actionTaskPoller.stop();
  }

  function startSelectionTaskPolling(): void {
    if (taskUpdateConnection?.connected && selectionTask !== null) return;
    selectionTaskPoller.start();
  }

  function startActionTaskPolling(): void {
    if (taskUpdateConnection?.connected && actionTask !== null) return;
    actionTaskPoller.start();
  }

  function handleTaskConnectionChange(connected: boolean): void {
    if (connected) {
      if (selectionTask !== null) stopSelectionTaskPolling();
      if (actionTask !== null) stopActionTaskPolling();
      return;
    }
    if (
      (selectionTask && !isTaskTerminal(selectionTask.status))
      || localStorage.getItem(selectionSyncTaskStorageKey)
    ) startSelectionTaskPolling();
    if (
      (actionTask && !isTaskTerminal(actionTask.status))
      || localStorage.getItem(actionTaskStorageKey)
    ) startActionTaskPolling();
  }

  function handleTaskUpdate(task: AssetTaskStatus): void {
    if (task.task_type === 'asset_action') rememberActionTask(task);
    if (task.task_type === 'asset_sync') {
      void syncStatusPoller.refresh();
      return;
    }

    const trackedTaskIds = new Set([
      selectionTask?.id,
      actionTask?.id,
      localStorage.getItem(selectionSyncTaskStorageKey),
      localStorage.getItem(actionTaskStorageKey),
    ].filter((id): id is string => id !== null));
    if (!trackedTaskIds.has(task.id)) return;

    if (task.task_type === 'asset_selection_sync') {
      void applySelectionTaskStatus(task);
    } else if (task.task_type === 'asset_action') {
      void applyActionTaskStatus(task);
    }
  }

  function startTaskUpdates(): void {
    taskUpdateConnection ??= new TaskUpdateConnection(
      (onstatus, onclose) => openTaskUpdates(onstatus, undefined, onclose),
      handleTaskUpdate,
      handleTaskConnectionChange,
    );
    taskUpdateConnection.start();
  }

  const matchingTagIds = $derived(new Set(searchedTagIds(expression)));
  const hasSearch = $derived(expression.children.length > 0);
  const selectedCount = $derived(selectedAssetCount(selection, results?.total ?? 0));
  const visibleSelectedIds = $derived(new Set(
    results?.items
      .filter((asset) => isAssetSelected(selection, asset.id))
      .map((asset) => asset.id) ?? [],
  ));
  const stackPrimaryLabel = $derived.by(() => {
    if (!stackPrimaryAssetId) return null;
    return results?.items.find((asset) => asset.id === stackPrimaryAssetId)?.original_file_name
      ?? `Asset ${stackPrimaryAssetId.slice(0, 8)}`;
  });

  function invalidateActionPlan(): void {
    const wasPlanning = actionPlanRequest.active;
    actionPlanRequest.abort();
    actionPlan = null;
    actionTargetIds = [];
    if (wasPlanning) actionBusy = false;
  }

  function invalidateViewerActionPlan(): void {
    if (actionContext !== 'viewer') return;
    invalidateActionPlan();
    actionError = null;
  }

  function reconcileStackPrimary(changedAssetIds: string[] = []): void {
    if (
      stackPrimaryAssetId
      && changedAssetIds.includes(stackPrimaryAssetId)
      && !isAssetSelected(selection, stackPrimaryAssetId)
    ) {
      stackPrimaryAssetId = null;
    }
    if (stackPrimaryAssetId) return;
    stackPrimaryAssetId = results?.items.find((asset) => isAssetSelected(selection, asset.id))?.id
      ?? null;
  }

  function chooseStackPrimary(assetId: string): void {
    if (!isAssetSelected(selection, assetId)) return;
    stackPrimaryAssetId = assetId;
    invalidateActionPlan();
  }

  async function loadRelationOptions(): Promise<void> {
    const [albumResult, tagResult] = await Promise.allSettled([
      getAlbumOptions(),
      getTagOptions(),
    ]);
    albums = albumResult.status === 'fulfilled' ? albumResult.value : [];
    tags = tagResult.status === 'fulfilled' ? tagResult.value : [];
  }

  async function loadAssets(allowSelectionRecovery = true): Promise<boolean> {
    const generation = ++assetLoadGeneration;
    const selectionOwner = selectionOwnership.current();
    const selectionId = selection.selectionId;
    infiniteLoading = false;
    searchController?.abort();
    const controller = new AbortController();
    searchController = controller;
    loading = true;
    error = null;
    try {
      const next = await searchAssets(
        expression,
        page,
        pageSize,
        sort,
        controller.signal,
        selectionId,
      );
      if (generation !== assetLoadGeneration || controller.signal.aborted) return false;
      if (next.pages > 0 && page > next.pages) {
        page = next.pages;
        return await loadAssets(allowSelectionRecovery);
      }
      results = next;
      if (
        next.selection
        && selectionId !== null
        && next.selection.id === selectionId
        && selectionReadIsCurrent(selectionOwner, selectionId)
        && (selection.selectionRevision === null || next.selection.revision >= selection.selectionRevision)
      ) {
        selection = setServerSelection(
          selection,
          next.selection.id,
          next.selection.revision,
          next.selection.selected_count,
          next.selection.selected_ids,
        );
      }
      return true;
    } catch (requestError) {
      if (requestError instanceof Error && requestError.name === 'AbortError') return false;
      if (
        allowSelectionRecovery
        && generation === assetLoadGeneration
        && selectionId !== null
        && selectionReadIsCurrent(selectionOwner, selectionId)
        && isAssetSelectionUnavailableError(requestError)
      ) {
        selectionSyncError = expiredSelectionMessage;
        clearSelection();
        return await loadAssets(false);
      }
      if (generation === assetLoadGeneration) {
        error = requestErrorMessage(requestError, 'Asset search failed.');
      }
      return false;
    } finally {
      if (generation === assetLoadGeneration) {
        if (searchController === controller) searchController = null;
        loading = false;
      }
    }
  }

  function captureInfiniteRefreshSnapshot(): InfiniteRefreshSnapshot {
    const cards = Array.from(
      document.querySelectorAll<HTMLElement>('.asset-grid .asset-card[data-asset-id]'),
    );
    const firstRelevantIndex = cards.findIndex((card) => card.getBoundingClientRect().bottom > 0);
    const anchorLimit = Math.max(pageSize, 24);
    const relevantCards = firstRelevantIndex >= 0
      ? cards.slice(firstRelevantIndex, firstRelevantIndex + anchorLimit)
      : [];
    return {
      anchors: relevantCards.flatMap((card) => {
        const id = card.dataset.assetId;
        return id ? [{ id, top: card.getBoundingClientRect().top }] : [];
      }),
      loadedThroughPage: Math.max(1, page),
      scrollY: window.scrollY,
    };
  }

  async function restoreInfiniteScrollPosition(snapshot: InfiniteRefreshSnapshot): Promise<void> {
    await tick();
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    const loadedIds = new Set(results?.items.map((asset) => asset.id) ?? []);
    const anchor = firstSurvivingScrollAnchor(snapshot.anchors, loadedIds);
    if (anchor) {
      const card = Array.from(
        document.querySelectorAll<HTMLElement>('.asset-grid .asset-card[data-asset-id]'),
      ).find((candidate) => candidate.dataset.assetId === anchor.id);
      if (card) {
        window.scrollBy({ top: card.getBoundingClientRect().top - anchor.top, behavior: 'auto' });
        return;
      }
    }
    const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    window.scrollTo({ top: Math.min(snapshot.scrollY, maxScroll), behavior: 'auto' });
  }

  async function loadInfiniteWindow(
    loadedThroughPage: number,
    allowSelectionRecovery = true,
  ): Promise<boolean> {
    const generation = ++assetLoadGeneration;
    const selectionOwner = selectionOwnership.current();
    const selectionId = selection.selectionId;
    infiniteLoading = false;
    searchController?.abort();
    const controller = new AbortController();
    searchController = controller;
    loading = true;
    error = null;
    try {
      const first = await searchAssets(
        expression,
        1,
        pageSize,
        sort,
        controller.signal,
        selectionId,
      );
      if (generation !== assetLoadGeneration || controller.signal.aborted) return false;
      const pageNumbers = infiniteWindowPages(loadedThroughPage, first.pages);
      const loadedPages: AssetSearchResponse[] = [first];
      const remainingPages = pageNumbers.slice(1);
      for (let offset = 0; offset < remainingPages.length; offset += 4) {
        const batch = remainingPages.slice(offset, offset + 4);
        const responses = await Promise.all(batch.map((pageNumber) => searchAssets(
          expression,
          pageNumber,
          pageSize,
          sort,
          controller.signal,
          selectionId,
        )));
        if (generation !== assetLoadGeneration || controller.signal.aborted) return false;
        loadedPages.push(...responses);
      }
      const lastPage = pageNumbers.at(-1) ?? 1;
      page = lastPage;
      results = {
        ...first,
        page: lastPage,
        items: mergeInfiniteWindowItems(loadedPages.map((response) => response.items)),
      };
      if (selectionId !== null && selectionReadIsCurrent(selectionOwner, selectionId)) {
        const pageSelections = loadedPages.map((response) => response.selection);
        if (canMergeServerSelectionPages(selection, pageSelections)) {
          selection = mergeServerSelectionPages(selection, pageSelections);
        } else if (pageSelections.some(Boolean)) {
          await refreshServerPageMembership(results.items.map((asset) => asset.id), controller.signal);
        }
      }
      if (generation !== assetLoadGeneration || controller.signal.aborted) return false;
      return true;
    } catch (requestError) {
      if (requestError instanceof Error && requestError.name === 'AbortError') return false;
      if (
        allowSelectionRecovery
        && generation === assetLoadGeneration
        && selectionId !== null
        && selectionReadIsCurrent(selectionOwner, selectionId)
        && isAssetSelectionUnavailableError(requestError)
      ) {
        selectionSyncError = expiredSelectionMessage;
        clearSelection();
        return await loadInfiniteWindow(loadedThroughPage, false);
      }
      if (generation === assetLoadGeneration) {
        error = requestErrorMessage(requestError, 'Asset search failed.');
      }
      return false;
    } finally {
      if (generation === assetLoadGeneration) {
        if (searchController === controller) searchController = null;
        loading = false;
      }
    }
  }

  async function refreshAssetsAfterMutation(): Promise<void> {
    if (listMode !== 'infinite' || !results) {
      await loadAssets();
      return;
    }
    const snapshot = captureInfiniteRefreshSnapshot();
    if (await loadInfiniteWindow(snapshot.loadedThroughPage)) {
      await restoreInfiniteScrollPosition(snapshot);
    }
  }

  const infiniteHasMore = $derived(
    listMode === 'infinite' && Boolean(results) && page < (results?.pages ?? 0),
  );

  async function loadNextInfinitePage(allowSelectionRecovery = true): Promise<boolean> {
    if (!infiniteHasMore || loading || infiniteLoading || !results) return false;
    const generation = assetLoadGeneration;
    const selectionOwner = selectionOwnership.current();
    const selectionId = selection.selectionId;
    const nextPage = page + 1;
    searchController?.abort();
    const controller = new AbortController();
    searchController = controller;
    infiniteLoading = true;
    try {
      const next = await searchAssets(
        expression,
        nextPage,
        pageSize,
        sort,
        controller.signal,
        selectionId,
      );
      if (
        generation !== assetLoadGeneration
        || controller.signal.aborted
        || listMode !== 'infinite'
        || !results
      ) return false;
      const knownIds = new Set(results.items.map((asset) => asset.id));
      const appendedItems: AssetSummary[] = [];
      for (const asset of next.items) {
        if (knownIds.has(asset.id)) continue;
        knownIds.add(asset.id);
        appendedItems.push(asset);
      }
      page = next.page;
      results = {
        ...results,
        page: next.page,
        pages: next.pages,
        total: next.total,
        items: [...results.items, ...appendedItems],
      };
      if (
        next.selection
        && selectionId !== null
        && next.selection.id === selectionId
        && selectionReadIsCurrent(selectionOwner, selectionId)
      ) {
        const merged = mergeServerSelectionPage(selection, next.selection);
        if (merged === selection) {
          await refreshServerPageMembership(next.items.map((asset) => asset.id), controller.signal);
        } else {
          selection = merged;
        }
      }
      return appendedItems.length > 0;
    } catch (requestError) {
      if (requestError instanceof Error && requestError.name === 'AbortError') return false;
      if (
        allowSelectionRecovery
        && generation === assetLoadGeneration
        && selectionId !== null
        && selectionReadIsCurrent(selectionOwner, selectionId)
        && isAssetSelectionUnavailableError(requestError)
      ) {
        selectionSyncError = expiredSelectionMessage;
        clearSelection();
        if (searchController === controller) searchController = null;
        infiniteLoading = false;
        return await loadNextInfinitePage(false);
      }
      if (generation === assetLoadGeneration) {
        error = requestErrorMessage(requestError, 'Asset search failed.');
      }
      return false;
    } finally {
      if (generation === assetLoadGeneration) {
        if (searchController === controller) searchController = null;
        infiniteLoading = false;
      }
    }
  }

  async function requestNextViewerIndex(): Promise<number | null> {
    if (!results) return null;
    if (listMode === 'infinite') {
      const previousLength = results.items.length;
      if (await loadNextInfinitePage()) return previousLength;
      return null;
    }
    if (page >= results.pages) return null;
    const previousPage = page;
    viewerSelectedAsset = viewerIndex !== null ? results.items[viewerIndex] ?? null : null;
    page += 1;
    if (!await loadAssets()) {
      page = previousPage;
      viewerSelectedAsset = null;
      return null;
    }
    return results?.items.length ? 0 : null;
  }

  async function requestPreviousViewerIndex(): Promise<number | null> {
    if (!results || listMode !== 'paged' || page <= 1) return null;
    const previousPage = page;
    viewerSelectedAsset = viewerIndex !== null ? results.items[viewerIndex] ?? null : null;
    page -= 1;
    if (!await loadAssets()) {
      page = previousPage;
      viewerSelectedAsset = null;
      return null;
    }
    return results?.items.length ? results.items.length - 1 : null;
  }

  function changeListMode(nextMode: AssetListMode): void {
    if (nextMode === listMode) return;
    const previousMode = listMode;
    const previousPage = page;
    listMode = nextMode;
    localStorage.setItem(ASSET_LIST_MODE_STORAGE_KEY, nextMode);
    page = 1;
    closeViewer();
    selectionAnchorIndex = null;
    void loadAssets().then((loaded) => {
      if (loaded) return;
      listMode = previousMode;
      page = previousPage;
      localStorage.setItem(ASSET_LIST_MODE_STORAGE_KEY, previousMode);
    });
  }

  function changeLayoutMode(nextMode: AssetLayoutMode): void {
    layoutMode = nextMode;
    localStorage.setItem('immich-companion:asset-layout', nextMode);
  }

  $effect(() => {
    if (loading || !infiniteSentinel || !infiniteHasMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) void loadNextInfinitePage();
      },
      { rootMargin: '640px 0px' },
    );
    observer.observe(infiniteSentinel);
    return () => observer.disconnect();
  });

  async function refreshServerPageMembership(
    assetIds: string[],
    signal?: AbortSignal,
  ): Promise<void> {
    if (!selection.selectionId || assetIds.length === 0) return;
    const selectionId = selection.selectionId;
    const owner = selectionOwnership.current();
    try {
      const membership = await getAssetSelectionMembership(selectionId, assetIds, signal);
      if (signal?.aborted || !selectionReadIsCurrent(owner, selectionId)) return;
      selection = patchServerSelectionMembership(selection, assetIds, membership);
    } catch (requestError) {
      if (signal?.aborted || isAbortError(requestError)) return;
      if (!selectionReadIsCurrent(owner, selectionId)) return;
      if (isAssetSelectionUnavailableError(requestError)) {
        selectionSyncError = expiredSelectionMessage;
        clearSelection();
        return;
      }
      selectionSyncError = requestErrorMessage(
        requestError,
        'Selection membership could not be loaded.',
      );
    }
  }

  async function persistServerPageMembership(assetIds: string[]): Promise<void> {
    if (!selection.selectionId || selection.selectionRevision === null) return;
    const selectionId = selection.selectionId;
    const selected = assetIds.filter((id) => selection.selectedIds.has(id));
    const unselected = assetIds.filter((id) => !selection.selectedIds.has(id));
    try {
      for (const [ids, value] of [[selected, true], [unselected, false]] as const) {
        if (!ids.length || selection.selectionRevision === null) continue;
        const updated = await updateAssetSelectionMembers(
          selectionId,
          ids,
          value,
          selection.selectionRevision,
        );
        if (selection.selectionId !== selectionId) return;
        selection = {
          ...selection,
          selectionRevision: updated.revision,
          serverSelectedCount: updated.selected_count,
        };
      }
    } catch (requestError) {
      if (selection.selectionId !== selectionId) return;
      if (isAssetSelectionUnavailableError(requestError)) {
        selectionSyncError = expiredSelectionMessage;
        clearSelection();
        return;
      }
      selectionSyncError = requestErrorMessage(requestError, 'Selection update failed.');
      await refreshServerPageMembership(assetIds);
    }
  }

  async function loadDetail(index: number): Promise<void> {
    const asset = results?.items[index];
    if (!asset) return;
    detailRequest.abort();
    const cached = detailCache.get(asset.id);
    if (cached) {
      detail = cached;
      detailError = null;
      detailLoading = false;
      return;
    }

    detail = null;
    detailError = null;
    detailLoading = true;
    const result = await detailRequest.run((signal) => getAssetDetail(asset.id, signal));
    if (!detailRequest.isCurrent(result.version)) return;

    if (result.status === 'success') {
      detailCache.set(asset.id, result.value);
      detail = result.value;
    } else if (result.status === 'error') {
      detailError = requestErrorMessage(result.error, 'Image details failed to load.');
    }
    detailLoading = false;
  }

  async function refreshDetail(assetId: string): Promise<void> {
    detailError = null;
    detailLoading = true;
    const result = await detailRequest.run((signal) => getAssetDetail(assetId, signal));
    if (!detailRequest.isCurrent(result.version)) return;

    if (result.status === 'success') {
      detailCache.set(assetId, result.value);
      detail = result.value;
    } else if (result.status === 'error') {
      detailError = requestErrorMessage(result.error, 'Image details failed to load.');
    }
    detailLoading = false;
  }

  async function syncViewerAsset(assetId: string): Promise<void> {
    viewerSyncing = true;
    viewerSyncError = null;
    detailRequest.abort();
    detailLoading = false;
    try {
      const syncedDetail = await synchronizeAsset(assetId);
      detailCache.set(assetId, syncedDetail);
      if (viewerIndex !== null && results?.items[viewerIndex]?.id === assetId) {
        detail = syncedDetail;
      }
      const refreshedAsset = await matchAssetSearch(assetId, expression);
      if (!refreshedAsset) {
        closeViewer();
        await refreshAssetsAfterMutation();
        return;
      }
      const refreshedIndex = patchResultAsset(refreshedAsset);
      if (refreshedIndex >= 0 && viewerIndex !== null) viewerIndex = refreshedIndex;
      await loadRelationOptions();
    } catch (requestError) {
      viewerSyncError = requestErrorMessage(requestError, 'Asset sync failed.');
    } finally {
      viewerSyncing = false;
    }
  }

  async function syncSelectedAssets(): Promise<void> {
    const owner = selectionOwnership.current();
    selectionSyncing = true;
    selectionSyncError = null;
    actionError = null;
    try {
      const result = await synchronizeAssetSelection(buildSelectionRequest(selection, expression));
      if (result.task_id) {
        registerSelectionTask(result.task_id, owner);
        await applySelectionTaskStatus(await getTaskStatus(result.task_id));
      } else {
        actionCompletionMessage = `${result.synced} assets synchronized.`;
        detailCache.clear();
        if (selectionOwnership.owns(owner)) clearSelection();
        await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
      }
    } catch (requestError) {
      if (isAssetSelectionUnavailableError(requestError)) {
        selectionSyncError = expiredSelectionMessage;
        if (selectionOwnership.owns(owner)) clearSelection();
      } else {
        selectionSyncError = requestErrorMessage(requestError, 'Selected asset sync failed.');
      }
    } finally {
      selectionSyncing = Boolean(
        (selectionTask && !isTaskTerminal(selectionTask.status))
        || localStorage.getItem(selectionSyncTaskStorageKey),
      );
    }
  }

  async function applySelectionTaskStatus(next: AssetTaskStatus): Promise<void> {
    if (!shouldApplyTaskStatus(selectionTask, next)) return;
    const terminal = isTaskTerminal(next.status);
    const terminalAlreadyHandled = terminal
      && selectionTask?.id === next.id
      && isTaskTerminal(selectionTask.status);

    selectionTask = next;
    selectionSyncing = !terminal;
    localStorage.setItem(selectionSyncTaskStorageKey, next.id);

    if (!terminal) {
      if (taskUpdateConnection?.connected) stopSelectionTaskPolling();
      else startSelectionTaskPolling();
      return;
    }

    const owner = selectionTaskOwner ?? localStorage.getItem(selectionSyncOwnerStorageKey);
    stopSelectionTaskPolling();
    clearSelectionTaskTracking();
    if (terminalAlreadyHandled) return;

    const summary = next.result?.summary;
    const failedIds = summary?.failed_ids ?? [];
    if (next.status === 'failed' || next.status === 'cancelled' || failedIds.length > 0) {
      selectionTaskErrorOpen = true;
      selectionSyncError = next.error?.message
        ?? (next.status === 'cancelled'
          ? 'Selected asset synchronization was cancelled.'
          : 'Some selected assets could not be synchronized.');
      return;
    }

    actionCompletionMessage = `${summary?.synced ?? next.counters.synced ?? 0} assets synchronized.`;
    detailCache.clear();
    if (selectionOwnership.owns(owner)) clearSelection();
    await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
  }

  async function pollSelectionTask(signal: AbortSignal): Promise<void> {
    const taskId = selectionTask?.id ?? localStorage.getItem(selectionSyncTaskStorageKey);
    if (!taskId) {
      stopSelectionTaskPolling();
      return;
    }
    try {
      await applySelectionTaskStatus(await getTaskStatus(taskId, signal));
    } catch (requestError) {
      if (signal.aborted || isAbortError(requestError)) return;
      if (isTaskUnavailableError(requestError)) {
        stopSelectionTaskPolling();
        clearSelectionTaskTracking();
        selectionTask = null;
        selectionSyncing = false;
        selectionSyncError = 'The previously tracked selected-asset sync is no longer available.';
        return;
      }
      selectionSyncError = requestErrorMessage(
        requestError,
        'Selected asset sync status is unavailable.',
      );
    }
  }

  function retryFailedSelection(ids: string[]): void {
    selection = setExplicitAssetIds(ids);
    markSelectionChanged();
    selectionTaskErrorOpen = false;
    selectionSyncError = null;
    invalidateActionPlan();
    void refreshSelection();
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
    closeViewer();
    clearSelection();
    void loadAssets();
  }

  function changePage(nextPage: number): void {
    if (nextPage === page) return;
    const previousPage = page;
    page = nextPage;
    closeViewer();
    selectionAnchorIndex = null;
    void loadAssets().then((loaded) => {
      if (!loaded) {
        page = previousPage;
        return;
      }
      document.querySelector('.asset-workspace')?.scrollIntoView({ behavior: 'smooth' });
    });
  }

  function changePageSize(nextPageSize: number): void {
    if (nextPageSize === pageSize) return;
    const previousPageSize = pageSize;
    const previousPage = page;
    pageSize = nextPageSize;
    page = 1;
    closeViewer();
    selectionAnchorIndex = null;
    void loadAssets().then((loaded) => {
      if (!loaded) {
        pageSize = previousPageSize;
        page = previousPage;
        return;
      }
      document.querySelector('.asset-workspace')?.scrollIntoView({ behavior: 'smooth' });
    });
  }

  function openViewer(index: number): void {
    invalidateViewerActionPlan();
    viewerSelectedAsset = null;
    viewerIndex = index;
    const asset = results?.items[index];
    void loadDetail(index);
    if (asset) void resolveViewerActionState(asset.id);
  }

  function navigateViewer(index: number): void {
    invalidateViewerActionPlan();
    viewerSelectedAsset = null;
    viewerIndex = index;
    const asset = results?.items[index];
    void loadDetail(index);
    if (asset) void resolveViewerActionState(asset.id);
  }

  async function selectViewerComparisonAsset(assetId: string): Promise<void> {
    invalidateViewerActionPlan();
    const resultIndex = results?.items.findIndex((asset) => asset.id === assetId) ?? -1;
    if (resultIndex >= 0) {
      navigateViewer(resultIndex);
      return;
    }

    detail = null;
    detailError = null;
    detailLoading = true;
    const result = await detailRequest.run((signal) => Promise.all([
      getAssetSummary(assetId, signal),
      getAssetDetail(assetId, signal),
    ]));
    if (!detailRequest.isCurrent(result.version) || viewerIndex === null) return;

    if (result.status === 'success') {
      const [asset, loadedDetail] = result.value;
      if (asset) {
        viewerSelectedAsset = asset;
        detailCache.set(assetId, loadedDetail);
        detail = loadedDetail;
        void resolveViewerActionState(assetId, true);
      }
    } else if (result.status === 'error') {
      detailError = requestErrorMessage(
        result.error,
        'Selected stack member details could not be loaded.',
      );
    }
    detailLoading = false;
  }

  function toggleSelection(assetId: string): void {
    selection = toggleAssetSelection(selection, assetId);
    markSelectionChanged();
    reconcileStackPrimary([assetId]);
    invalidateActionPlan();
    void persistServerPageMembership([assetId]);
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
    const affectedIds = shiftKey && selectionAnchorIndex !== null
      ? items
        .slice(Math.min(selectionAnchorIndex, index), Math.max(selectionAnchorIndex, index) + 1)
        .map((item) => item.id)
      : [asset.id];
    markSelectionChanged();
    reconcileStackPrimary(affectedIds);
    selectionAnchorIndex = index;
    invalidateActionPlan();
    void persistServerPageMembership(affectedIds);
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
    dragChangedIds = new Set([asset.id]);
    selection = setSelectionRange(
      selection,
      items.map((item) => item.id),
      index,
      index,
      dragSelectionValue,
    );
    markSelectionChanged();
    reconcileStackPrimary([asset.id]);
    invalidateActionPlan();
  }

  function continueDragSelection(index: number, event: PointerEvent): void {
    if (!dragSelecting || event.pointerType !== 'mouse') return;
    if ((event.buttons & 1) === 0) {
      finishDragSelection();
      return;
    }
    if (dragLastIndex === null || dragLastIndex === index) return;
    const ids = results?.items.map((item) => item.id) ?? [];
    const changedIds = ids.slice(Math.min(dragLastIndex, index), Math.max(dragLastIndex, index) + 1);
    selection = setSelectionRange(
      selection,
      ids,
      dragLastIndex,
      index,
      dragSelectionValue,
    );
    changedIds.forEach((assetId) => dragChangedIds.add(assetId));
    markSelectionChanged();
    reconcileStackPrimary(changedIds);
    dragLastIndex = index;
    invalidateActionPlan();
  }

  function finishDragSelection(): void {
    if (!dragSelecting) return;
    dragSelecting = false;
    selectionAnchorIndex = dragLastIndex;
    dragLastIndex = null;
    const changedIds = [...dragChangedIds];
    dragChangedIds.clear();
    void persistServerPageMembership(changedIds);
    void refreshSelection();
  }

  function clearSelection(): void {
    selection = createAssetSelectionState();
    markSelectionChanged();
    stackPrimaryAssetId = null;
    selectionResolution = null;
    invalidateActionPlan();
    selectionRequest.abort();
    selectionLoading = false;
    selectionAnchorIndex = null;
    dragSelecting = false;
    dragLastIndex = null;
    dragChangedIds.clear();
  }

  function selectPage(): void {
    selection = selectCurrentPage(
      selection,
      results?.items.map((asset) => asset.id) ?? [],
    );
    markSelectionChanged();
    reconcileStackPrimary();
    invalidateActionPlan();
    void persistServerPageMembership(results?.items.map((asset) => asset.id) ?? []);
    void refreshSelection();
  }

  async function selectEveryMatch(): Promise<void> {
    const owner = selectionOwnership.current();
    const expressionSnapshot = copySearchGroup(expression);
    selectionRequest.abort();
    selectionResolution = null;
    selectionLoading = true;
    actionError = null;
    const result = await selectAllRequest.run(async (signal) => {
      const serverSelection = await createAssetSelection(signal);
      return await selectAllAssetSelection(serverSelection.id, expressionSnapshot, signal);
    });
    if (!selectAllRequest.isCurrent(result.version) || !selectionOwnership.owns(owner)) return;

    if (result.status === 'success') {
      const filledSelection = result.value;
      selection = setServerSelection(
        selection,
        filledSelection.id,
        filledSelection.revision,
        filledSelection.selected_count,
        results?.items.map((asset) => asset.id) ?? [],
      );
      markSelectionChanged(false);
      stackPrimaryAssetId = results?.items[0]?.id ?? null;
      invalidateActionPlan();
      selectionLoading = false;
      await refreshSelection();
      return;
    }
    if (result.status === 'error') {
      actionError = requestErrorMessage(result.error, 'Could not select all matching assets.');
    }
    selectionLoading = false;
  }

  function invertPage(): void {
    selection = invertCurrentPage(
      selection,
      results?.items.map((asset) => asset.id) ?? [],
    );
    markSelectionChanged();
    reconcileStackPrimary(results?.items.map((asset) => asset.id) ?? []);
    invalidateActionPlan();
    void persistServerPageMembership(results?.items.map((asset) => asset.id));
    void refreshSelection();
  }

  async function refreshSelection(): Promise<void> {
    if (selectedAssetCount(selection, results?.total ?? 0) === 0) {
      selectionRequest.abort();
      selectionResolution = null;
      selectionLoading = false;
      return;
    }

    selectionLoading = true;
    actionError = null;
    const owner = selectionOwnership.current();
    const result = await selectionRequest.run((signal) => resolveAssetSelection(
      buildSelectionRequest(selection, expression),
      signal,
    ));
    if (!selectionRequest.isCurrent(result.version)) return;

    if (result.status === 'success') selectionResolution = result.value;
    else if (result.status === 'error') {
      if (isAssetSelectionUnavailableError(result.error)) {
        selectionSyncError = expiredSelectionMessage;
        if (selectionOwnership.owns(owner)) clearSelection();
      } else {
        actionError = requestErrorMessage(result.error, 'Selection resolution failed.');
      }
    }
    selectionLoading = false;
  }

  async function createActionPlan(
    request: AssetSelectionRequest,
    context: 'selection' | 'viewer',
    action: AssetActionIntent,
    relationIds: string[] = [],
    stackResolution?: StackResolution,
  ): Promise<void> {
    invalidateActionPlan();
    actionBusy = true;
    actionError = null;
    actionMessage = null;
    actionContext = context;
    actionTargetIds = request.mode === 'explicit' ? [...request.ids] : [];
    const owner = context === 'selection' ? selectionOwnership.current() : null;
    const primaryAssetId = action === 'stack'
      ? stackPrimaryAssetId ?? request.ids[0] ?? null
      : null;
    if (action === 'stack' && primaryAssetId === null) {
      actionError = 'Choose a selected image as the stack main before reviewing this action.';
      actionBusy = false;
      return;
    }

    const result = await actionPlanRequest.run((signal) => planAssetAction(
      request,
      action,
      relationIds,
      stackResolution,
      primaryAssetId ?? undefined,
      signal,
    ));
    if (!actionPlanRequest.isCurrent(result.version)) return;

    if (result.status === 'success') actionPlan = result.value;
    else if (result.status === 'error') {
      if (owner && isAssetSelectionUnavailableError(result.error)) {
        actionError = expiredSelectionMessage;
        if (selectionOwnership.owns(owner)) clearSelection();
      } else {
        actionError = requestErrorMessage(result.error, 'Action planning failed.');
      }
    }
    actionBusy = false;
  }

  function previewSelectionAction(
    action: AssetActionIntent,
    relationIds: string[] = [],
    stackResolution?: StackResolution,
  ): void {
    void createActionPlan(
      buildSelectionRequest(selection, expression),
      'selection',
      action,
      relationIds,
      stackResolution,
    );
  }

  async function confirmStackAction(stackResolution: StackResolution): Promise<void> {
    if (!actionPlan) return;
    const request = buildSelectionRequest(selection, expression);
    const confirmedTargetIds = [...actionTargetIds];
    const owner = selectionOwnership.current();
    actionBusy = true;
    actionError = null;
    try {
      const reviewedPlan = await planAssetAction(
        request,
        'stack',
        [],
        stackResolution,
        actionPlan.stack_primary_asset_id ?? undefined,
      );
      const started = await executeAssetActionTask(reviewedPlan.id);
      registerActionTask(started.task_id, owner);
      await applyActionTaskStatus(await getTaskStatus(started.task_id));
      actionPlan = null;
      actionTargetIds = confirmedTargetIds;
    } catch (requestError) {
      if (isAssetSelectionUnavailableError(requestError)) {
        actionError = expiredSelectionMessage;
        if (selectionOwnership.owns(owner)) clearSelection();
      } else {
        actionError = requestErrorMessage(requestError, 'Stack action execution failed.');
      }
    } finally {
      if (!actionTask || isTaskTerminal(actionTask.status)) actionBusy = false;
    }
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
      await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
    } else if (!confirmedTargetId) {
      closeViewer();
      await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
    } else {
      const affectedIds = [...new Set([
        ...result.applied_ids,
        ...result.failed_ids,
        confirmedTargetId,
      ])];
      await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
      const refreshedAssets = await Promise.all(
        affectedIds.map(async (assetId) => {
          detailCache.delete(assetId);
          return [assetId, await matchAssetSearch(assetId, expression)] as const;
        }),
      );
      for (const [, refreshed] of refreshedAssets) {
        if (refreshed) patchResultAsset(refreshed);
      }
      const refreshedAsset = refreshedAssets.find(([assetId]) => assetId === confirmedTargetId)?.[1] ?? null;
      if (!refreshedAsset) {
        closeViewer();
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
    actionTargetIds = [];
  }

  async function createAndExecuteRelationAction(
    request: AssetSelectionRequest,
    context: 'selection' | 'viewer',
    action: Extract<AssetActionIntent, 'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'>,
    relationIds: string[],
  ): Promise<void> {
    invalidateActionPlan();
    actionBusy = true;
    actionError = null;
    actionMessage = null;
    actionContext = context;
    actionTargetIds = request.mode === 'explicit' ? [...request.ids] : [];
    const owner = context === 'selection' ? selectionOwnership.current() : null;
    try {
      const plan = await planAssetAction(request, action, relationIds);
      if (context === 'selection') {
        const started = await executeAssetActionTask(plan.id);
        registerActionTask(started.task_id, owner!);
        await applyActionTaskStatus(await getTaskStatus(started.task_id));
      } else {
        const result = await executeAssetAction(plan.id);
        await applyActionResult(result, context, actionTargetIds);
      }
    } catch (requestError) {
      if (owner && isAssetSelectionUnavailableError(requestError)) {
        actionError = expiredSelectionMessage;
        if (selectionOwnership.owns(owner)) clearSelection();
      } else {
        actionError = requestErrorMessage(requestError, 'Relation action failed.');
      }
    } finally {
      if (context !== 'selection' || !actionTask || isTaskTerminal(actionTask.status)) actionBusy = false;
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
    if (
      !force
      && viewerActionAssetId === assetId
      && (viewerActionResolution || viewerActionRequest.active)
    ) return;

    viewerActionAssetId = assetId;
    viewerActionResolution = null;
    viewerActionError = null;
    const result = await viewerActionRequest.run((signal) => resolveAssetSelection(
      buildExplicitAssetSelectionRequest(assetId),
      signal,
    ));
    if (!viewerActionRequest.isCurrent(result.version) || viewerActionAssetId !== assetId) return;

    if (result.status === 'success') viewerActionResolution = result.value;
    else if (result.status === 'error') {
      viewerActionError = requestErrorMessage(
        result.error,
        'Image action state could not be resolved.',
      );
    }
  }

  function closeViewer(): void {
    viewerIndex = null;
    viewerSelectedAsset = null;
    detailRequest.abort();
    detail = null;
    detailLoading = false;
    detailError = null;
    viewerActionRequest.abort();
    viewerActionAssetId = null;
    viewerActionResolution = null;
    viewerActionError = null;
    viewerSyncing = false;
    viewerSyncError = null;
    if (actionContext === 'viewer') invalidateViewerActionPlan();
  }

  async function confirmAction(): Promise<void> {
    if (!actionPlan) return;
    const confirmedContext = actionContext;
    const confirmedTargetIds = [...actionTargetIds];
    const owner = confirmedContext === 'selection' ? selectionOwnership.current() : null;
    actionBusy = true;
    actionError = null;
    try {
      if (confirmedContext === 'selection') {
        const started = await executeAssetActionTask(actionPlan.id);
        registerActionTask(started.task_id, owner!);
        await applyActionTaskStatus(await getTaskStatus(started.task_id));
        actionPlan = null;
      } else {
        const result = await executeAssetAction(actionPlan.id);
        await applyActionResult(result, confirmedContext, confirmedTargetIds);
      }
    } catch (requestError) {
      if (owner && isAssetSelectionUnavailableError(requestError)) {
        actionError = expiredSelectionMessage;
        if (selectionOwnership.owns(owner)) clearSelection();
      } else {
        actionError = requestErrorMessage(requestError, 'Action execution failed.');
      }
    } finally {
      if (confirmedContext !== 'selection' || !actionTask || isTaskTerminal(actionTask.status)) {
        actionBusy = false;
      }
    }
  }

  async function applyActionTaskStatus(next: AssetTaskStatus): Promise<void> {
    if (!shouldApplyTaskStatus(actionTask, next)) return;
    const terminal = isTaskTerminal(next.status);
    const terminalAlreadyHandled = terminal
      && actionTask?.id === next.id
      && isTaskTerminal(actionTask.status);

    actionTask = next;
    actionBusy = !terminal;
    rememberActionTask(next);
    localStorage.setItem(actionTaskStorageKey, next.id);

    if (!terminal) {
      if (taskUpdateConnection?.connected) stopActionTaskPolling();
      else startActionTaskPolling();
      return;
    }

    const owner = actionTaskOwner ?? localStorage.getItem(actionTaskOwnerStorageKey);
    stopActionTaskPolling();
    clearActionTaskTracking();
    if (terminalAlreadyHandled) return;

    const summary = next.result?.summary ?? {};
    detailCache.clear();
    await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
    if (next.status === 'failed' || next.status === 'cancelled') {
      actionError = next.error?.message
        ?? (next.status === 'cancelled' ? 'The bulk action was cancelled.' : 'The bulk action failed.');
      return;
    }

    actionCompletionMessage = `${summary.applied_count ?? 0} changed · ${summary.skipped_count ?? 0} skipped.`;
    if (selectionOwnership.owns(owner)) clearSelection();
  }

  async function pollActionTask(signal: AbortSignal): Promise<void> {
    const taskId = actionTask?.id ?? localStorage.getItem(actionTaskStorageKey);
    if (!taskId) {
      stopActionTaskPolling();
      return;
    }
    try {
      await applyActionTaskStatus(await getTaskStatus(taskId, signal));
    } catch (requestError) {
      if (signal.aborted || isAbortError(requestError)) return;
      if (isTaskUnavailableError(requestError)) {
        stopActionTaskPolling();
        clearActionTaskTracking();
        actionTask = null;
        actionBusy = false;
        actionError = 'The previously tracked bulk action is no longer available.';
        return;
      }
      actionError = requestErrorMessage(requestError, 'Action status is unavailable.');
    }
  }

  async function cancelActionTask(): Promise<void> {
    if (!actionTask || isTaskTerminal(actionTask.status)) return;
    try {
      await applyActionTaskStatus(await cancelTask(actionTask.id));
    } catch (requestError) {
      actionError = requestErrorMessage(requestError, 'Could not cancel the action.');
    }
  }

  async function loadActionTaskHistory(): Promise<void> {
    try {
      const history = await listTasks('asset_action');
      const knownIds = new Set(actionTaskHistory.map((task) => task.id));
      actionTaskHistory = [
        ...actionTaskHistory,
        ...history.filter((task) => !knownIds.has(task.id)),
      ].slice(0, 10);
    } catch {
      // The active task overlay remains usable if task history cannot be loaded.
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
    const failureIsCurrent = status.last_failure !== null
      && (status.last_success === null
        || status.last_failure.created_at > status.last_success.created_at);
    if (failureIsCurrent && status.last_failure) {
      const failure = status.last_failure;
      const label = failure.mode === 'full' ? 'Full' : 'Incremental';
      return `${label} sync failed after ${failure.attempts} attempt${failure.attempts === 1 ? '' : 's'}`
        + (failure.error ? `: ${failure.error}` : '.');
    }
    if (status.last_success) {
      const counters = status.last_success.counters;
      return `Last ${status.last_success.mode} sync · ${counters.assets_seen ?? 0} assets · ${counters.assets_removed ?? 0} removed`;
    }
    return null;
  }

  async function refreshSyncStatus(signal: AbortSignal): Promise<void> {
    try {
      const next = await getAssetSyncStatus(signal);
      const requestedRunId = manualSyncRunId;
      let manualRun: Awaited<ReturnType<typeof getAssetSyncRunStatus>> | null = null;
      if (requestedRunId !== null) {
        try {
          manualRun = await getAssetSyncRunStatus(requestedRunId, signal);
        } catch (requestError) {
          if (signal.aborted || isAbortError(requestError)) return;
          if (isTaskUnavailableError(requestError) && manualSyncRunId === requestedRunId) {
            manualSyncRunId = null;
            syncError = 'The requested synchronization run is no longer available.';
          }
        }
      }

      const nextSuccessId = next.last_success?.id ?? null;
      const nextFailureId = next.last_failure?.id ?? null;
      const failureIsCurrent = next.last_failure !== null
        && (next.last_success === null
          || next.last_failure.created_at > next.last_success.created_at);
      const completedSinceLastCheck = syncStatusInitialized
        && nextSuccessId !== null
        && nextSuccessId !== handledSyncSuccessId;
      const failedSinceLastCheck = syncStatusInitialized
        && nextFailureId !== null
        && nextFailureId !== handledSyncFailureId;
      const manualRunActive = manualRun !== null
        && !['completed', 'failed'].includes(manualRun.status);
      const manualRunCompleted = manualRun !== null
        && manualSyncRunId === manualRun.id
        && manualRun.status === 'completed';
      const manualRunFailed = manualRun !== null
        && manualSyncRunId === manualRun.id
        && manualRun.status === 'failed';

      syncing = next.active !== null || next.pending !== null || manualRunActive;
      syncMessage = next.active || next.pending || failureIsCurrent ? describeSync(next) : null;
      syncProgress = next.active?.progress ?? null;
      if (completedSinceLastCheck || manualRunCompleted) syncError = null;
      if (failedSinceLastCheck && failureIsCurrent && next.last_failure) {
        syncError = next.last_failure.error
          ? `${next.last_failure.mode === 'full' ? 'Full' : 'Incremental'} sync failed after ${next.last_failure.attempts} attempt${next.last_failure.attempts === 1 ? '' : 's'}: ${next.last_failure.error}`
          : 'Synchronization failed after its retry limit.';
      }
      if (manualRunFailed && manualRun) {
        syncError = manualRun.error
          ? `${manualRun.mode === 'full' ? 'Full' : 'Incremental'} sync failed after ${manualRun.attempts} attempt${manualRun.attempts === 1 ? '' : 's'}: ${manualRun.error}`
          : 'The requested synchronization failed after its retry limit.';
        manualSyncRunId = null;
      }
      if (manualRunCompleted && manualRun) {
        const counters = manualRun.counters;
        syncCompletionMessage = `${manualRun.mode === 'full' ? 'Full' : 'Incremental'} sync completed: `
          + `${counters.assets_updated ?? 0} updated, ${counters.assets_created ?? 0} created, `
          + `${counters.assets_removed ?? 0} removed.`;
        manualSyncRunId = null;
      }

      if (!syncStatusInitialized) {
        syncStatusInitialized = true;
        handledSyncSuccessId = nextSuccessId;
        handledSyncFailureId = nextFailureId;
      } else if (completedSinceLastCheck) {
        handledSyncSuccessId = nextSuccessId;
        detailCache.clear();
        await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
      }
      if (manualRunCompleted && !completedSinceLastCheck) {
        detailCache.clear();
        await Promise.all([loadRelationOptions(), refreshAssetsAfterMutation()]);
      }
      if (nextFailureId !== null) handledSyncFailureId = nextFailureId;
    } catch (requestError) {
      if (signal.aborted || isAbortError(requestError)) return;
      if (!syncStatusInitialized) {
        syncMessage = requestErrorMessage(requestError, 'Sync status is unavailable.');
      }
    }
  }

  function syncPollDelay(): number {
    if (document.visibilityState === 'hidden') return hiddenSyncPollMs;
    return syncing || manualSyncRunId !== null ? activeSyncPollMs : idleSyncPollMs;
  }

  const syncStatusPoller = new CoalescedPoller(refreshSyncStatus, syncPollDelay);

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') void syncStatusPoller.refresh();
    else syncStatusPoller.reschedule();
  }

  async function syncAssets(mode: AssetSyncMode = 'incremental'): Promise<void> {
    syncing = true;
    syncStatusPoller.reschedule(activeSyncPollMs);
    syncMessage = mode === 'full' ? 'Queueing full sync…' : 'Queueing incremental sync…';
    syncError = null;
    error = null;
    try {
      const started = await startAssetSync(mode);
      manualSyncRunId = started.id;
      await syncStatusPoller.refresh(true);
    } catch (requestError) {
      manualSyncRunId = null;
      error = requestErrorMessage(requestError, 'Immich sync failed.');
      syncing = false;
      syncStatusPoller.reschedule();
    }
  }

  onMount(() => {
    const savedLayout = localStorage.getItem('immich-companion:asset-layout');
    if (savedLayout === 'normal' || savedLayout === 'condensed') layoutMode = savedLayout;
    listMode = decodeAssetListMode(localStorage.getItem(ASSET_LIST_MODE_STORAGE_KEY));
    selectionTaskOwner = localStorage.getItem(selectionSyncOwnerStorageKey);
    actionTaskOwner = localStorage.getItem(actionTaskOwnerStorageKey);
    const recoveredSelectionTaskId = localStorage.getItem(selectionSyncTaskStorageKey);
    const recoveredActionTaskId = localStorage.getItem(actionTaskStorageKey);
    selectionSyncing = recoveredSelectionTaskId !== null;
    actionBusy = recoveredActionTaskId !== null;
    startTaskUpdates();
    void loadActionTaskHistory();
    const url = new URL(window.location.href);
    const albumId = url.searchParams.get('albumId');
    const tagId = url.searchParams.get('tagId');
    if (albumId || tagId) {
      const filters = createSimpleAssetSearchFilters();
      if (albumId) filters.albumIds = [albumId];
      if (tagId) filters.tagIds = [tagId];
      expression = simpleFiltersToSearchGroup(filters);
    }
    window.addEventListener('pointerup', finishDragSelection);
    window.addEventListener('pointercancel', finishDragSelection);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    void loadRelationOptions();
    void loadAssets();
    syncStatusPoller.start();
    if (recoveredSelectionTaskId) startSelectionTaskPolling();
    if (recoveredActionTaskId) startActionTaskPolling();
    return () => {
      window.removeEventListener('pointerup', finishDragSelection);
      window.removeEventListener('pointercancel', finishDragSelection);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      syncStatusPoller.stop();
      taskUpdateConnection?.stop();
      stopSelectionTaskPolling();
      stopActionTaskPolling();
    };
  });

  onDestroy(() => {
    syncStatusPoller.stop();
    taskUpdateConnection?.stop();
    stopSelectionTaskPolling();
    stopActionTaskPolling();
    searchController?.abort();
    detailRequest.abort();
    selectionRequest.abort();
    selectAllRequest.abort();
    viewerActionRequest.abort();
    actionPlanRequest.abort();
    detailCache.clear();
  });
</script>

<section class="asset-workspace" aria-label="Asset search workspace">
  <AssetSearchToolbar {albums} {tags} disabled={loading} onsearch={applySearch} />

  <AssetResultStatus
    total={results?.total ?? 0}
    shown={results?.items.length ?? 0}
    shownLabel={listMode === 'infinite' ? 'loaded' : 'on this page'}
    selected={selectedCount}
    {syncing}
    {syncMessage}
    {syncProgress}
    onsync={() => void syncAssets('incremental')}
    onfullsync={() => void syncAssets('full')}
  />

  {#if error && results}
    <StatusNotice tone="error" message={error} actionLabel="Retry" onaction={() => void loadAssets()} />
  {/if}

  {#if results}
    <AssetSelectionActions
      {selectedCount}
      matchingTotal={results.total}
      currentPageCount={results.items.length}
      infiniteScroll={listMode === 'infinite'}
      allMatching={selection.mode === 'all_matching'}
      summary={selectionResolution?.summary ?? null}
      {albums}
      {tags}
      plan={actionContext === 'selection' ? actionPlan : null}
      {stackPrimaryLabel}
      busy={selectionLoading || actionBusy}
      error={actionContext === 'selection' ? actionError : null}
      syncBusy={selectionSyncing}
      syncError={selectionSyncError}
      onsync={() => void syncSelectedAssets()}
      onselectpage={selectPage}
      onselectall={selectEveryMatch}
      oninvertpage={invertPage}
      onclear={clearSelection}
      onplan={previewSelectionAction}
      onrelationconfirm={confirmSelectionRelationAction}
      onconfirm={confirmAction}
      oncancel={invalidateActionPlan}
      onstackconfirm={confirmStackAction}
    />
  {/if}

  {#if actionMessage}<p class="action-message" role="status">{actionMessage}</p>{/if}
  {#if actionError && actionContext === 'selection'}
    <p class="action-error" role="alert">Bulk action failed: {actionError}</p>
  {/if}

  {#if loading && !results}
    <AssetLoadingState />
  {:else if error && !results}
    <AssetErrorState message={error} onretry={loadAssets} />
  {:else if results && results.items.length === 0}
    <AssetEmptyState {syncing} showSync={!hasSearch} onsync={() => void syncAssets('incremental')} />
  {:else if results}
    <div class="result-layout-controls">
      <AssetPagination
        page={results.page}
        pages={results.pages}
        total={results.total}
        pageSize={results.page_size}
        disabled={loading}
        onpage={changePage}
        onpagesizechange={changePageSize}
        mode={listMode}
        onmodechange={changeListMode}
        showPagination={false}
      />
      <LayoutModeSwitch mode={layoutMode} onchange={changeLayoutMode} />
    </div>
    <AssetGrid
      assets={results.items}
      selectedIds={visibleSelectedIds}
      selectionActive={selectedCount > 0}
      indicatorConfig={cardIndicatorConfig}
      {matchingTagIds}
      layout={layoutMode}
      stackPrimaryId={stackPrimaryAssetId}
      onopen={openViewer}
      onselect={selectAtIndex}
      onsetstackprimary={chooseStackPrimary}
      ondragstart={beginDragSelection}
      ondragenter={continueDragSelection}
    />
    {#if listMode === 'infinite'}
      <div bind:this={infiniteSentinel} class="infinite-status" aria-live="polite">
        {#if infiniteLoading}
          Loading more assets…
        {:else if !infiniteHasMore}
          End of matching assets
        {/if}
      </div>
    {/if}
    <AssetPagination
      page={results.page}
      pages={results.pages}
      total={results.total}
      pageSize={results.page_size}
      disabled={loading}
      onpage={changePage}
      onpagesizechange={changePageSize}
      mode={listMode}
      showModeToggle={false}
    />
  {/if}
</section>

<AssetActionTaskHistory tasks={actionTaskHistory} />

{#if selectionTask && !isTaskTerminal(selectionTask.status)}
  <AssetTaskProgress task={selectionTask} overlay />
{/if}

{#if actionTask && !isTaskTerminal(actionTask.status)}
  <AssetTaskProgress task={actionTask} overlay oncancel={() => void cancelActionTask()} />
{/if}

{#if selectionTask && selectionTaskErrorOpen}
  <AssetTaskErrorDialog
    task={selectionTask}
    onretry={retryFailedSelection}
    onclose={() => (selectionTaskErrorOpen = false)}
  />
{/if}

{#if actionError}
  <AssetActionErrorDialog
    message={actionError}
    onclose={() => (actionError = null)}
  />
{/if}

{#if syncError}
  <AssetActionErrorDialog
    message={syncError}
    onclose={() => (syncError = null)}
  />
{/if}

{#if syncCompletionMessage}
  <ConfirmDialog
    title="Synchronization completed"
    message={syncCompletionMessage}
    confirmLabel="Close"
    icon="check"
    onconfirm={() => (syncCompletionMessage = null)}
    onclose={() => (syncCompletionMessage = null)}
  />
{/if}

{#if actionCompletionMessage}
  <ConfirmDialog
    title="Action completed"
    message={actionCompletionMessage}
    confirmLabel="Close"
    icon="check"
    onconfirm={() => (actionCompletionMessage = null)}
    onclose={() => (actionCompletionMessage = null)}
  />
{/if}

{#if viewerIndex !== null && (viewerSelectedAsset || results?.items[viewerIndex])}
  <AssetViewerDialog
    assets={results?.items ?? []}
    initialIndex={viewerIndex}
    selectedAsset={viewerSelectedAsset}
    selectedIds={visibleSelectedIds}
    {detail}
    {detailLoading}
    {detailError}
    {albums}
    {tags}
    actionPlan={actionContext === 'viewer' ? actionPlan : null}
    actionSummary={viewerActionAssetId ? viewerActionResolution?.summary ?? null : null}
    selectionCount={selectedCount}
    selectionStackPrimaryId={stackPrimaryAssetId}
    {actionBusy}
    actionError={actionContext === 'viewer' ? actionError ?? viewerActionError : viewerActionError}
    syncBusy={viewerSyncing}
    syncError={viewerSyncError}
    comparisonSource={viewerComparisonSource}
    comparisonActivation={viewerComparisonActivation}
    canrequestprevious={listMode === 'paged' && page > 1}
    onrequestprevious={requestPreviousViewerIndex}
    canrequestnext={listMode === 'infinite' ? infiniteHasMore : page < (results?.pages ?? 0)}
    onrequestnext={requestNextViewerIndex}
    onnavigate={navigateViewer}
    oncomparisonnavigate={(assetId) => void selectViewerComparisonAsset(assetId)}
    ontoggleselection={toggleSelection}
    onselectionstackprimary={chooseStackPrimary}
    onpreviewchange={() => invalidateViewerActionPlan()}
    onaction={previewViewerAction}
    onsetprimary={(assetId) => previewViewerAction(assetId, 'set_stack_primary')}
    onrelationconfirm={confirmViewerRelationAction}
    onconfirmaction={confirmAction}
    oncancelaction={invalidateActionPlan}
    onsync={(assetId) => void syncViewerAsset(assetId)}
    onclose={closeViewer}
  />
{/if}

<style>
  .asset-workspace {
    display: grid;
    gap: 1.1rem;
  }

  .result-layout-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    justify-content: space-between;
    gap: 0.65rem 1rem;
  }

  .infinite-status {
    min-height: 1.5rem;
    color: var(--color-ink-muted);
    text-align: center;
    font-size: 0.72rem;
  }

  .action-message {
    margin: 0;
    color: var(--color-accent-strong);
    font-size: 0.74rem;
    font-weight: 720;
  }

  .action-error {
    margin: 0;
    color: var(--color-danger, #b42318);
    font-size: 0.74rem;
    font-weight: 720;
  }
</style>

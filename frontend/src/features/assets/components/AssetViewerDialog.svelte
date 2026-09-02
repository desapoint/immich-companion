<script lang="ts" module>
  /**
   * Window key events also bubble out of native dialogs. Only the viewer's
   * own surface may use its shortcuts; nested dialogs and controls must keep
   * their native keyboard behavior.
   */
  export function shouldHandleViewerShortcut(
    target: object | null,
    viewerDialog: object,
  ): boolean {
    const element = target as (EventTarget & {
      closest?: (selector: string) => object | null;
    }) | null;
    const closestDialog = element?.closest?.('dialog, [role="dialog"]');
    if (closestDialog && closestDialog !== viewerDialog) return false;
    return !element?.closest?.(
      'input, textarea, select, button, a, summary, [role="button"], [contenteditable="true"]',
    );
  }

  export function shouldHandleDuplicateComparisonShortcut(
    target: object | null,
    viewerDialog: object,
  ): boolean {
    const element = target as (EventTarget & {
      closest?: (selector: string) => object | null;
    }) | null;
    const closestDialog = element?.closest?.('dialog, [role="dialog"]');
    if (closestDialog && closestDialog !== viewerDialog) return false;
    return !element?.closest?.(
      'input, textarea, select, [contenteditable="true"]',
    );
  }

  export function duplicateViewerShortcut(
    key: string,
  ): 'keep' | 'delete' | 'stack' | 'primary' | null {
    return ({ k: 'keep', d: 'delete', s: 'stack', p: 'primary' } as const)[key] ?? null;
  }
</script>

<script lang="ts">
  import { flushSync, onMount, untrack } from 'svelte';

  import {
    analyzeAssetIntegrity,
    buildAssetPreviewItems,
    getAssetIntegrity,
    getTaskStatus,
    openTaskStream,
  } from '../api/assetApi';
  import {
    assetAsStackMember,
    comparisonPreviewState,
    nextViewerIndex,
    stackMembersForAsset,
  } from '../state/assetViewModel';
  import { resolveViewerMediaUrls } from '../state/viewerMedia';
  import {
    anchoredScrollOffset,
    captureImageZoomAnchor,
    captureViewerPanOrigin,
    captureVisibleImageCenter,
    draggedScrollOffset,
    type ImageZoomAnchor,
    type ViewerPanOrigin,
  } from '../state/viewerZoom';
  import type {
    AlbumOption,
    AssetActionIntent,
    AssetActionPlan,
    AssetComparisonActivation,
    AssetComparisonSource,
    AssetDetail,
    AssetIntegrityReport,
    AssetStackMember,
    AssetSummary,
    AssetSelectionSummary,
    AssetTaskStatus,
    DuplicateReviewContext,
    TagOption,
    ViewerScaleMode,
  } from '../types/assets';
  import AssetInfoPanel from './AssetInfoPanel.svelte';
  import AssetIntegrityDialog from './AssetIntegrityDialog.svelte';
  import AssetActionConfirmDialog from './AssetActionConfirmDialog.svelte';
  import AssetViewerComparisonTray from './AssetViewerComparisonTray.svelte';
  import DuplicateComparisonMatrix from './DuplicateComparisonMatrix.svelte';
  import AssetViewerFooter from './AssetViewerFooter.svelte';
  import AssetViewerHeader from './AssetViewerHeader.svelte';

  interface Props {
    assets: AssetSummary[];
    initialIndex: number;
    selectedAsset?: AssetSummary | null;
    selectedIds: Set<string>;
    detail: AssetDetail | null;
    detailLoading: boolean;
    detailError: string | null;
    albums: AlbumOption[];
    tags: TagOption[];
    actionPlan: AssetActionPlan | null;
    actionSummary: AssetSelectionSummary | null;
    actionBusy?: boolean;
    actionError?: string | null;
    syncBusy?: boolean;
    syncError?: string | null;
    actionsEnabled?: boolean;
    selectionEnabled?: boolean;
    selectionCount?: number;
    selectionStackPrimaryId?: string | null;
    restoreBusy?: boolean;
    apiOnly?: boolean;
    integrityEnabled?: boolean;
    duplicateContext?: DuplicateReviewContext | null;
    onduplicatedisposition?: (assetId: string, disposition: 'keep' | 'delete' | 'stack') => void;
    onduplicatestackprimary?: (assetId: string) => void;
    onduplicatesimilarityreference?: (assetId: string) => boolean | void | Promise<boolean | void>;
    onduplicatepreviousgroup?: () => void;
    onduplicatenextgroup?: () => void;
    comparisonSource?: AssetComparisonSource;
    comparisonActivation?: AssetComparisonActivation;
    comparisonAssets?: AssetStackMember[];
    oncomparisonnavigate?: (assetId: string) => void;
    canrequestprevious?: boolean;
    onrequestprevious?: () => Promise<number | null>;
    canrequestnext?: boolean;
    onrequestnext?: () => Promise<number | null>;
    onnavigate: (index: number) => void;
    ontoggleselection: (assetId: string) => void;
    onselectionstackprimary?: (assetId: string) => void;
    onvisiblechange: (assetId: string) => void;
    onaction: (
      assetId: string,
      action: AssetActionIntent,
      relationIds?: string[],
    ) => void;
    onsetprimary?: (assetId: string) => void;
    onrelationconfirm: (
      assetId: string,
      action: Extract<AssetActionIntent, 'add_album' | 'add_tag' | 'remove_album' | 'remove_tag'>,
      relationIds: string[],
    ) => void;
    onconfirmaction: () => void;
    oncancelaction: () => void;
    onrestore?: (assetId: string) => void;
    onsync: (assetId: string) => void;
    onclose: () => void;
  }

  let {
    assets,
    initialIndex,
    selectedAsset = null,
    selectedIds,
    detail,
    detailLoading,
    detailError,
    albums,
    tags,
    actionPlan,
    actionSummary,
    actionBusy = false,
    actionError = null,
    syncBusy = false,
    syncError = null,
    actionsEnabled = true,
    selectionEnabled,
    selectionCount = 0,
    selectionStackPrimaryId = null,
    restoreBusy = false,
    apiOnly = false,
    integrityEnabled = !apiOnly,
    duplicateContext = null,
    onduplicatedisposition,
    onduplicatestackprimary,
    onduplicatesimilarityreference,
    onduplicatepreviousgroup,
    onduplicatenextgroup,
    comparisonSource = 'stack',
    comparisonActivation = 'click',
    comparisonAssets = [],
    oncomparisonnavigate,
    canrequestprevious = false,
    onrequestprevious,
    canrequestnext = false,
    onrequestnext,
    onnavigate,
    ontoggleselection,
    onselectionstackprimary,
    onvisiblechange,
    onaction,
    onsetprimary,
    onrelationconfirm,
    onconfirmaction,
    oncancelaction,
    onrestore,
    onsync,
    onclose,
  }: Props = $props();

  let dialogElement: HTMLDialogElement;
  let viewerScroll: HTMLDivElement;
  let viewerImage = $state<HTMLImageElement>();
  let scaleMode = $state<ViewerScaleMode>('fit');
  let zoom = $state(1);
  let viewportWidth = $state(1);
  let viewportHeight = $state(1);
  let imageLoading = $state(true);
  let imageError = $state(false);
  let imageNaturalWidth = $state<number | null>(null);
  let imageNaturalHeight = $state<number | null>(null);
  let viewerMediaUrl = $state('');
  let viewerMediaUrls = $state<string[]>([]);
  let viewerMediaIndex = $state(0);
  let infoOpen = $state(false);
  let helpOpen = $state(false);
  let visibleAssetId = $state('');
  let selectedAssetId = '';
  let duplicateGroupId = '';
  let comparisonReferenceId = $state('');
  let comparisonReferenceChanging = $state(false);
  let flickerReturnAssetId = $state<string | null>(null);
  let flickerPending = $state(false);
  let flickerReferenceUrl = $state('');
  let loadedMediaAssetId = '';
  let mediaLoadGeneration = 0;
  const mediaUrlCache = new Map<string, string[]>();
  const mediaPreferredIndex = new Map<string, number>();
  const loadedMediaUrls = new Set<string>();
  const mediaDimensions = new Map<string, { width: number; height: number }>();
  const mediaPreloadPromises = new Map<string, Promise<void>>();
  let pendingComparisonAnchor: ImageZoomAnchor | null = null;
  let panOrigin = $state<ViewerPanOrigin | null>(null);
  let nextLoading = $state(false);
  let integrityDialogOpen = $state(false);
  let integrityAssetId = $state('');
  let integrityFilename = $state('');
  let integrityReport = $state.raw<AssetIntegrityReport | null>(null);
  let integrityTask = $state.raw<AssetTaskStatus | null>(null);
  let integrityError = $state<string | null>(null);
  let integritySocket: WebSocket | null = null;
  let integrityPollTimer: ReturnType<typeof setInterval> | null = null;
  let integrityGeneration = 0;
  const currentIndex = $derived(initialIndex);
  const currentAsset = $derived(selectedAsset ?? assets[currentIndex]);
  const selectionAvailable = $derived(selectionEnabled ?? actionsEnabled);
  const comparisonMembers = $derived(
    comparisonSource === 'stack' ? stackMembersForAsset(currentAsset) : comparisonAssets,
  );
  const previewItems = $derived(
    buildAssetPreviewItems(
      comparisonMembers,
      comparisonSource === 'stack' ? currentAsset.stack?.primary_asset_id : undefined,
    ),
  );
  const hasComparisonTray = $derived(previewItems.length > 1);
  const visibleAsset = $derived(
    comparisonMembers.find((asset) => asset.id === visibleAssetId)
      ?? assetAsStackMember(currentAsset),
  );
  const duplicateNavigationAvailable = $derived(
    duplicateContext !== null && comparisonMembers.length > 1,
  );
  const hasPrevious = $derived(
    duplicateNavigationAvailable
      || currentIndex > 0
      || (canrequestprevious && onrequestprevious !== undefined),
  );
  const hasNext = $derived(
    duplicateNavigationAvailable
      || currentIndex < assets.length - 1
      || (canrequestnext && onrequestnext !== undefined),
  );
  const naturalWidth = $derived(
    imageNaturalWidth ?? (apiOnly && detail ? detail.width : visibleAsset.width) ?? 1,
  );
  const naturalHeight = $derived(
    imageNaturalHeight ?? (apiOnly && detail ? detail.height : visibleAsset.height) ?? 1,
  );
  const visibleFilename = $derived(
    apiOnly && detail ? detail.original_file_name : visibleAsset.original_file_name,
  );
  const fitScale = $derived(
    Math.max(0.01, Math.min((viewportWidth - 144) / naturalWidth, (viewportHeight - 32) / naturalHeight)),
  );
  const effectiveScale = $derived((scaleMode === 'fit' ? fitScale : 1) * zoom);
  const displayWidth = $derived(Math.max(1, naturalWidth * effectiveScale));
  const displayHeight = $derived(Math.max(1, naturalHeight * effectiveScale));
  const zoomPercent = $derived(Math.round(zoom * 100));
  const integrityActive = $derived(
    integrityTask !== null
      && integrityAssetId === visibleAsset.id
      && !isTaskTerminal(integrityTask.status),
  );

  function isTaskTerminal(status: AssetTaskStatus['status']): boolean {
    return status === 'completed' || status === 'failed' || status === 'cancelled';
  }

  function stopIntegrityWatch(): void {
    integritySocket?.close();
    integritySocket = null;
    if (integrityPollTimer !== null) {
      clearInterval(integrityPollTimer);
      integrityPollTimer = null;
    }
  }

  async function refreshIntegrityReport(assetId: string, generation: number): Promise<void> {
    try {
      const state = await getAssetIntegrity(assetId);
      if (generation !== integrityGeneration || assetId !== integrityAssetId) return;
      if (state.freshness !== 'current' || !state.report) {
        integrityError = 'The completed report is no longer current for this asset.';
        return;
      }
      integrityError = null;
      integrityReport = state.report;
      integrityTask = null;
    } catch (requestError) {
      if (generation !== integrityGeneration) return;
      integrityError = requestError instanceof Error
        ? requestError.message
        : 'The integrity report could not be loaded.';
    }
  }

  async function handleIntegrityTask(
    task: AssetTaskStatus,
    assetId: string,
    generation: number,
  ): Promise<void> {
    if (generation !== integrityGeneration || assetId !== integrityAssetId) return;
    integrityError = null;
    integrityTask = task;
    if (!isTaskTerminal(task.status)) return;
    stopIntegrityWatch();
    if (task.status === 'completed') {
      await refreshIntegrityReport(assetId, generation);
      return;
    }
    integrityError = task.error?.message
      ?? (task.status === 'cancelled'
        ? 'Integrity analysis was cancelled.'
        : 'Integrity analysis failed.');
  }

  async function pollIntegrityTask(
    taskId: string,
    assetId: string,
    generation: number,
  ): Promise<void> {
    try {
      await handleIntegrityTask(await getTaskStatus(taskId), assetId, generation);
    } catch (requestError) {
      if (generation !== integrityGeneration) return;
      integrityError = requestError instanceof Error
        ? requestError.message
        : 'Integrity progress is temporarily unavailable.';
    }
  }

  function startIntegrityPolling(taskId: string, assetId: string, generation: number): void {
    if (
      generation !== integrityGeneration
      || assetId !== integrityAssetId
      || !integrityDialogOpen
    ) return;
    if (integrityPollTimer !== null) return;
    void pollIntegrityTask(taskId, assetId, generation);
    integrityPollTimer = setInterval(
      () => void pollIntegrityTask(taskId, assetId, generation),
      1000,
    );
  }

  function watchIntegrityTask(taskId: string, assetId: string, generation: number): void {
    stopIntegrityWatch();
    integritySocket = openTaskStream(
      taskId,
      (task) => void handleIntegrityTask(task, assetId, generation),
      () => startIntegrityPolling(taskId, assetId, generation),
    );
  }

  async function openIntegrity(force = false): Promise<void> {
    const assetId = visibleAsset.id;
    const generation = ++integrityGeneration;
    stopIntegrityWatch();
    integrityDialogOpen = true;
    integrityAssetId = assetId;
    integrityFilename = visibleFilename;
    integrityReport = null;
    integrityTask = null;
    integrityError = null;
    try {
      const response = await analyzeAssetIntegrity(assetId, force);
      if (generation !== integrityGeneration || assetId !== integrityAssetId) return;
      integrityReport = response.state === 'ready' ? response.report : null;
      if (response.state === 'ready' && response.report) return;
      if (!response.task_id) {
        integrityError = 'Companion did not return an integrity task.';
        return;
      }
      watchIntegrityTask(response.task_id, assetId, generation);
    } catch (requestError) {
      if (generation !== integrityGeneration) return;
      integrityError = requestError instanceof Error
        ? requestError.message
        : 'Integrity analysis could not be started.';
    }
  }

  function closeIntegrity(): void {
    integrityGeneration += 1;
    stopIntegrityWatch();
    integrityDialogOpen = false;
    integrityTask = null;
  }

  function normalizedZoom(value: number): number {
    return Math.min(8, Math.max(0.25, Math.round(value * 100) / 100));
  }

  function currentVisibleCenterAnchor(): ImageZoomAnchor | null {
    if (!viewerImage || imageLoading || imageError) return null;
    return captureVisibleImageCenter(
      viewerImage.getBoundingClientRect(),
      viewerScroll.getBoundingClientRect(),
    );
  }

  function captureDuplicateComparisonView(): void {
    if (!duplicateContext) return;
    pendingComparisonAnchor = currentVisibleCenterAnchor();
  }

  function restoreDuplicateComparisonView(): void {
    const anchor = pendingComparisonAnchor;
    if (!anchor || !viewerImage || imageLoading || imageError) return;
    pendingComparisonAnchor = null;
    requestAnimationFrame(() => {
      if (!viewerImage) return;
      const offset = anchoredScrollOffset(
        anchor,
        viewerImage.getBoundingClientRect(),
        viewerScroll.scrollLeft,
        viewerScroll.scrollTop,
      );
      viewerScroll.scrollLeft = offset.left;
      viewerScroll.scrollTop = offset.top;
    });
  }

  function changeZoom(value: number, anchor: ImageZoomAnchor | null): void {
    const nextZoom = normalizedZoom(value);
    if (nextZoom === zoom) return;
    flushSync(() => {
      zoom = nextZoom;
    });
    if (!anchor || !viewerImage) return;
    const offset = anchoredScrollOffset(
      anchor,
      viewerImage.getBoundingClientRect(),
      viewerScroll.scrollLeft,
      viewerScroll.scrollTop,
    );
    viewerScroll.scrollLeft = offset.left;
    viewerScroll.scrollTop = offset.top;
  }

  function changeZoomFromVisibleCenter(value: number): void {
    changeZoom(value, currentVisibleCenterAnchor());
  }

  function toggleScale(): void {
    scaleMode = scaleMode === 'fit' ? 'actual' : 'fit';
    zoom = 1;
  }

  function closeViewer(): void {
    if (dialogElement.open) dialogElement.close();
    onclose();
  }

  function cancelReferenceFlicker(): void {
    flickerPending = false;
    flickerReturnAssetId = null;
    flickerReferenceUrl = '';
  }

  async function setComparisonReference(assetId: string): Promise<void> {
    if (
      !duplicateContext
      || !onduplicatesimilarityreference
      || assetId === comparisonReferenceId
      || comparisonReferenceChanging
    ) return;
    cancelReferenceFlicker();
    captureDuplicateComparisonView();
    comparisonReferenceChanging = true;
    try {
      const changed = await onduplicatesimilarityreference(assetId);
      if (changed === false) return;
      comparisonReferenceId = assetId;
    } finally {
      comparisonReferenceChanging = false;
    }
  }

  function cycleDuplicateComparison(direction: 'previous' | 'next'): void {
    const members = comparisonMembers;
    if (members.length < 2) return;
    cancelReferenceFlicker();
    captureDuplicateComparisonView();
    const currentMemberIndex = members.findIndex((asset) => asset.id === visibleAssetId);
    const nextIndex = currentMemberIndex < 0
      ? direction === 'next' ? 0 : members.length - 1
      : direction === 'next'
        ? (currentMemberIndex + 1) % members.length
        : (currentMemberIndex - 1 + members.length) % members.length;
    visibleAssetId = members[nextIndex].id;
  }

  async function navigate(direction: 'previous' | 'next'): Promise<void> {
    if (duplicateNavigationAvailable) {
      cycleDuplicateComparison(direction);
      return;
    }
    captureDuplicateComparisonView();
    const nextIndex = nextViewerIndex(currentIndex, direction, assets.length);
    const canLoadAdjacent = direction === 'next'
      ? canrequestnext && onrequestnext !== undefined
      : canrequestprevious && onrequestprevious !== undefined;
    const loadAdjacent = direction === 'next' ? onrequestnext : onrequestprevious;
    if (nextIndex === currentIndex && canLoadAdjacent && loadAdjacent) {
      if (nextLoading) return;
      nextLoading = true;
      try {
        const loadedIndex = await loadAdjacent();
        if (loadedIndex !== null) onnavigate(loadedIndex);
      } finally {
        nextLoading = false;
      }
      return;
    }
    if (nextIndex === currentIndex) return;
    onnavigate(nextIndex);
  }

  function previewComparison(assetId: string): void {
    cancelReferenceFlicker();
    captureDuplicateComparisonView();
    visibleAssetId = assetId;
  }

  function selectViewedStackAsset(assetId: string): void {
    captureDuplicateComparisonView();
    const resultIndex = assets.findIndex((asset) => asset.id === assetId);
    if (resultIndex >= 0) {
      onnavigate(resultIndex);
      return;
    }
    oncomparisonnavigate?.(assetId);
  }

  function restoreComparison(): void {
    cancelReferenceFlicker();
    captureDuplicateComparisonView();
    visibleAssetId = duplicateContext ? comparisonReferenceId : currentAsset.id;
  }

  function commitComparison(assetId: string): void {
    cancelReferenceFlicker();
    captureDuplicateComparisonView();
    if (duplicateContext) {
      visibleAssetId = assetId;
      return;
    }
    const nextState = comparisonPreviewState(comparisonSource, currentAsset.id, assetId);
    visibleAssetId = nextState.visibleId;
    if (nextState.selectedId === currentAsset.id) return;
    const resultIndex = assets.findIndex((asset) => asset.id === nextState.selectedId);
    if (resultIndex >= 0) onnavigate(resultIndex);
    else oncomparisonnavigate?.(nextState.selectedId);
  }

  function cachedDuplicateMediaUrl(assetId: string): string | null {
    const urls = mediaUrlCache.get(assetId);
    if (!urls?.length) return null;
    const index = Math.min(mediaPreferredIndex.get(assetId) ?? 0, urls.length - 1);
    const url = urls[index];
    return url && loadedMediaUrls.has(url) ? url : null;
  }

  async function startReferenceFlicker(): Promise<void> {
    if (
      !duplicateContext
      || imageLoading
      || imageError
      || flickerPending
      || flickerReturnAssetId !== null
      || visibleAssetId === comparisonReferenceId
    ) return;
    const reference = comparisonMembers.find((member) => member.id === comparisonReferenceId);
    if (!reference) return;
    flickerPending = true;
    let referenceUrl = cachedDuplicateMediaUrl(reference.id);
    if (!referenceUrl) {
      await preloadAssetMedia(reference);
      if (!flickerPending || visibleAssetId === comparisonReferenceId) return;
      referenceUrl = cachedDuplicateMediaUrl(reference.id);
    }
    if (!referenceUrl) {
      flickerPending = false;
      return;
    }
    flickerReturnAssetId = visibleAssetId;
    flickerReferenceUrl = referenceUrl;
    flickerPending = false;
  }

  function stopReferenceFlicker(): void {
    cancelReferenceFlicker();
  }

  function handleKeydown(event: KeyboardEvent): void {
    const key = event.key.toLowerCase();
    const comparisonShortcut = duplicateContext
      && (event.key === 'ArrowLeft' || event.key === 'ArrowRight' || ['h', 'l', 'f', 'r'].includes(key));
    if (comparisonShortcut) {
      if (!shouldHandleDuplicateComparisonShortcut(event.target, dialogElement)) return;
      event.preventDefault();
      if (event.key === 'ArrowLeft' || key === 'h') void navigate('previous');
      else if (event.key === 'ArrowRight' || key === 'l') void navigate('next');
      else if (key === 'f' && !event.repeat) void startReferenceFlicker();
      else if (key === 'r') void setComparisonReference(visibleAsset.id);
      return;
    }
    if (!shouldHandleViewerShortcut(event.target, dialogElement)) return;
    const duplicateShortcut = duplicateContext ? duplicateViewerShortcut(key) : null;

    if (event.key === 'ArrowLeft' || key === 'h') {
      event.preventDefault();
      void navigate('previous');
    } else if (event.key === 'ArrowRight' || key === 'l') {
      event.preventDefault();
      void navigate('next');
    } else if (event.key === ' ') {
      event.preventDefault();
      ontoggleselection(currentAsset.id);
    } else if (duplicateShortcut === 'primary' && onduplicatestackprimary) {
      event.preventDefault();
      onduplicatestackprimary(visibleAsset.id);
    } else if (duplicateShortcut && duplicateShortcut !== 'primary' && onduplicatedisposition) {
      event.preventDefault();
      onduplicatedisposition(visibleAsset.id, duplicateShortcut);
    } else if (key === 'i') {
      event.preventDefault();
      infoOpen = !infoOpen;
    } else if (key === 'm') {
      event.preventDefault();
      toggleScale();
    } else if (event.key === '+' || event.key === '=') {
      event.preventDefault();
      changeZoomFromVisibleCenter(zoom * 1.2);
    } else if (event.key === '-') {
      event.preventDefault();
      changeZoomFromVisibleCenter(zoom / 1.2);
    } else if (event.key === '0') {
      event.preventDefault();
      changeZoomFromVisibleCenter(1);
    } else if (event.key === '?') {
      event.preventDefault();
      helpOpen = !helpOpen;
    } else if (event.key === 'Escape' || key === 'q') {
      event.preventDefault();
      closeViewer();
    }
  }

  function handleKeyup(event: KeyboardEvent): void {
    if (event.key.toLowerCase() !== 'f' || (!flickerPending && flickerReturnAssetId === null)) return;
    event.preventDefault();
    stopReferenceFlicker();
  }

  function handleCancel(event: Event): void {
    event.preventDefault();
    closeViewer();
  }

  function handleWheel(event: WheelEvent): void {
    if (!event.ctrlKey || !viewerImage) return;
    event.preventDefault();
    const imageRect = viewerImage.getBoundingClientRect();
    const anchor = imageLoading || imageError
      ? null
      : captureImageZoomAnchor(event.clientX, event.clientY, imageRect)
        ?? captureVisibleImageCenter(imageRect, viewerScroll.getBoundingClientRect());
    changeZoom(event.deltaY < 0 ? zoom * 1.12 : zoom / 1.12, anchor);
  }

  function startPan(event: PointerEvent): void {
    if (!event.isPrimary || event.button !== 0) return;
    if (
      viewerScroll.scrollWidth <= viewerScroll.clientWidth
      && viewerScroll.scrollHeight <= viewerScroll.clientHeight
    ) return;
    panOrigin = captureViewerPanOrigin(
      event.pointerId,
      event.clientX,
      event.clientY,
      viewerScroll.scrollLeft,
      viewerScroll.scrollTop,
    );
    const target = event.currentTarget as HTMLDivElement | null;
    target?.setPointerCapture(event.pointerId);
  }

  function movePan(event: PointerEvent): void {
    if (!panOrigin || panOrigin.pointerId !== event.pointerId) return;
    event.preventDefault();
    const offset = draggedScrollOffset(panOrigin, event.clientX, event.clientY);
    viewerScroll.scrollLeft = offset.left;
    viewerScroll.scrollTop = offset.top;
  }

  function finishPan(event: PointerEvent): void {
    if (!panOrigin || panOrigin.pointerId !== event.pointerId) return;
    const target = event.currentTarget as HTMLDivElement | null;
    if (target?.hasPointerCapture(event.pointerId)) target.releasePointerCapture(event.pointerId);
    panOrigin = null;
  }

  function applyViewerMedia(assetId: string, urls: string[]): void {
    mediaUrlCache.set(assetId, urls);
    viewerMediaUrls = urls;
    viewerMediaIndex = Math.min(mediaPreferredIndex.get(assetId) ?? 0, Math.max(0, urls.length - 1));
    viewerMediaUrl = urls[viewerMediaIndex] ?? '';
    imageLoading = Boolean(viewerMediaUrl) && !loadedMediaUrls.has(viewerMediaUrl);
    imageError = !viewerMediaUrl;
  }

  async function preloadAssetMedia(asset: AssetStackMember): Promise<void> {
    if (mediaDimensions.has(asset.id)) return;
    const existing = mediaPreloadPromises.get(asset.id);
    if (existing) {
      await existing;
      return;
    }

    const preload = (async () => {
      const urls = mediaUrlCache.get(asset.id)
        ?? await resolveViewerMediaUrls(asset.id, asset.original_mime_type);
      mediaUrlCache.set(asset.id, urls);
      for (let index = mediaPreferredIndex.get(asset.id) ?? 0; index < urls.length; index += 1) {
        const url = urls[index];
        const loaded = await new Promise<HTMLImageElement | null>((resolve) => {
          const image = new Image();
          image.decoding = 'async';
          image.onload = () => resolve(image);
          image.onerror = () => resolve(null);
          image.src = url;
        });
        if (!loaded) continue;
        mediaPreferredIndex.set(asset.id, index);
        loadedMediaUrls.add(url);
        mediaDimensions.set(asset.id, {
          width: loaded.naturalWidth,
          height: loaded.naturalHeight,
        });
        break;
      }
    })();

    mediaPreloadPromises.set(asset.id, preload);
    try {
      await preload;
    } finally {
      if (mediaPreloadPromises.get(asset.id) === preload) mediaPreloadPromises.delete(asset.id);
    }
  }

  function handleImageLoad(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    loadedMediaUrls.add(image.currentSrc || viewerMediaUrl);
    mediaPreferredIndex.set(loadedMediaAssetId, viewerMediaIndex);
    mediaDimensions.set(loadedMediaAssetId, {
      width: image.naturalWidth,
      height: image.naturalHeight,
    });
    flushSync(() => {
      imageNaturalWidth = image.naturalWidth;
      imageNaturalHeight = image.naturalHeight;
      imageLoading = false;
      imageError = false;
    });
    restoreDuplicateComparisonView();
  }

  function handleImageError(): void {
    const nextIndex = viewerMediaIndex + 1;
    if (nextIndex < viewerMediaUrls.length) {
      viewerMediaIndex = nextIndex;
      mediaPreferredIndex.set(loadedMediaAssetId, nextIndex);
      viewerMediaUrl = viewerMediaUrls[nextIndex];
      imageLoading = !loadedMediaUrls.has(viewerMediaUrl);
      imageError = false;
      return;
    }
    imageLoading = false;
    imageError = true;
  }

  $effect(() => {
    const assetId = currentAsset.id;
    if (assetId === selectedAssetId) return;
    selectedAssetId = assetId;
    if (!duplicateContext) visibleAssetId = assetId;
    untrack(() => onvisiblechange(assetId));
  });

  $effect(() => {
    const groupId = duplicateContext?.group_id ?? '';
    if (!groupId || groupId === duplicateGroupId) return;
    duplicateGroupId = groupId;
    cancelReferenceFlicker();
    const availableIds = new Set(comparisonMembers.map((asset) => asset.id));
    const similarityReference = duplicateContext?.members.find(
      (member) => member.similarity?.state === 'reference',
    )?.id ?? null;
    const preferredReference = similarityReference
      ?? duplicateContext?.selected_keeper_asset_id
      ?? duplicateContext?.recommended_keeper_asset_id
      ?? currentAsset.id;
    comparisonReferenceId = availableIds.has(preferredReference)
      ? preferredReference
      : comparisonMembers[0]?.id ?? currentAsset.id;
    visibleAssetId = currentAsset.id;
  });

  $effect(() => {
    if (!duplicateContext || comparisonReferenceChanging) return;
    const similarityReference = duplicateContext.members.find(
      (member) => member.similarity?.state === 'reference',
    )?.id;
    if (similarityReference && similarityReference !== comparisonReferenceId) {
      comparisonReferenceId = similarityReference;
    }
  });

  $effect(() => {
    if (!duplicateContext || comparisonMembers.length < 2) return;
    const members = [...comparisonMembers];
    const activeId = visibleAsset.id;
    untrack(() => {
      for (const member of members) {
        if (member.id !== activeId) void preloadAssetMedia(member);
      }
    });
  });

  $effect(() => {
    const assetId = visibleAsset.id;
    const mimeType = visibleAsset.original_mime_type;
    if (assetId === loadedMediaAssetId) return;
    loadedMediaAssetId = assetId;
    const generation = ++mediaLoadGeneration;
    untrack(() => onvisiblechange(assetId));
    if (!duplicateContext) zoom = 1;
    const cachedDimensions = mediaDimensions.get(assetId);
    imageNaturalWidth = cachedDimensions?.width ?? null;
    imageNaturalHeight = cachedDimensions?.height ?? null;
    imageError = false;
    const cachedUrls = mediaUrlCache.get(assetId);
    if (cachedUrls) {
      applyViewerMedia(assetId, cachedUrls);
      return;
    }
    imageLoading = true;
    viewerMediaUrl = '';
    viewerMediaUrls = [];
    viewerMediaIndex = 0;

    untrack(() => {
      void resolveViewerMediaUrls(assetId, mimeType).then((urls) => {
        if (generation !== mediaLoadGeneration || loadedMediaAssetId !== assetId) return;
        applyViewerMedia(assetId, urls);
      });
    });
  });

  onMount(() => {
    if (duplicateContext) infoOpen = true;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogElement.showModal();
    dialogElement.focus({ preventScroll: true });
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('keyup', handleKeyup);
    const resizeObserver = new ResizeObserver(([entry]) => {
      viewportWidth = entry.contentRect.width;
      viewportHeight = entry.contentRect.height;
    });
    resizeObserver.observe(viewerScroll);
    return () => {
      stopIntegrityWatch();
      resizeObserver.disconnect();
      window.removeEventListener('keydown', handleKeydown);
      window.removeEventListener('keyup', handleKeyup);
      document.body.style.overflow = previousOverflow;
    };
  });
</script>

<dialog
  bind:this={dialogElement}
  class="asset-viewer"
  aria-labelledby="asset-viewer-title"
  tabindex="-1"
  oncancel={handleCancel}
>
  <AssetViewerHeader
    filename={visibleFilename}
    selectedFilename={apiOnly && detail ? detail.original_file_name : currentAsset.original_file_name}
    selected={selectedIds.has(currentAsset.id)}
    {scaleMode}
    {infoOpen}
    {helpOpen}
    {zoomPercent}
    {actionSummary}
    {albums}
    {tags}
    hasStack={currentAsset.stack !== null}
    isVisibleStackPrimary={currentAsset.stack?.primary_asset_id === visibleAsset.id}
    {actionBusy}
    {actionError}
    {actionsEnabled}
    selectionEnabled={selectionAvailable}
    {restoreBusy}
    {integrityActive}
    duplicateMode={duplicateContext !== null}
    onrestore={onrestore ? () => onrestore(currentAsset.id) : undefined}
    onintegrity={integrityEnabled ? () => void openIntegrity() : undefined}
    onaction={(action, relationIds) => onaction(currentAsset.id, action, relationIds)}
    onsetprimary={() => onsetprimary?.(visibleAsset.id)}
    onrelationconfirm={(action, relationIds) =>
      onrelationconfirm(currentAsset.id, action, relationIds)}
    ontoggleselection={() => ontoggleselection(currentAsset.id)}
    ontogglescale={toggleScale}
    onzoomout={() => changeZoomFromVisibleCenter(zoom / 1.2)}
    onzoomreset={() => changeZoomFromVisibleCenter(1)}
    onzoomin={() => changeZoomFromVisibleCenter(zoom * 1.2)}
    ontoggleinfo={() => (infoOpen = !infoOpen)}
    ontogglehelp={() => (helpOpen = !helpOpen)}
    onclose={closeViewer}
  />

  {#if actionPlan}
    <AssetActionConfirmDialog
      plan={actionPlan}
      {albums}
      {tags}
      busy={actionBusy}
      onconfirm={onconfirmaction}
      onclose={oncancelaction}
    />
  {/if}

  {#if integrityDialogOpen}
    <AssetIntegrityDialog
      filename={integrityFilename}
      report={integrityReport}
      task={integrityTask}
      error={integrityError}
      onreanalyze={() => void openIntegrity(true)}
      onclose={closeIntegrity}
    />
  {/if}

  <section class="viewer-content" aria-label="Full-size image">
    <div bind:this={viewerScroll} class="viewer-scroll">
      <div
        class="viewer-stage"
        class:dragging={panOrigin !== null}
        role="group"
        aria-label="Image pan and zoom surface"
        style={`width: max(100%, ${displayWidth + 144}px); min-height: max(100%, ${displayHeight + 32}px);`}
        onwheel={handleWheel}
        onpointerdown={startPan}
        onpointermove={movePan}
        onpointerup={finishPan}
        onpointercancel={finishPan}
        onlostpointercapture={finishPan}
      >
        {#if imageLoading}
          <div class="image-status" role="status">Loading full-size image…</div>
        {/if}
        {#if imageError}
          <div class="image-status error" role="alert">The full-size image could not be loaded.</div>
        {/if}
        {#if viewerMediaUrl}
          <img
            bind:this={viewerImage}
            src={viewerMediaUrl}
            alt={visibleAsset.original_file_name}
            draggable="false"
            class:hidden={imageLoading || imageError}
            style={`width: ${displayWidth}px; height: ${displayHeight}px;`}
            onload={handleImageLoad}
            onerror={handleImageError}
            ondblclick={toggleScale}
          />
        {/if}
        {#if flickerReferenceUrl}
          <img
            class="flicker-reference"
            src={flickerReferenceUrl}
            alt="Comparison reference"
            draggable="false"
            style={`width: ${displayWidth}px; height: ${displayHeight}px;`}
          />
        {/if}
      </div>
    </div>

    <button
      class="viewer-nav previous"
      type="button"
      onclick={() => void navigate('previous')}
      disabled={!hasPrevious || nextLoading}
      aria-label={duplicateContext ? 'Previous group image' : 'Previous image'}
      title={duplicateContext ? 'Previous group image (Left arrow or H)' : 'Previous image (Left arrow or H)'}
    >
      ‹
    </button>
    <button
      class="viewer-nav next"
      type="button"
      onclick={() => void navigate('next')}
      disabled={!hasNext || nextLoading}
      aria-label={duplicateContext ? 'Next group image' : 'Next image'}
      title={duplicateContext ? 'Next group image (Right arrow or L)' : 'Next image (Right arrow or L)'}
    >
      ›
    </button>

    {#if duplicateContext && comparisonReferenceChanging}
      <div class="flicker-status" role="status">Updating comparison reference…</div>
    {:else if duplicateContext && flickerReturnAssetId !== null}
      <div class="flicker-status" role="status">Reference · release F to return</div>
    {/if}

    {#if duplicateContext && comparisonReferenceId}
      <DuplicateComparisonMatrix
        context={duplicateContext}
        referenceId={comparisonReferenceId}
        visibleId={visibleAsset.id}
      />
    {/if}

    {#if infoOpen}
      <AssetInfoPanel
        asset={currentAsset}
        {detail}
        loading={detailLoading}
        error={detailError}
        reserveComparisonTray={hasComparisonTray}
        syncing={syncBusy}
        syncError={syncError}
        onsync={() => onsync(currentAsset.id)}
        {apiOnly}
        selectionStackActive={selectionCount >= 2}
        selectionStackEligible={selectedIds.has(currentAsset.id)}
        selectionStackPrimary={selectionStackPrimaryId === currentAsset.id}
        {onselectionstackprimary}
        {duplicateContext}
        {onduplicatedisposition}
        {onduplicatestackprimary}
        {onduplicatesimilarityreference}
        {onduplicatepreviousgroup}
        {onduplicatenextgroup}
      />
    {/if}

    {#if hasComparisonTray}
      <AssetViewerComparisonTray
        items={previewItems}
        source={comparisonSource}
        activation={comparisonActivation}
        selectedId={duplicateContext ? comparisonReferenceId : currentAsset.id}
        visibleId={visibleAsset.id}
        avoidInfoPanel={infoOpen}
        onpreview={previewComparison}
        onrestore={restoreComparison}
        oncommit={commitComparison}
        onselectviewed={duplicateContext ? (assetId) => void setComparisonReference(assetId) : selectViewedStackAsset}
      />
    {/if}
  </section>

  <AssetViewerFooter
    asset={apiOnly && detail ? detail : visibleAsset}
    position={currentIndex + 1}
    total={assets.length}
    selectedId={duplicateContext ? comparisonReferenceId : currentAsset.id}
    visibleId={visibleAsset.id}
  />
</dialog>

<style>
  .asset-viewer {
    width: 100vw;
    max-width: none;
    height: 100vh;
    height: 100dvh;
    max-height: none;
    margin: 0;
    padding: 0;
    overflow: hidden;
    border: 0;
    color: var(--color-ink-strong);
    background: var(--color-canvas);
  }

  .asset-viewer[open] {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
  }

  .asset-viewer::backdrop {
    background: rgb(0 0 0 / 82%);
    backdrop-filter: blur(0.45rem);
  }

  .viewer-content {
    position: relative;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background-color: #111713;
    background-image:
      linear-gradient(45deg, #263029 25%, transparent 25%),
      linear-gradient(-45deg, #263029 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #263029 75%),
      linear-gradient(-45deg, transparent 75%, #263029 75%);
    background-position: 0 0, 0 0.75rem, 0.75rem -0.75rem, -0.75rem 0;
    background-size: 1.5rem 1.5rem;
  }

  .viewer-scroll {
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    overflow: scroll;
    overscroll-behavior: contain;
    overflow-anchor: none;
    scrollbar-gutter: stable both-edges;
  }

  .viewer-stage {
    display: grid;
    position: relative;
    place-items: center;
    padding: 1rem clamp(3.5rem, 7vw, 6rem);
    cursor: grab;
    touch-action: none;
    user-select: none;
  }

  .viewer-stage.dragging {
    cursor: grabbing;
  }

  .viewer-stage img {
    display: block;
    max-width: none;
    max-height: none;
    user-select: none;
  }

  .viewer-stage img.hidden {
    visibility: hidden;
  }

  .viewer-stage img.flicker-reference {
    position: absolute;
    z-index: 1;
    top: 50%;
    left: 50%;
    pointer-events: none;
    transform: translate(-50%, -50%);
  }

  .image-status,
  .flicker-status {
    position: absolute;
    z-index: 2;
    max-width: min(24rem, calc(100vw - 4rem));
    padding: 0.7rem 0.9rem;
    border: 1px solid rgb(255 255 255 / 22%);
    border-radius: var(--radius-sm);
    color: #fff;
    background: rgb(0 0 0 / 70%);
    font-size: 0.78rem;
  }

  .flicker-status {
    z-index: 6;
    top: 0.8rem;
    left: 50%;
    padding: 0.42rem 0.65rem;
    transform: translateX(-50%);
  }

  .image-status.error {
    color: #ffd6d6;
  }

  .viewer-nav {
    position: absolute;
    z-index: 3;
    top: 50%;
    display: grid;
    width: clamp(2.6rem, 5vw, 3.6rem);
    height: clamp(3.8rem, 9vh, 5.5rem);
    padding: 0;
    place-items: center;
    border: 1px solid rgb(255 255 255 / 24%);
    border-radius: var(--radius-sm);
    color: #fff;
    background: rgb(0 0 0 / 64%);
    box-shadow: 0 0.7rem 2rem rgb(0 0 0 / 25%);
    cursor: pointer;
    font-size: 2rem;
    transform: translateY(-50%);
    backdrop-filter: blur(0.4rem);
  }

  .viewer-nav.previous {
    left: 0.7rem;
  }

  .viewer-nav.next {
    right: 0.7rem;
  }

  .viewer-nav:disabled {
    cursor: default;
    opacity: 0.22;
  }

  @media (max-width: 38rem) {
    .viewer-stage {
      padding-inline: 2.8rem;
    }

    .viewer-nav.previous {
      left: 0.25rem;
    }

    .viewer-nav.next {
      right: 0.25rem;
    }
  }
</style>

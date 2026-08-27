<script lang="ts">
  import { flushSync, onMount, untrack } from 'svelte';

  import { assetOriginalUrl, buildAssetPreviewItems } from '../api/assetApi';
  import {
    assetAsStackMember,
    comparisonPreviewState,
    nextViewerIndex,
    stackMembersForAsset,
  } from '../state/assetViewModel';
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
    AssetStackMember,
    AssetSummary,
    AssetSelectionSummary,
    TagOption,
    ViewerScaleMode,
  } from '../types/assets';
  import AssetInfoPanel from './AssetInfoPanel.svelte';
  import AssetActionConfirmDialog from './AssetActionConfirmDialog.svelte';
  import AssetViewerComparisonTray from './AssetViewerComparisonTray.svelte';
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
    comparisonSource?: AssetComparisonSource;
    comparisonActivation?: AssetComparisonActivation;
    comparisonAssets?: AssetStackMember[];
    oncomparisonnavigate?: (assetId: string) => void;
    canrequestnext?: boolean;
    onrequestnext?: () => Promise<number | null>;
    onnavigate: (index: number) => void;
    ontoggleselection: (assetId: string) => void;
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
    comparisonSource = 'stack',
    comparisonActivation = 'click',
    comparisonAssets = [],
    oncomparisonnavigate,
    canrequestnext = false,
    onrequestnext,
    onnavigate,
    ontoggleselection,
    onvisiblechange,
    onaction,
    onsetprimary,
    onrelationconfirm,
    onconfirmaction,
    oncancelaction,
    onsync,
    onclose,
  }: Props = $props();

  let dialogElement: HTMLDialogElement;
  let viewerScroll: HTMLDivElement;
  let viewerImage: HTMLImageElement;
  let scaleMode = $state<ViewerScaleMode>('fit');
  let zoom = $state(1);
  let viewportWidth = $state(1);
  let viewportHeight = $state(1);
  let imageLoading = $state(true);
  let imageError = $state(false);
  let infoOpen = $state(false);
  let helpOpen = $state(false);
  let visibleAssetId = $state('');
  let selectedAssetId = '';
  let loadedMediaAssetId = '';
  let panOrigin = $state<ViewerPanOrigin | null>(null);
  let nextLoading = $state(false);
  const currentIndex = $derived(initialIndex);
  const currentAsset = $derived(selectedAsset ?? assets[currentIndex]);
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
  const hasPrevious = $derived(currentIndex > 0);
  const hasNext = $derived(currentIndex < assets.length - 1 || (canrequestnext && onrequestnext !== undefined));
  const naturalWidth = $derived(visibleAsset.width ?? 1);
  const naturalHeight = $derived(visibleAsset.height ?? 1);
  const fitScale = $derived(
    Math.max(0.01, Math.min((viewportWidth - 144) / naturalWidth, (viewportHeight - 32) / naturalHeight)),
  );
  const effectiveScale = $derived((scaleMode === 'fit' ? fitScale : 1) * zoom);
  const displayWidth = $derived(Math.max(1, naturalWidth * effectiveScale));
  const displayHeight = $derived(Math.max(1, naturalHeight * effectiveScale));
  const zoomPercent = $derived(Math.round(zoom * 100));

  function normalizedZoom(value: number): number {
    return Math.min(8, Math.max(0.25, Math.round(value * 100) / 100));
  }

  function currentVisibleCenterAnchor(): ImageZoomAnchor | null {
    if (imageLoading || imageError) return null;
    return captureVisibleImageCenter(
      viewerImage.getBoundingClientRect(),
      viewerScroll.getBoundingClientRect(),
    );
  }

  function changeZoom(value: number, anchor: ImageZoomAnchor | null): void {
    const nextZoom = normalizedZoom(value);
    if (nextZoom === zoom) return;
    flushSync(() => {
      zoom = nextZoom;
    });
    if (!anchor) return;
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

  async function navigate(direction: 'previous' | 'next'): Promise<void> {
    const nextIndex = nextViewerIndex(currentIndex, direction, assets.length);
    if (nextIndex === currentIndex && direction === 'next' && onrequestnext && canrequestnext) {
      if (nextLoading) return;
      nextLoading = true;
      try {
        const loadedIndex = await onrequestnext();
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
    visibleAssetId = assetId;
  }

  function selectViewedStackAsset(assetId: string): void {
    const resultIndex = assets.findIndex((asset) => asset.id === assetId);
    if (resultIndex >= 0) {
      onnavigate(resultIndex);
      return;
    }
    oncomparisonnavigate?.(assetId);
  }

  function restoreComparison(): void {
    visibleAssetId = currentAsset.id;
  }

  function commitComparison(assetId: string): void {
    const nextState = comparisonPreviewState(comparisonSource, currentAsset.id, assetId);
    visibleAssetId = nextState.visibleId;
    if (nextState.selectedId === currentAsset.id) return;
    const resultIndex = assets.findIndex((asset) => asset.id === nextState.selectedId);
    if (resultIndex >= 0) onnavigate(resultIndex);
    else oncomparisonnavigate?.(nextState.selectedId);
  }

  function handleKeydown(event: KeyboardEvent): void {
    const target = event.target as HTMLElement | null;
    if (target?.closest('dialog, [role="dialog"]')) return;
    if (target?.matches('input, textarea, select, [contenteditable="true"]')) return;
    const key = event.key.toLowerCase();

    if (event.key === 'ArrowLeft' || key === 'h') {
      event.preventDefault();
      void navigate('previous');
    } else if (event.key === 'ArrowRight' || key === 'l') {
      event.preventDefault();
      void navigate('next');
    } else if (event.key === ' ' && !target?.closest('button, a, summary')) {
      event.preventDefault();
      ontoggleselection(currentAsset.id);
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

  function handleCancel(event: Event): void {
    event.preventDefault();
    closeViewer();
  }

  function handleWheel(event: WheelEvent): void {
    if (!event.ctrlKey) return;
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

  $effect(() => {
    const assetId = currentAsset.id;
    if (assetId === selectedAssetId) return;
    selectedAssetId = assetId;
    visibleAssetId = assetId;
    untrack(() => onvisiblechange(assetId));
  });

  $effect(() => {
    const assetId = visibleAsset.id;
    if (assetId === loadedMediaAssetId) return;
    loadedMediaAssetId = assetId;
    untrack(() => onvisiblechange(currentAsset.id));
    zoom = 1;
    imageLoading = true;
    imageError = false;
  });

  onMount(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogElement.showModal();
    dialogElement.focus({ preventScroll: true });
    window.addEventListener('keydown', handleKeydown);
    const resizeObserver = new ResizeObserver(([entry]) => {
      viewportWidth = entry.contentRect.width;
      viewportHeight = entry.contentRect.height;
    });
    resizeObserver.observe(viewerScroll);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('keydown', handleKeydown);
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
    filename={visibleAsset.original_file_name}
    selectedFilename={currentAsset.original_file_name}
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
        <img
          bind:this={viewerImage}
          src={assetOriginalUrl(visibleAsset.id)}
          alt={visibleAsset.original_file_name}
          draggable="false"
          class:hidden={imageLoading || imageError}
          style={`width: ${displayWidth}px; height: ${displayHeight}px;`}
          onload={() => (imageLoading = false)}
          onerror={() => {
            imageLoading = false;
            imageError = true;
          }}
          ondblclick={toggleScale}
        />
      </div>
    </div>

    <button
      class="viewer-nav previous"
      type="button"
      onclick={() => void navigate('previous')}
      disabled={!hasPrevious}
      aria-label="Previous image"
      title="Previous image (Left arrow or H)"
    >
      ‹
    </button>
    <button
      class="viewer-nav next"
      type="button"
      onclick={() => void navigate('next')}
      disabled={!hasNext || nextLoading}
      aria-label="Next image"
      title="Next image (Right arrow or L)"
    >
      ›
    </button>

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
      />
    {/if}

    {#if hasComparisonTray}
      <AssetViewerComparisonTray
        items={previewItems}
        source={comparisonSource}
        activation={comparisonActivation}
        selectedId={currentAsset.id}
        visibleId={visibleAsset.id}
        avoidInfoPanel={infoOpen}
        onpreview={previewComparison}
        onrestore={restoreComparison}
        oncommit={commitComparison}
        onselectviewed={selectViewedStackAsset}
      />
    {/if}
  </section>

  <AssetViewerFooter
    asset={visibleAsset}
    position={currentIndex + 1}
    total={assets.length}
    selectedId={currentAsset.id}
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

  .image-status {
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

<script lang="ts">
  import { onMount } from 'svelte';
  import { CheckCheck, ListChecks, RotateCcw, Shuffle, X } from '@lucide/svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2InfiniteFooter from '../components/V2InfiniteFooter.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2RangeSlider from '../components/V2RangeSlider.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { createGridViewportAnchor } from '../components/gridViewportAnchor';
  import {
    applyAssetRangeFromSnapshot,
    applyShiftAssetRange,
    cloneAssetSelection,
    emptyAssetSelection,
    getAssetSelectionCount,
    invertAssetSelection,
    isAssetSelected,
    selectAllMatchingAssets,
    selectVisibleAssets,
    toggleAssetSelected,
    type AssetSelectionMode,
    type AssetSelectionState,
  } from '../components/assetSelection';

  let page = $state(1);
  let pageSize = $state(24);
  let resultMode = $state<ResultMode>('Pagination');
  let loaded = $state(24);
  let sort = $state('deletedAt:desc');
  let viewer = $state(false);
  let assetGrid = $state<HTMLElement | null>(null);
  let assetColumns = $state(4);
  let selection = $state<AssetSelectionState>(emptyAssetSelection());

  let pointerCandidate = $state(false);
  let draggingSelection = $state(false);
  let suppressClickId = $state<number | null>(null);
  let dragStartId = $state<number | null>(null);
  let dragMode = $state<AssetSelectionMode>('add');
  let dragStartX = $state(0);
  let dragStartY = $state(0);
  let pointerX = $state(0);
  let pointerY = $state(0);
  let dragSnapshot: AssetSelectionState | null = null;
  let autoScrollFrame: number | null = null;
  let suppressClickFrame: number | null = null;

  const gridViewportAnchor = createGridViewportAnchor(() => assetGrid);
  const total = 126;
  const visibleCount = $derived(resultMode === 'Pagination'
    ? Math.min(pageSize, Math.max(0, total - (page - 1) * pageSize))
    : Math.min(loaded, total));
  const firstIndex = $derived(resultMode === 'Pagination' ? (page - 1) * pageSize : 0);
  const items = $derived(Array.from({ length: visibleCount }, (_, i) => firstIndex + i));
  const selectedCount = $derived(getAssetSelectionCount(selection, total));
  const selectionActive = $derived(selectedCount > 0);
  const selectedVisibleCount = $derived(items.filter((id) => isSelected(id)).length);
  const allMatchingSelected = $derived(selection.allMatchingSelected);

  function setPageSize(next: number): void { pageSize = next; page = 1; loaded = Math.max(next, Math.min(loaded, total)); }
  function setMode(mode: ResultMode): void { resultMode = mode; if (mode === 'Pagination') page = 1; else loaded = Math.max(pageSize, loaded); }
  function setAssetColumns(next: number | string): void { assetColumns = Number(next); gridViewportAnchor.adjust(); }
  function isSelected(id: number): boolean { return isAssetSelected(selection, id); }
  function clearSelection(): void { selection = emptyAssetSelection(); }
  function selectVisible(): void { selection = selectVisibleAssets(items); }
  function selectAllMatching(): void { selection = selectAllMatchingAssets(items[0] ?? null); }
  function invertSelection(): void { selection = invertAssetSelection(selection); }

  function handleSelectionClick(id: number, event: MouseEvent): void {
    selection = event.shiftKey ? applyShiftAssetRange(selection, items, id) : toggleAssetSelected(selection, id);
  }

  function handleTileActivate(id: number, event: MouseEvent): void {
    if (suppressClickId === id) { suppressClickId = null; return; }
    if (selectionActive || event.metaKey || event.ctrlKey || event.shiftKey) { handleSelectionClick(id, event); return; }
    viewer = true;
  }

  function startSelectionPointer(id: number, event: PointerEvent): void {
    if (event.button !== 0 || event.pointerType === 'touch') return;
    pointerCandidate = true;
    draggingSelection = false;
    suppressClickId = null;
    dragStartId = id;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    pointerX = event.clientX;
    pointerY = event.clientY;
    dragMode = isSelected(id) ? 'remove' : 'add';
    dragSnapshot = cloneAssetSelection(selection);
  }

  function applyDragRange(toId: number): void {
    if (dragStartId === null || dragSnapshot === null) return;
    selection = applyAssetRangeFromSnapshot(dragSnapshot, items, dragStartId, toId, dragMode);
  }

  function assetIdUnderPointer(x: number, y: number): number | null {
    const element = document.elementFromPoint(x, y)?.closest<HTMLElement>('[data-asset-id]');
    if (!element) return null;
    const id = Number(element.dataset.assetId);
    return Number.isFinite(id) ? id : null;
  }

  function updateDragFromPointer(): void { const id = assetIdUnderPointer(pointerX, pointerY); if (id !== null) applyDragRange(id); }
  function autoScrollStep(): void {
    if (!draggingSelection) { autoScrollFrame = null; return; }
    const scroller = document.querySelector<HTMLElement>('.v2-content');
    if (scroller) {
      const rect = scroller.getBoundingClientRect();
      const edge = 72;
      let delta = 0;
      if (pointerY < rect.top + edge) delta = -Math.ceil(((rect.top + edge - pointerY) / edge) * 18);
      else if (pointerY > rect.bottom - edge) delta = Math.ceil(((pointerY - (rect.bottom - edge)) / edge) * 18);
      if (delta !== 0) { scroller.scrollTop += delta; updateDragFromPointer(); }
    }
    autoScrollFrame = requestAnimationFrame(autoScrollStep);
  }
  function startAutoScroll(): void { if (autoScrollFrame === null) autoScrollFrame = requestAnimationFrame(autoScrollStep); }
  function stopAutoScroll(): void { if (autoScrollFrame !== null) { cancelAnimationFrame(autoScrollFrame); autoScrollFrame = null; } }
  function clearSuppressedClickSoon(): void {
    if (suppressClickFrame !== null) cancelAnimationFrame(suppressClickFrame);
    suppressClickFrame = requestAnimationFrame(() => { suppressClickId = null; suppressClickFrame = null; });
  }

  function handlePointerMove(event: PointerEvent): void {
    if (!pointerCandidate || dragStartId === null) return;
    pointerX = event.clientX; pointerY = event.clientY;
    if (!draggingSelection) {
      if (Math.hypot(pointerX - dragStartX, pointerY - dragStartY) < 6) return;
      draggingSelection = true;
      selection = { ...selection, anchor: dragStartId };
      document.body.classList.add('v2-range-selecting');
      startAutoScroll();
    }
    event.preventDefault();
    updateDragFromPointer();
  }

  function finishPointerGesture(): void {
    const completedDrag = draggingSelection;
    const startId = dragStartId;
    if (completedDrag) {
      const endId = assetIdUnderPointer(pointerX, pointerY);
      if (endId !== null) applyDragRange(endId);
      selection = { ...selection, anchor: startId };
      suppressClickId = startId;
      clearSuppressedClickSoon();
    }
    pointerCandidate = false; draggingSelection = false; dragStartId = null; dragSnapshot = null;
    stopAutoScroll(); document.body.classList.remove('v2-range-selecting');
  }

  function cancelPointerGesture(): void {
    if (draggingSelection && dragSnapshot !== null) selection = cloneAssetSelection(dragSnapshot);
    pointerCandidate = false; draggingSelection = false; dragStartId = null; dragSnapshot = null; suppressClickId = null;
    stopAutoScroll(); document.body.classList.remove('v2-range-selecting');
  }

  function restoreSelected(): void { clearSelection(); }
  function restoreAll(): void { clearSelection(); }

  onMount(() => () => {
    gridViewportAnchor.destroy(); stopAutoScroll();
    if (suppressClickFrame !== null) cancelAnimationFrame(suppressClickFrame);
    document.body.classList.remove('v2-range-selecting');
  });
</script>

<svelte:window
  onpointermove={handlePointerMove}
  onpointerup={finishPointerGesture}
  onpointercancel={cancelPointerGesture}
  onkeydown={(event) => {
    if (event.key === 'Escape') {
      if (draggingSelection) cancelPointerGesture();
      else if (viewer) viewer = false;
      else if (selectionActive) clearSelection();
    }
  }}
/>

<V2PageLayout title="Restore" description="Review current Immich trash and restore individual, selected, or all trashed assets.">
  {#snippet headerActions()}<V2Button variant="primary" onclick={restoreAll}>Restore all</V2Button>{/snippet}
  <V2Zone>
    {#if selectionActive}
      <V2Toolbar class="v2-selection-toolbar">
        <V2Badge text={allMatchingSelected ? `All ${selectedCount.toLocaleString()} selected` : `${selectedCount.toLocaleString()} selected`} />
        <V2Button title="Select visible" ariaLabel="Select visible" active={selectedVisibleCount === items.length && items.length > 0} onclick={selectVisible}><ListChecks size={18} /></V2Button>
        <V2Button title={`Select all ${total.toLocaleString()} trashed assets`} ariaLabel={`Select all ${total.toLocaleString()} trashed assets`} active={allMatchingSelected} onclick={selectAllMatching}><CheckCheck size={18} /></V2Button>
        <V2Button title="Invert selection" ariaLabel="Invert selection" onclick={invertSelection}><Shuffle size={18} /></V2Button>
        <V2Button title="Clear selection" ariaLabel="Clear selection" onclick={clearSelection}><X size={18} /></V2Button>
        {#snippet actions()}<V2Button variant="primary" title="Restore selected" ariaLabel="Restore selected" onclick={restoreSelected}><RotateCcw size={18} /></V2Button>{/snippet}
      </V2Toolbar>
    {:else}
      <V2Toolbar>
        <V2Badge text={`${total.toLocaleString()} trashed assets`} />
        <V2Button title="Select visible" ariaLabel="Select visible" onclick={selectVisible}><ListChecks size={18} /></V2Button>
        <V2Button title={`Select all ${total.toLocaleString()} trashed assets`} ariaLabel={`Select all ${total.toLocaleString()} trashed assets`} onclick={selectAllMatching}><CheckCheck size={18} /></V2Button>
        {#snippet actions()}
          <V2RangeSlider label="Per row" min={2} max={10} step={1} bind:value={assetColumns} valueLabel={`${assetColumns}`} width={92} thumbSize={18} ariaLabel="Images per row" oninteractionstart={() => gridViewportAnchor.begin(assetColumns)} onchange={setAssetColumns} oninteractionend={gridViewportAnchor.end} />
          <V2CollectionControls id="restore-results" {sort} sortFields={[{value:'deletedAt',label:'Deleted date'},{value:'takenAt',label:'Taken date'},{value:'name',label:'Name'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={(value) => sort = value} onpagesize={setPageSize} onmode={setMode} />
        {/snippet}
      </V2Toolbar>
    {/if}

    <div class="v2-asset-grid" data-fixed-columns="true" style={`--v2-asset-columns:${assetColumns}`} bind:this={assetGrid}>
      {#each items as i}
        <V2AssetTile index={i} label={`Trash item ${i + 1}`} sublabel="Deleted recently" selected={isSelected(i)} selectionMode={selectionActive} onactivate={(event) => handleTileActivate(i, event)} onselect={(event) => handleSelectionClick(i, event)} onpreview={() => viewer = true} onpointerdown={(event) => startSelectionPointer(i, event)} />
      {/each}
    </div>

    {#if resultMode === 'Pagination'}
      <V2Pagination {page} {pageSize} {total} onpage={(next) => page = next} />
    {:else}
      <V2InfiniteFooter loaded={Math.min(loaded, total)} {total} batchSize={pageSize} noun="trashed assets" onloadmore={() => loaded = Math.min(total, loaded + pageSize)} />
    {/if}
  </V2Zone>
</V2PageLayout>

<V2Viewer open={viewer} title="Restore Viewer" mode="restore" onclose={() => viewer = false} />

<script lang="ts">
  import { onMount } from 'svelte';
  import type { LocalChangeDiagnostics } from '../utils/localChangeDiagnostics';
  import LocalChangeControls from './LocalChangeControls.svelte';
  import LocalChangeDiagnosticStatus from './LocalChangeDiagnosticStatus.svelte';
  import LocalChangeGrid from './LocalChangeGrid.svelte';
  import {
    LOCAL_CHANGE_LABEL_FONT_PX,
    LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
    aggregateLocalChangeGrid,
    canRenderLocalChangeLabel,
    clampLocalChangePercent,
    localChangeGridSizeForLevel,
  } from '../utils/localChangeVisualization';

  type ImageRect = { x: number; y: number; width: number; height: number };

  let {
    selectedSrc,
    referenceSrc,
    selectedLabel,
    referenceLabel,
    transform,
    diagnostics = null,
    loading = false,
    error = '',
    emphasis = $bindable(0),
    minimumDifference = $bindable(0),
    highlightColor = $bindable('#00DCFF'),
    highlightColorPosition = $bindable(120),
    gridDetailLevel = $bindable(4),
    onselectedload,
    onreferenceload,
    onselectederror,
    onreferenceerror,
    onviewport,
  }: {
    selectedSrc: string;
    referenceSrc: string;
    selectedLabel: string;
    referenceLabel: string;
    transform: string;
    diagnostics?: LocalChangeDiagnostics | null;
    loading?: boolean;
    error?: string;
    emphasis?: number;
    minimumDifference?: number;
    highlightColor?: string;
    highlightColorPosition?: number;
    gridDetailLevel?: number;
    onselectedload?: (event: Event) => void;
    onreferenceload?: (event: Event) => void;
    onselectederror?: () => void;
    onreferenceerror?: () => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let selectedNaturalWidth = $state(0);
  let selectedNaturalHeight = $state(0);
  let viewportWidth = $state(0);
  let viewportHeight = $state(0);
  let controlsOpen = $state(false);
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;

  function showControls(): void {
    if (hoverTimer) clearTimeout(hoverTimer);
    controlsOpen = true;
  }

  function hideControlsSoon(): void {
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => (controlsOpen = false), 80);
  }

  function parseTransform(value: string): { panX: number; panY: number; zoom: number } {
    const match = value.match(/translate\((-?[\d.]+)px,\s*(-?[\d.]+)px\)\s*scale\((-?[\d.]+)\)/);
    return match
      ? { panX: Number(match[1]) || 0, panY: Number(match[2]) || 0, zoom: Number(match[3]) || 1 }
      : { panX: 0, panY: 0, zoom: 1 };
  }

  function hasValidGrid(value: LocalChangeDiagnostics | null): value is LocalChangeDiagnostics {
    return !!value
      && value.available
      && value.rows > 0
      && value.columns > 0
      && value.cells.length === value.rows
      && value.cells.every((row) => row.length === value.columns);
  }

  function measureViewport(): void {
    if (!viewport) return;
    const bounds = viewport.getBoundingClientRect();
    viewportWidth = Math.max(0, bounds.width);
    viewportHeight = Math.max(0, bounds.height);
  }

  function selectedLoaded(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    selectedNaturalWidth = image.naturalWidth;
    selectedNaturalHeight = image.naturalHeight;
    measureViewport();
    onselectedload?.(event);
  }

  function referenceLoaded(event: Event): void {
    onreferenceload?.(event);
  }

  let gridDetailSize = $derived(localChangeGridSizeForLevel(gridDetailLevel));
  let displayGrid = $derived.by(() => {
    if (!hasValidGrid(diagnostics)) return null;
    return aggregateLocalChangeGrid(diagnostics.cells, gridDetailSize, gridDetailSize) ?? {
      rows: diagnostics.rows,
      columns: diagnostics.columns,
      cells: diagnostics.cells.map((row) => row.map(clampLocalChangePercent)),
    };
  });
  let gridCells = $derived(displayGrid?.cells.flat() ?? []);
  let gridRows = $derived(displayGrid?.rows ?? 1);
  let gridColumns = $derived(displayGrid?.columns ?? 1);
  let gridDetailLabel = $derived(
    displayGrid ? `${displayGrid.columns}×${displayGrid.rows}` : `${gridDetailSize}×${gridDetailSize}`,
  );

  let imageRect = $derived.by((): ImageRect | null => {
    if (
      viewportWidth <= 0
      || viewportHeight <= 0
      || selectedNaturalWidth <= 0
      || selectedNaturalHeight <= 0
    ) return null;

    const fit = Math.min(
      viewportWidth / selectedNaturalWidth,
      viewportHeight / selectedNaturalHeight,
    );
    const { panX, panY, zoom } = parseTransform(transform);
    const drawWidth = selectedNaturalWidth * fit * zoom;
    const drawHeight = selectedNaturalHeight * fit * zoom;
    return {
      x: (viewportWidth - drawWidth) / 2 + panX,
      y: (viewportHeight - drawHeight) / 2 + panY,
      width: drawWidth,
      height: drawHeight,
    };
  });

  let labelsVisible = $derived.by(() => {
    if (!imageRect || gridCells.length === 0) return false;
    return canRenderLocalChangeLabel({
      cellWidth: imageRect.width / gridColumns,
      cellHeight: imageRect.height / gridRows,
      measuredLabelWidth: LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
      fontSize: LOCAL_CHANGE_LABEL_FONT_PX,
    });
  });

  let gridStyle = $derived.by(() => {
    const rect = imageRect ?? { x: 0, y: 0, width: 0, height: 0 };
    return [
      `left:${rect.x}px`,
      `top:${rect.y}px`,
      `width:${rect.width}px`,
      `height:${rect.height}px`,
      `grid-template-columns:repeat(${gridColumns},minmax(0,1fr))`,
      `grid-template-rows:repeat(${gridRows},minmax(0,1fr))`,
      `visibility:${imageRect ? 'visible' : 'hidden'}`,
    ].join(';');
  });

  onMount(() => {
    onviewport?.(viewport);
    measureViewport();
    const observer = viewport && typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(measureViewport)
      : null;
    if (viewport) observer?.observe(viewport);
    return () => {
      observer?.disconnect();
      if (hoverTimer) clearTimeout(hoverTimer);
      onviewport?.(null);
    };
  });
</script>

<div
  class="v2-compare-overlay mode-local-changes"
  class:controls-open={controlsOpen}
  bind:this={viewport}
  role="group"
  aria-label="Localized change comparison"
  onmouseenter={showControls}
  onmouseleave={hideControlsSoon}
  onfocusin={showControls}
  onfocusout={hideControlsSoon}
>
  <img
    class="v2-local-change-image"
    style:transform={transform}
    src={selectedSrc}
    alt={selectedLabel}
    onload={selectedLoaded}
    onerror={onselectederror}
  >

  {#if gridCells.length > 0}
    <LocalChangeGrid
      cells={gridCells}
      style={gridStyle}
      {labelsVisible}
      {highlightColor}
      {emphasis}
      {minimumDifference}
    />
  {/if}

  <img
    class="v2-local-change-reference-source"
    src={referenceSrc}
    alt={referenceLabel}
    onload={referenceLoaded}
    onerror={onreferenceerror}
  >

  <LocalChangeControls
    bind:highlightColor
    bind:highlightColorPosition
    bind:gridDetailLevel
    {gridDetailLabel}
    bind:minimumDifference
    bind:emphasis
  />

  <LocalChangeDiagnosticStatus {diagnostics} {loading} {error} />
</div>

<style>
  .mode-local-changes {
    overflow:hidden;
  }
  .v2-local-change-image {
    position:absolute;
    inset:0;
    width:100%;
    height:100%;
    object-fit:contain;
    transform-origin:center center;
    will-change:transform;
    user-select:none;
    pointer-events:none;
  }
  .v2-local-change-reference-source {
    position:absolute;
    width:1px;
    height:1px;
    opacity:0;
    pointer-events:none;
  }
</style>

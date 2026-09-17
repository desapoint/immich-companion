<script lang="ts">
  import { onMount } from 'svelte';
  import type { LocalChangeDiagnostics } from '../data/localChangeDiagnostics';
  import V2RangeSlider from './V2RangeSlider.svelte';
  import {
    LOCAL_CHANGE_LABEL_FONT_PX,
    LOCAL_CHANGE_LABEL_MAX_WIDTH_PX,
    canRenderLocalChangeLabel,
    clampLocalChangePercent,
    localChangeFillAlpha,
    localChangeFillColor,
    localChangePassesVisibilityThreshold,
  } from './localChangeVisualization';

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

  function sourceLabel(source: LocalChangeDiagnostics['source']): string {
    if (source === 'original') return 'Original detail sample';
    if (source === 'transcoded') return 'Full-size conversion detail sample';
    if (source === 'preview') return 'Preview fallback detail sample';
    return 'Detail sample';
  }

  function diagnosticSummary(value: LocalChangeDiagnostics): string {
    const changed = value.changedPercent?.toFixed(2) ?? '—';
    const coherent = value.coherentChangedPercent?.toFixed(2) ?? '—';
    const largest = value.largestChangedRegionPercent?.toFixed(2) ?? '—';
    const regions = value.substantialRegionCount ?? '—';
    return `Changed ${changed}% · coherent ${coherent}% · largest region ${largest}% · ${regions} regions`;
  }

  let gridCells = $derived.by(() => {
    if (!hasValidGrid(diagnostics)) return [];
    return diagnostics.cells.flat().map(clampLocalChangePercent);
  });

  let gridRows = $derived(hasValidGrid(diagnostics) ? diagnostics.rows : 1);
  let gridColumns = $derived(hasValidGrid(diagnostics) ? diagnostics.columns : 1);

  let imageRect = $derived.by((): ImageRect | null => {
    if (
      viewportWidth <= 0
      || viewportHeight <= 0
      || selectedNaturalWidth <= 0
      || selectedNaturalHeight <= 0
    ) {
      return null;
    }

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
    <div
      class="v2-local-change-grid"
      class:labels-visible={labelsVisible}
      style={gridStyle}
      aria-hidden="true"
    >
      {#each gridCells as changed}
        <div
          class="v2-local-change-cell"
          style:background-color={localChangeFillColor(
            highlightColor,
            localChangeFillAlpha(changed, emphasis, minimumDifference),
          )}
        >
          <span
            class="v2-local-change-label"
            class:difference-visible={localChangePassesVisibilityThreshold(changed, minimumDifference)}
          >
            {Math.round(changed)}%
          </span>
        </div>
      {/each}
    </div>
  {/if}

  <img
    class="v2-local-change-reference-source"
    src={referenceSrc}
    alt={referenceLabel}
    onload={referenceLoaded}
    onerror={onreferenceerror}
  >

  <div class="v2-compare-floating-controls v2-compare-hover v2-local-change-controls">
    <V2RangeSlider
      label="Color"
      min={0}
      max={255}
      bind:value={highlightColor}
      bind:numericValue={highlightColorPosition}
      track="spectrum"
      width={160}
      swatch={highlightColor}
      ariaLabel="Local changes highlight color"
    />
    <V2RangeSlider
      label="Minimum difference visible"
      min={0}
      max={100}
      step={1}
      bind:value={minimumDifference}
      suffix="%"
      track="fill"
      width={112}
      ariaLabel="Minimum visible local difference"
    />
    <V2RangeSlider
      label="Minimum highlight intensity"
      min={0}
      max={100}
      step={1}
      bind:value={emphasis}
      suffix="%"
      track="fill"
      width={112}
      ariaLabel="Minimum highlight intensity"
    />
  </div>

  {#if loading}
    <div class="v2-local-change-status" role="status">Calculating localized changes…</div>
  {:else if error}
    <div class="v2-local-change-status" role="alert">{error}</div>
  {:else if diagnostics?.available}
    <div class="v2-local-change-note">
      {diagnosticSummary(diagnostics)} · {sourceLabel(diagnostics.source)} · validator evidence
    </div>
  {:else}
    <div class="v2-local-change-status">Localized detail evidence is unavailable for this pair.</div>
  {/if}
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
  .v2-local-change-grid {
    position:absolute;
    z-index:2;
    display:grid;
    pointer-events:none;
    contain:layout paint style;
  }
  .v2-local-change-cell {
    position:relative;
    min-width:0;
    min-height:0;
    overflow:hidden;
    box-shadow:inset 0 0 0 .5px rgba(255,255,255,.24);
  }
  .v2-local-change-label {
    position:absolute;
    left:50%;
    top:50%;
    transform:translate(-50%, -50%);
    visibility:hidden;
    color:#fff;
    font:700 12px/1.2 system-ui, sans-serif;
    white-space:nowrap;
    text-shadow:
      -1px -1px 0 rgba(0,0,0,.9),
      1px -1px 0 rgba(0,0,0,.9),
      -1px 1px 0 rgba(0,0,0,.9),
      1px 1px 0 rgba(0,0,0,.9),
      0 1px 2px rgba(0,0,0,.95);
    pointer-events:none;
  }
  .v2-local-change-grid.labels-visible .v2-local-change-label.difference-visible {
    visibility:visible;
  }
  .v2-local-change-reference-source {
    position:absolute;
    width:1px;
    height:1px;
    opacity:0;
    pointer-events:none;
  }
  .v2-local-change-controls {
    width:min(760px, calc(100% - 28px));
    min-width:0;
    max-width:calc(100% - 28px);
    flex-wrap:wrap;
    justify-content:center;
    border-radius:14px;
    padding:9px 12px;
    box-sizing:border-box;
  }
  .v2-local-change-note,
  .v2-local-change-status {
    position:absolute;
    left:50%;
    bottom:14px;
    z-index:8;
    transform:translateX(-50%);
    max-width:calc(100% - 24px);
    border:1px solid #385467;
    border-radius:999px;
    padding:6px 10px;
    background:rgba(0,0,0,.84);
    color:#e8f8ff;
    font-size:11px;
    text-align:center;
    pointer-events:none;
  }
</style>

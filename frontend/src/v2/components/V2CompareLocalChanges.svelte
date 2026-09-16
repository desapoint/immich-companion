<script lang="ts">
  import type { LocalChangeDiagnostics } from '../data/localChangeDiagnostics';

  let {
    selectedSrc,
    referenceSrc,
    selectedLabel,
    referenceLabel,
    transform,
    diagnostics = null,
    loading = false,
    error = '',
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
    onselectedload?: (event: Event) => void;
    onreferenceload?: (event: Event) => void;
    onselectederror?: () => void;
    onreferenceerror?: () => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let canvas = $state<HTMLCanvasElement | null>(null);
  let selectedImage = $state<HTMLImageElement | null>(null);
  let referenceImage = $state<HTMLImageElement | null>(null);
  let renderFrame: number | null = null;

  function parseTransform(value: string): { panX: number; panY: number; zoom: number } {
    const match = value.match(/translate\((-?[\d.]+)px,\s*(-?[\d.]+)px\)\s*scale\((-?[\d.]+)\)/);
    return match
      ? { panX: Number(match[1]) || 0, panY: Number(match[2]) || 0, zoom: Number(match[3]) || 1 }
      : { panX: 0, panY: 0, zoom: 1 };
  }

  function imageRect(
    image: HTMLImageElement,
    width: number,
    height: number,
    panX: number,
    panY: number,
    zoom: number,
  ): { x: number; y: number; width: number; height: number } {
    const fit = Math.min(width / image.naturalWidth, height / image.naturalHeight);
    const drawWidth = image.naturalWidth * fit * zoom;
    const drawHeight = image.naturalHeight * fit * zoom;
    return {
      x: (width - drawWidth) / 2 + panX,
      y: (height - drawHeight) / 2 + panY,
      width: drawWidth,
      height: drawHeight,
    };
  }

  function drawGrid(
    context: CanvasRenderingContext2D,
    rect: { x: number; y: number; width: number; height: number },
    value: LocalChangeDiagnostics,
  ): void {
    if (!value.available || value.rows < 1 || value.columns < 1) return;
    if (value.cells.length !== value.rows || value.cells.some((row) => row.length !== value.columns)) return;
    const cellWidth = rect.width / value.columns;
    const cellHeight = rect.height / value.rows;
    const fontSize = Math.max(7, Math.min(12, cellWidth * 0.32, cellHeight * 0.3));

    context.save();
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.font = `700 ${fontSize}px system-ui, sans-serif`;
    context.lineWidth = 1;

    for (let row = 0; row < value.rows; row += 1) {
      for (let column = 0; column < value.columns; column += 1) {
        const changed = Math.max(0, Math.min(100, value.cells[row]?.[column] ?? 0));
        const x = rect.x + column * cellWidth;
        const y = rect.y + row * cellHeight;
        const alpha = changed <= 0 ? 0 : 0.08 + (changed / 100) * 0.5;

        if (alpha > 0) {
          context.fillStyle = `rgba(0, 220, 255, ${alpha})`;
          context.fillRect(x, y, cellWidth, cellHeight);
        }
        context.strokeStyle = 'rgba(255, 255, 255, 0.24)';
        context.strokeRect(x + 0.5, y + 0.5, Math.max(0, cellWidth - 1), Math.max(0, cellHeight - 1));

        context.save();
        context.beginPath();
        context.rect(x, y, cellWidth, cellHeight);
        context.clip();
        const label = `${Math.round(changed)}%`;
        context.lineWidth = 2.5;
        context.strokeStyle = 'rgba(0, 0, 0, 0.82)';
        context.strokeText(label, x + cellWidth / 2, y + cellHeight / 2);
        context.fillStyle = '#fff';
        context.fillText(label, x + cellWidth / 2, y + cellHeight / 2);
        context.restore();
      }
    }
    context.restore();
  }

  function render(): void {
    if (!viewport || !canvas || !selectedImage) return;
    if (!selectedImage.complete || !selectedImage.naturalWidth || !selectedImage.naturalHeight) return;

    const bounds = viewport.getBoundingClientRect();
    const width = Math.max(1, Math.round(bounds.width));
    const height = Math.max(1, Math.round(bounds.height));
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    const context = canvas.getContext('2d');
    if (!context) return;

    context.clearRect(0, 0, width, height);
    const { panX, panY, zoom } = parseTransform(transform);
    const rect = imageRect(selectedImage, width, height, panX, panY, zoom);
    context.drawImage(selectedImage, rect.x, rect.y, rect.width, rect.height);
    if (diagnostics) drawGrid(context, rect, diagnostics);
  }

  function scheduleRender(): void {
    if (renderFrame !== null) cancelAnimationFrame(renderFrame);
    renderFrame = requestAnimationFrame(() => {
      renderFrame = null;
      render();
    });
  }

  function selectedLoaded(event: Event): void {
    onselectedload?.(event);
    scheduleRender();
  }

  function referenceLoaded(event: Event): void {
    onreferenceload?.(event);
    scheduleRender();
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

  $effect(() => {
    onviewport?.(viewport);
    if (!viewport) return () => onviewport?.(null);
    const observer = new ResizeObserver(scheduleRender);
    observer.observe(viewport);
    scheduleRender();
    return () => {
      observer.disconnect();
      if (renderFrame !== null) cancelAnimationFrame(renderFrame);
      onviewport?.(null);
    };
  });

  $effect(() => {
    selectedSrc;
    referenceSrc;
    transform;
    diagnostics;
    loading;
    error;
    scheduleRender();
  });
</script>

<div
  class="v2-compare-overlay mode-local-changes"
  bind:this={viewport}
  role="group"
  aria-label="Localized change comparison"
>
  <canvas bind:this={canvas} class="v2-local-change-canvas" aria-label="Selected image with localized validation grid"></canvas>
  <img bind:this={selectedImage} class="v2-local-change-source" src={selectedSrc} alt={selectedLabel} onload={selectedLoaded} onerror={onselectederror}>
  <img bind:this={referenceImage} class="v2-local-change-source" src={referenceSrc} alt={referenceLabel} onload={referenceLoaded} onerror={onreferenceerror}>

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
  .v2-local-change-canvas {
    position:absolute;
    inset:0;
    width:100%;
    height:100%;
    display:block;
    pointer-events:none;
  }
  .v2-local-change-source {
    position:absolute;
    width:1px;
    height:1px;
    opacity:0;
    pointer-events:none;
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

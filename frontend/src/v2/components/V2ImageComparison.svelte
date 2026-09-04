<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2Checkbox from './V2Checkbox.svelte';
  import V2RangeSlider from './V2RangeSlider.svelte';
  import V2Segmented from './V2Segmented.svelte';

  export type ComparisonMode = 'Side by side' | 'Swipe' | 'Transparency' | 'Difference';

  let {
    selectedSrc,
    referenceSrc,
    differenceSrc,
    selectedLabel = 'Selected image',
    referenceLabel = 'Reference / keeper candidate',
    mode = $bindable<ComparisonMode>('Side by side'),
    opacity = $bindable(50),
    split = $bindable(50),
    diffHue = $bindable(190),
    diffContrast = $bindable(180),
    diffBinary = $bindable(true),
  }: {
    selectedSrc: string;
    referenceSrc: string;
    differenceSrc: string;
    selectedLabel?: string;
    referenceLabel?: string;
    mode?: ComparisonMode;
    opacity?: number;
    split?: number;
    diffHue?: number;
    diffContrast?: number;
    diffBinary?: boolean;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let selectedImage = $state<HTMLImageElement | null>(null);
  let zoom = $state(1);
  let panX = $state(0);
  let panY = $state(0);
  let dragging = $state(false);
  let dragPointer = $state<number | null>(null);
  let lastX = $state(0);
  let lastY = $state(0);
  let swiping = $state(false);
  let swipePointer = $state<number | null>(null);
  let controlsOpen = $state(false);
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;

  const transform = $derived(`translate(${panX}px, ${panY}px) scale(${zoom})`);

  function differenceColor(value: number): string {
    const clamped = Math.max(0, Math.min(400, value));
    if (clamped <= 360) return `hsl(${clamped} 90% 58%)`;
    const white = ((clamped - 360) / 40) * 100;
    return `color-mix(in srgb, hsl(0 90% 58%) ${100 - white}%, white ${white}%)`;
  }

  function differenceValueLabel(value: number): string {
    if (value <= 360) return `${value}°`;
    const white = Math.round(((value - 360) / 40) * 100);
    return white >= 100 ? 'White' : `${white}% white`;
  }

  function naturalSize() {
    return {
      width: selectedImage?.naturalWidth || 800,
      height: selectedImage?.naturalHeight || 600,
    };
  }

  function renderedSize() {
    if (!viewport) return null;
    const rect = viewport.getBoundingClientRect();
    const image = naturalSize();
    if (!rect.width || !rect.height || !image.width || !image.height) return null;
    const fit = Math.min(rect.width / image.width, rect.height / image.height);
    return {
      viewportW: rect.width,
      viewportH: rect.height,
      imageW: image.width * fit * zoom,
      imageH: image.height * fit * zoom,
    };
  }

  function clampPan() {
    const size = renderedSize();
    if (!size) return;
    const maxX = Math.abs(size.imageW - size.viewportW) / 2;
    const maxY = Math.abs(size.imageH - size.viewportH) / 2;
    panX = Math.max(-maxX, Math.min(maxX, panX));
    panY = Math.max(-maxY, Math.min(maxY, panY));
  }

  function setZoom(next: number, anchorX: number | null = null, anchorY: number | null = null) {
    const old = zoom;
    const nextZoom = Math.max(0.1, Math.min(8, next));
    if (anchorX !== null && anchorY !== null && old !== nextZoom) {
      const ratio = nextZoom / old;
      panX = anchorX - (anchorX - panX) * ratio;
      panY = anchorY - (anchorY - panY) * ratio;
    }
    zoom = nextZoom;
    if (Math.abs(zoom - 1) < 0.0001) {
      panX = 0;
      panY = 0;
    }
    clampPan();
  }

  function fit() {
    zoom = 1;
    panX = 0;
    panY = 0;
  }

  function actual() {
    if (!viewport) return fit();
    const rect = viewport.getBoundingClientRect();
    const image = naturalSize();
    if (!rect.width || !rect.height || !image.width || !image.height) return fit();
    const fitScale = Math.min(rect.width / image.width, rect.height / image.height) || 1;
    zoom = Math.max(0.1, Math.min(8, 1 / fitScale));
    panX = 0;
    panY = 0;
  }

  function changeMode(next: string) {
    mode = next as ComparisonMode;
    requestAnimationFrame(fit);
  }

  function shouldIgnore(target: EventTarget | null) {
    return target instanceof Element && !!target.closest('button,input,label,.v2-compare-swipe-hit,.v2-compare-floating-controls');
  }

  function panStart(event: PointerEvent) {
    if (shouldIgnore(event.target)) return;
    event.preventDefault();
    dragging = true;
    dragPointer = event.pointerId;
    lastX = event.clientX;
    lastY = event.clientY;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
  }

  function panMove(event: PointerEvent) {
    if (!dragging || dragPointer !== event.pointerId) return;
    event.preventDefault();
    panX += event.clientX - lastX;
    panY += event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    clampPan();
  }

  function panEnd(event: PointerEvent) {
    if (!dragging || dragPointer !== event.pointerId) return;
    dragging = false;
    dragPointer = null;
    try { (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId); } catch {}
  }

  function wheel(event: WheelEvent) {
    event.preventDefault();
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const anchorX = event.clientX - rect.left - rect.width / 2;
    const anchorY = event.clientY - rect.top - rect.height / 2;
    setZoom(zoom * (event.deltaY < 0 ? 1.12 : 1 / 1.12), anchorX, anchorY);
  }

  function updateSwipe(event: PointerEvent) {
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();
    if (!rect.width) return;
    split = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
  }

  function swipeStart(event: PointerEvent) {
    if (mode !== 'Swipe') return;
    event.preventDefault();
    event.stopPropagation();
    swiping = true;
    swipePointer = event.pointerId;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
    updateSwipe(event);
  }

  function swipeMove(event: PointerEvent) {
    if (!swiping || swipePointer !== event.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    updateSwipe(event);
  }

  function swipeEnd(event: PointerEvent) {
    if (!swiping || swipePointer !== event.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    swiping = false;
    swipePointer = null;
    try { (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId); } catch {}
  }

  function showControls() {
    if (hoverTimer) clearTimeout(hoverTimer);
    controlsOpen = true;
  }

  function hideControlsSoon() {
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => (controlsOpen = false), 80);
  }

  $effect(() => {
    const currentMode = mode;
    void currentMode;
    requestAnimationFrame(fit);
  });
</script>

<svelte:window onresize={() => requestAnimationFrame(fit)} />

<div class="v2-compare-component">
  <div class="v2-compare-component-tools">
    <V2Segmented items={['Side by side','Swipe','Transparency','Difference']} active={mode} onselect={changeMode} ariaLabel="Comparison mode" />
    <div class="v2-compare-zoom-tools">
      <V2Button onclick={() => setZoom(zoom / 1.25)} title="Zoom out">−</V2Button>
      <span class="v2-zoom-readout">{Math.round(zoom * 100)}%</span>
      <V2Button onclick={() => setZoom(zoom * 1.25)} title="Zoom in">+</V2Button>
      <V2Button onclick={fit} title="Fit image to comparison zone">Fit</V2Button>
      <V2Button onclick={actual} title="Show image at actual pixel size">1:1</V2Button>
    </div>
  </div>

  <div
    class="v2-compare-stage"
    class:single={mode !== 'Side by side'}
    class:panning={dragging}
    onpointerdown={panStart}
    onpointermove={panMove}
    onpointerup={panEnd}
    onpointercancel={panEnd}
    onwheel={wheel}
  >
    {#if mode === 'Side by side'}
      <div class="v2-compare-pane" bind:this={viewport}>
        <span class="v2-compare-label">{selectedLabel}</span>
        <div class="v2-compare-transform" style={`transform:${transform}`}>
          <img bind:this={selectedImage} src={selectedSrc} alt={selectedLabel} onload={() => requestAnimationFrame(fit)}>
        </div>
      </div>
      <div class="v2-compare-pane reference">
        <span class="v2-compare-label">{referenceLabel}</span>
        <div class="v2-compare-transform" style={`transform:${transform}`}><img src={referenceSrc} alt={referenceLabel}></div>
      </div>
    {:else}
      <div
        class={`v2-compare-overlay mode-${mode.toLowerCase().replaceAll(' ','-')}`}
        class:controls-open={controlsOpen}
        bind:this={viewport}
        tabindex="0"
        onmouseenter={showControls}
        onmouseleave={hideControlsSoon}
        onfocusin={showControls}
        onfocusout={hideControlsSoon}
      >
        {#if mode === 'Difference'}
          <div class="v2-compare-transform" style={`transform:${transform}`}><img bind:this={selectedImage} src={differenceSrc} alt="Generated difference preview"></div>
          <div class="v2-compare-floating-controls v2-difference-controls" onmouseenter={showControls} onmouseleave={hideControlsSoon}>
            <V2RangeSlider label="Color" min={0} max={400} bind:value={diffHue} track="spectrum" width={160} swatch={differenceColor(diffHue)} valueLabel={differenceValueLabel(diffHue)} ariaLabel="Difference highlight color" />
            <V2Checkbox label="Two colors only" checked={diffBinary} onchange={(checked) => (diffBinary = checked)} />
            {#if !diffBinary}<V2RangeSlider label="Contrast" min={50} max={300} bind:value={diffContrast} suffix="%" track="fill" width={112} ariaLabel="Difference contrast" />{/if}
          </div>
          <div class="v2-difference-note">Black = same · color intensity = difference amount</div>
        {:else}
          <div class="v2-compare-layer"><div class="v2-compare-transform" style={`transform:${transform}`}><img src={referenceSrc} alt={referenceLabel}></div></div>
          <div class="v2-compare-layer top" style={mode === 'Transparency' ? `opacity:${opacity/100}` : `clip-path:inset(0 ${100-split}% 0 0)`}><div class="v2-compare-transform" style={`transform:${transform}`}><img bind:this={selectedImage} src={selectedSrc} alt={selectedLabel}></div></div>
          {#if mode === 'Swipe'}
            <div class="v2-compare-split-line" style={`left:${split}%`}></div>
            <div class="v2-compare-split-handle" style={`left:${split}%`}>↔</div>
            <div class="v2-compare-swipe-hit" style={`left:${split}%`} onpointerdown={swipeStart} onpointermove={swipeMove} onpointerup={swipeEnd} onpointercancel={swipeEnd}></div>
          {:else if mode === 'Transparency'}
            <div class="v2-compare-floating-controls v2-compare-hover" onmouseenter={showControls} onmouseleave={hideControlsSoon}>
              <V2RangeSlider label="Transparency" min={0} max={100} bind:value={opacity} suffix="%" track="fill" width={160} ariaLabel="Overlay transparency" />
            </div>
          {/if}
        {/if}
        <div class="v2-compare-legend"><span>Reference</span><span>Selected</span></div>
      </div>
    {/if}
  </div>
</div>
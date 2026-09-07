<script lang="ts">
  import V2RangeSlider from './V2RangeSlider.svelte';
  import V2Toggle from './V2Toggle.svelte';

  let {
    selectedSrc,
    referenceSrc,
    selectedLabel,
    referenceLabel,
    transform,
    diffHue = $bindable(190),
    diffContrast = $bindable(180),
    diffBinary = $bindable(true),
    diffTolerance = $bindable(8),
    onselectedload,
    onreferenceload,
    onviewport,
  }: {
    selectedSrc: string;
    referenceSrc: string;
    selectedLabel: string;
    referenceLabel: string;
    transform: string;
    diffHue?: number;
    diffContrast?: number;
    diffBinary?: boolean;
    diffTolerance?: number;
    onselectedload?: (event: Event) => void;
    onreferenceload?: (event: Event) => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let canvas = $state<HTMLCanvasElement | null>(null);
  let selectedImage = $state<HTMLImageElement | null>(null);
  let referenceImage = $state<HTMLImageElement | null>(null);
  let controlsOpen = $state(false);
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;
  let renderFrame: number | null = null;
  let diffColor = $state('#00FFFF');

  const safeTolerance = $derived(Math.max(0, Math.min(50, diffTolerance)));
  const continuousContrast = $derived(Math.max(50, Math.min(300, diffContrast)));

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

  function hslToRgb(hue: number): [number, number, number] {
    const h = ((hue % 360) + 360) % 360;
    const s = 0.9;
    const l = 0.58;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h / 60) % 2 - 1));
    const m = l - c / 2;
    let r = 0, g = 0, b = 0;
    if (h < 60) [r, g, b] = [c, x, 0];
    else if (h < 120) [r, g, b] = [x, c, 0];
    else if (h < 180) [r, g, b] = [0, c, x];
    else if (h < 240) [r, g, b] = [0, x, c];
    else if (h < 300) [r, g, b] = [x, 0, c];
    else [r, g, b] = [c, 0, x];
    return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
  }

  function drawContained(
    context: CanvasRenderingContext2D,
    image: HTMLImageElement,
    width: number,
    height: number,
    panX: number,
    panY: number,
    zoom: number,
  ): void {
    if (!image.naturalWidth || !image.naturalHeight) return;
    const fit = Math.min(width / image.naturalWidth, height / image.naturalHeight);
    const drawWidth = image.naturalWidth * fit * zoom;
    const drawHeight = image.naturalHeight * fit * zoom;
    const x = (width - drawWidth) / 2 + panX;
    const y = (height - drawHeight) / 2 + panY;
    context.drawImage(image, x, y, drawWidth, drawHeight);
  }

  function renderDifference(): void {
    if (!viewport || !canvas || !selectedImage || !referenceImage) return;
    if (!selectedImage.complete || !referenceImage.complete || !selectedImage.naturalWidth || !referenceImage.naturalWidth) return;

    const rect = viewport.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;

    const selectedSurface = document.createElement('canvas');
    const referenceSurface = document.createElement('canvas');
    selectedSurface.width = referenceSurface.width = width;
    selectedSurface.height = referenceSurface.height = height;
    const selectedContext = selectedSurface.getContext('2d', { willReadFrequently: true });
    const referenceContext = referenceSurface.getContext('2d', { willReadFrequently: true });
    const outputContext = canvas.getContext('2d');
    if (!selectedContext || !referenceContext || !outputContext) return;

    const { panX, panY, zoom } = parseTransform(transform);
    drawContained(referenceContext, referenceImage, width, height, panX, panY, zoom);
    drawContained(selectedContext, selectedImage, width, height, panX, panY, zoom);

    try {
      const selectedPixels = selectedContext.getImageData(0, 0, width, height);
      const referencePixels = referenceContext.getImageData(0, 0, width, height);
      const output = outputContext.createImageData(width, height);
      const threshold = safeTolerance / 100 * 255;
      const contrast = continuousContrast / 100;
      const [highlightR, highlightG, highlightB] = hslToRgb(diffHue);

      for (let index = 0; index < output.data.length; index += 4) {
        const selectedPresent = selectedPixels.data[index + 3] > 0;
        const referencePresent = referencePixels.data[index + 3] > 0;
        if (!selectedPresent && !referencePresent) continue;

        let difference = 255;
        if (selectedPresent && referencePresent) {
          difference = Math.max(
            Math.abs(selectedPixels.data[index] - referencePixels.data[index]),
            Math.abs(selectedPixels.data[index + 1] - referencePixels.data[index + 1]),
            Math.abs(selectedPixels.data[index + 2] - referencePixels.data[index + 2]),
          );
        }

        if (diffBinary) {
          const changed = !selectedPresent || !referencePresent || difference >= threshold;
          output.data[index] = changed ? highlightR : 0;
          output.data[index + 1] = changed ? highlightG : 0;
          output.data[index + 2] = changed ? highlightB : 0;
          output.data[index + 3] = 255;
          continue;
        }

        if (selectedPresent && referencePresent && difference < threshold) {
          output.data[index + 3] = 255;
          continue;
        }
        const intensity = !selectedPresent || !referencePresent
          ? 1
          : Math.max(0, Math.min(1, ((difference - threshold) / Math.max(1, 255 - threshold)) * contrast));
        output.data[index] = Math.round(highlightR * intensity);
        output.data[index + 1] = Math.round(highlightG * intensity);
        output.data[index + 2] = Math.round(highlightB * intensity);
        output.data[index + 3] = 255;
      }
      outputContext.clearRect(0, 0, width, height);
      outputContext.putImageData(output, 0, 0);
    } catch {
      outputContext.clearRect(0, 0, width, height);
    }
  }

  function scheduleRender(): void {
    if (renderFrame !== null) cancelAnimationFrame(renderFrame);
    renderFrame = requestAnimationFrame(() => {
      renderFrame = null;
      renderDifference();
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
    diffHue;
    diffBinary;
    safeTolerance;
    continuousContrast;
    scheduleRender();
  });
</script>

<div
  class="v2-compare-overlay mode-difference"
  class:controls-open={controlsOpen}
  bind:this={viewport}
  role="group"
  aria-label="Difference comparison"
  onmouseenter={showControls}
  onmouseleave={hideControlsSoon}
  onfocusin={showControls}
  onfocusout={hideControlsSoon}
>
  <canvas bind:this={canvas} class="v2-difference-canvas" aria-hidden="true"></canvas>
  <img bind:this={referenceImage} class="v2-difference-source" src={referenceSrc} alt={referenceLabel} onload={referenceLoaded}>
  <img bind:this={selectedImage} class="v2-difference-source" src={selectedSrc} alt={selectedLabel} onload={selectedLoaded}>

  <div class="v2-compare-floating-controls v2-difference-controls">
    <V2RangeSlider
      label="Color"
      min={0}
      max={400}
      bind:value={diffColor}
      bind:numericValue={diffHue}
      track="spectrum"
      width={160}
      swatch={diffColor}
      ariaLabel="Difference highlight color"
    />
    <V2Toggle label="Two colors only" checked={diffBinary} onchange={(checked) => (diffBinary = checked)} />
    <V2RangeSlider
      label="Tolerance"
      min={0}
      max={50}
      step={1}
      bind:value={diffTolerance}
      suffix="%"
      track="fill"
      width={112}
      ariaLabel="Difference tolerance"
    />
    <V2RangeSlider
      label="Contrast"
      min={50}
      max={300}
      bind:value={diffContrast}
      suffix="%"
      track="fill"
      width={112}
      disabled={diffBinary}
      ariaLabel="Difference contrast"
    />
  </div>
  <div class="v2-difference-note">Lower tolerance reveals subtler changes · black = same</div>
</div>

<style>
  .v2-difference-canvas {
    position:absolute;
    inset:0;
    width:100%;
    height:100%;
    display:block;
    pointer-events:none;
  }
  .v2-difference-source {
    position:absolute;
    width:1px;
    height:1px;
    opacity:0;
    pointer-events:none;
  }
</style>

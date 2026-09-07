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
  let controlsOpen = $state(false);
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;
  let diffColor = $state('#00FFFF');

  const safeTolerance = $derived(Math.max(1, Math.min(50, diffTolerance)));
  const binaryContrast = $derived(Math.round(700 + safeTolerance * 18));
  const binaryBrightness = $derived(Math.max(0.55, 1.55 - safeTolerance / 55));
  const continuousContrast = $derived(Math.max(50, Math.min(300, diffContrast)));
  const differenceFilter = $derived(diffBinary
    ? `grayscale(1) brightness(${binaryBrightness}) contrast(${binaryContrast}%) sepia(1) saturate(8) hue-rotate(${diffHue - 40}deg)`
    : `grayscale(1) brightness(${Math.max(0.7, 1.25 - safeTolerance / 100)}) contrast(${continuousContrast}%) sepia(1) saturate(8) hue-rotate(${diffHue - 40}deg)`);

  function showControls(): void {
    if (hoverTimer) clearTimeout(hoverTimer);
    controlsOpen = true;
  }

  function hideControlsSoon(): void {
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => (controlsOpen = false), 80);
  }

  $effect(() => {
    onviewport?.(viewport);
    return () => onviewport?.(null);
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
  <div class="v2-compare-layer">
    <div class="v2-compare-transform" style={`transform:${transform}`}>
      <img src={referenceSrc} alt={referenceLabel} onload={onreferenceload}>
    </div>
  </div>
  <div class="v2-compare-layer top v2-difference-selected">
    <div class="v2-compare-transform" style={`transform:${transform}`}>
      <img
        src={selectedSrc}
        alt={selectedLabel}
        onload={onselectedload}
        style={`filter:${differenceFilter}`}
      >
    </div>
  </div>

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
      min={1}
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
  .v2-difference-selected img {
    mix-blend-mode:difference;
  }
</style>

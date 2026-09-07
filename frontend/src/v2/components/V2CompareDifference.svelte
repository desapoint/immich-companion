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
    onselectedload?: (event: Event) => void;
    onreferenceload?: (event: Event) => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let controlsOpen = $state(false);
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;
  let diffColor = $state('#00FFFF');

  const renderFilter = $derived(diffBinary
    ? 'grayscale(1) brightness(2.2) contrast(1200%)'
    : `grayscale(1) contrast(${diffContrast}%)`);

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
  <div class="v2-difference-stack" style={`filter:${renderFilter}`}>
    <div class="v2-compare-layer">
      <div class="v2-compare-transform" style={`transform:${transform}`}>
        <img src={referenceSrc} alt={referenceLabel} onload={onreferenceload}>
      </div>
    </div>
    <div class="v2-compare-layer top v2-difference-selected">
      <div class="v2-compare-transform" style={`transform:${transform}`}>
        <img src={selectedSrc} alt={selectedLabel} onload={onselectedload}>
      </div>
    </div>
  </div>
  <div class="v2-difference-tint" style={`background:${diffColor}`}></div>

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
  <div class="v2-difference-note">Black = same · color intensity = difference amount</div>
</div>

<style>
  .v2-difference-stack { position:absolute; inset:0; background:#000; isolation:isolate; }
  .v2-difference-selected { mix-blend-mode:difference; }
  .v2-difference-tint { position:absolute; inset:0; z-index:3; mix-blend-mode:multiply; pointer-events:none; }
</style>

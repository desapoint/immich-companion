<script lang="ts">
  import V2RangeSlider from './V2RangeSlider.svelte';
  import V2Toggle from './V2Toggle.svelte';

  let {
    differenceSrc,
    transform,
    diffHue = $bindable(190),
    diffContrast = $bindable(180),
    diffBinary = $bindable(true),
    onimageload,
    onviewport,
  }: {
    differenceSrc: string;
    transform: string;
    diffHue?: number;
    diffContrast?: number;
    diffBinary?: boolean;
    onimageload?: (event: Event) => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let controlsOpen = $state(false);
  let hoverTimer: ReturnType<typeof setTimeout> | undefined;
  let diffColor = $state('#00FFFF');

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
  <div class="v2-compare-transform" style={`transform:${transform}`}>
    <img src={differenceSrc} alt="Generated difference preview" onload={onimageload}>
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

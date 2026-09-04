<script lang="ts">
  import V2Checkbox from './V2Checkbox.svelte';
  import V2RangeSlider from './V2RangeSlider.svelte';
  import { differenceHighlightCss } from '../demo/duplicateVisuals';

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

  function hueLabel(value: number): string {
    if (value <= 360) return `${value}°`;
    const white = Math.round(((value - 360) / 40) * 100);
    return white >= 100 ? 'White' : `${white}% white`;
  }

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
  tabindex="0"
  onmouseenter={showControls}
  onmouseleave={hideControlsSoon}
  onfocusin={showControls}
  onfocusout={hideControlsSoon}
>
  <div class="v2-compare-transform" style={`transform:${transform}`}>
    <img src={differenceSrc} alt="Generated difference preview" onload={onimageload}>
  </div>
  <div class="v2-compare-floating-controls v2-difference-controls" onmouseenter={showControls} onmouseleave={hideControlsSoon}>
    <V2RangeSlider label="Color" min={0} max={400} bind:value={diffHue} track="spectrum" width={160} swatch={differenceHighlightCss(diffHue)} valueLabel={hueLabel(diffHue)} ariaLabel="Difference highlight color" />
    <V2Checkbox label="Two colors only" checked={diffBinary} onchange={(checked) => (diffBinary = checked)} />
    {#if !diffBinary}
      <V2RangeSlider label="Contrast" min={50} max={300} bind:value={diffContrast} suffix="%" track="fill" width={112} ariaLabel="Difference contrast" />
    {/if}
  </div>
  <div class="v2-difference-note">Black = same · color intensity = difference amount</div>
</div>

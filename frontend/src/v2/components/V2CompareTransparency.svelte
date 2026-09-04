<script lang="ts">
  import V2RangeSlider from './V2RangeSlider.svelte';

  let {
    selectedSrc,
    referenceSrc,
    selectedLabel,
    referenceLabel,
    transform,
    opacity = $bindable(50),
    onselectedload,
    onviewport,
  }: {
    selectedSrc: string;
    referenceSrc: string;
    selectedLabel: string;
    referenceLabel: string;
    transform: string;
    opacity?: number;
    onselectedload?: (event: Event) => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
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

  $effect(() => {
    onviewport?.(viewport);
    return () => onviewport?.(null);
  });
</script>

<div
  class="v2-compare-overlay mode-transparency"
  class:controls-open={controlsOpen}
  bind:this={viewport}
  role="group"
  aria-label="Transparency comparison"
  onmouseenter={showControls}
  onmouseleave={hideControlsSoon}
  onfocusin={showControls}
  onfocusout={hideControlsSoon}
>
  <div class="v2-compare-layer"><div class="v2-compare-transform" style={`transform:${transform}`}><img src={referenceSrc} alt={referenceLabel}></div></div>
  <div class="v2-compare-layer top" style={`opacity:${opacity / 100}`}><div class="v2-compare-transform" style={`transform:${transform}`}><img src={selectedSrc} alt={selectedLabel} onload={onselectedload}></div></div>
  <div class="v2-compare-floating-controls v2-compare-hover">
    <V2RangeSlider label="Transparency" min={0} max={100} bind:value={opacity} suffix="%" track="fill" width={160} ariaLabel="Overlay transparency" />
  </div>
  <div class="v2-compare-legend"><span>Reference</span><span>Selected</span></div>
</div>

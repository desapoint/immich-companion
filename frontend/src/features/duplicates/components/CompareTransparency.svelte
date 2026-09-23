<script lang="ts">
  import V2RangeSlider from '../../../lib/components/ui/RangeSlider.svelte';
  import ComparisonImageLayer from './ComparisonImageLayer.svelte';
  import type { ComparisonImagePair } from '../types/comparisonLayer';
  import { createViewportAttachment } from '../state/comparisonViewportAttachment';

  let {
    pair,
    transform,
    opacity = $bindable(50),
    onviewport,
  }: {
    pair: ComparisonImagePair;
    transform: string;
    opacity?: number;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

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

  const viewportAttachment = createViewportAttachment(
    (node) => onviewport?.(node),
    undefined,
    () => {
      if (hoverTimer) clearTimeout(hoverTimer);
      hoverTimer = undefined;
    },
  );
</script>

<div
  class="v2-compare-overlay mode-transparency"
  class:controls-open={controlsOpen}
  {@attach viewportAttachment}
  role="group"
  aria-label="Transparency comparison"
  onmouseenter={showControls}
  onmouseleave={hideControlsSoon}
  onfocusin={showControls}
  onfocusout={hideControlsSoon}
>
  <ComparisonImageLayer image={pair.reference} {transform} />
  <ComparisonImageLayer image={pair.selected} {transform} top opacity={opacity / 100} />
  <div class="v2-compare-floating-controls v2-compare-hover">
    <V2RangeSlider label="Transparency" min={0} max={100} bind:value={opacity} suffix="%" track="fill" width={160} ariaLabel="Overlay transparency" />
  </div>
  <div class="v2-compare-legend"><span>Reference</span><span>Selected</span></div>
</div>

<script lang="ts">
  import { onDestroy } from 'svelte';
  import { FlickerHoldController } from '../state/flickerHold';
  import ComparisonImageLayer from './ComparisonImageLayer.svelte';
  import type { ComparisonImagePair } from '../types/comparisonLayer';
  import { createViewportAttachment } from '../state/comparisonViewportAttachment';

  let {
    pair,
    transform,
    onviewport,
  }: {
    pair: ComparisonImagePair;
    transform: string;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let showReference = $state(false);
  const hold = new FlickerHoldController((active) => (showReference = active));

  function pointerDown(event: PointerEvent): void {
    if (event.button !== 0 || !hold.pointerDown(event.pointerId)) return;
    event.preventDefault();
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
  }

  function pointerEnd(event: PointerEvent): void {
    if (!hold.pointerUp(event.pointerId)) return;
    event.preventDefault();
    event.stopPropagation();
    try { (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId); } catch {}
  }

  function pointerCaptureLost(event: PointerEvent): void {
    hold.pointerUp(event.pointerId);
  }

  function keyDown(event: KeyboardEvent): void {
    if (!hold.keyDown(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
  }

  function keyUp(event: KeyboardEvent): void {
    if (!hold.keyUp(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
  }

  function cancelHold(): void {
    hold.cancel();
  }

  const viewportAttachment = createViewportAttachment((node) => onviewport?.(node));

  onDestroy(cancelHold);
</script>

<svelte:window onblur={cancelHold} />

<div
  class="v2-compare-overlay mode-flicker"
  {@attach viewportAttachment}
  role="group"
  aria-label="Flicker comparison"
>
  <ComparisonImageLayer
    image={pair.selected}
    {transform}
    visible={!showReference}
  />
  <ComparisonImageLayer
    image={pair.reference}
    {transform}
    top
    visible={showReference}
  />

  <div class="v2-compare-floating-controls v2-flicker-controls">
    <button
      type="button"
      class="v2-button v2-flicker-hold"
      data-active={showReference || undefined}
      aria-label="Hold to show reference"
      aria-pressed={showReference}
      onpointerdown={pointerDown}
      onpointerup={pointerEnd}
      onpointercancel={pointerEnd}
      onlostpointercapture={pointerCaptureLost}
      onkeydown={keyDown}
      onkeyup={keyUp}
      onblur={cancelHold}
    >
      Hold to show reference
    </button>
  </div>
  <div class="v2-compare-legend"><span>Selected</span><span>{showReference ? 'Reference visible' : 'Selected visible'}</span></div>
</div>

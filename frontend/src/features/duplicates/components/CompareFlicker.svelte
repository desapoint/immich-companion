<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { FlickerHoldController } from '../state/flickerHold';

  let {
    selectedSrc,
    referenceSrc,
    selectedLabel,
    referenceLabel,
    transform,
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
    onselectedload?: (event: Event) => void;
    onreferenceload?: (event: Event) => void;
    onselectederror?: () => void;
    onreferenceerror?: () => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
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

  onMount(() => {
    onviewport?.(viewport);
    return () => onviewport?.(null);
  });

  onDestroy(cancelHold);
</script>

<svelte:window onblur={cancelHold} />

<div
  class="v2-compare-overlay mode-flicker"
  bind:this={viewport}
  role="group"
  aria-label="Flicker comparison"
>
  <div class="v2-compare-layer">
    <div class="v2-compare-transform" style={`transform:${transform}`}>
      <img src={selectedSrc} alt={selectedLabel} onload={onselectedload} onerror={onselectederror}>
    </div>
  </div>
  <div class="v2-compare-layer top v2-flicker-reference" class:reference-visible={showReference} aria-hidden={!showReference}>
    <div class="v2-compare-transform" style={`transform:${transform}`}>
      <img src={referenceSrc} alt={referenceLabel} onload={onreferenceload} onerror={onreferenceerror}>
    </div>
  </div>

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

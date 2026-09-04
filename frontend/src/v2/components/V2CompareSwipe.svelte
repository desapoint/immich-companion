<script lang="ts">
  let {
    selectedSrc,
    referenceSrc,
    selectedLabel,
    referenceLabel,
    transform,
    split = $bindable(50),
    onselectedload,
    onviewport,
  }: {
    selectedSrc: string;
    referenceSrc: string;
    selectedLabel: string;
    referenceLabel: string;
    transform: string;
    split?: number;
    onselectedload?: (event: Event) => void;
    onviewport?: (node: HTMLElement | null) => void;
  } = $props();

  let viewport = $state<HTMLElement | null>(null);
  let swiping = $state(false);
  let swipePointer = $state<number | null>(null);

  function updateSwipe(event: PointerEvent): void {
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();
    if (!rect.width) return;
    split = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
  }

  function swipeStart(event: PointerEvent): void {
    event.preventDefault();
    event.stopPropagation();
    swiping = true;
    swipePointer = event.pointerId;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
    updateSwipe(event);
  }

  function swipeMove(event: PointerEvent): void {
    if (!swiping || swipePointer !== event.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    updateSwipe(event);
  }

  function swipeEnd(event: PointerEvent): void {
    if (!swiping || swipePointer !== event.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    swiping = false;
    swipePointer = null;
    try { (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId); } catch {}
  }

  $effect(() => {
    onviewport?.(viewport);
    return () => onviewport?.(null);
  });
</script>

<div class="v2-compare-overlay mode-swipe" bind:this={viewport}>
  <div class="v2-compare-layer"><div class="v2-compare-transform" style={`transform:${transform}`}><img src={referenceSrc} alt={referenceLabel}></div></div>
  <div class="v2-compare-layer top" style={`clip-path:inset(0 ${100 - split}% 0 0)`}><div class="v2-compare-transform" style={`transform:${transform}`}><img src={selectedSrc} alt={selectedLabel} onload={onselectedload}></div></div>
  <div class="v2-compare-split-line" style={`left:${split}%`}></div>
  <div class="v2-compare-split-handle" style={`left:${split}%`}>↔</div>
  <button
    type="button"
    class="v2-compare-swipe-hit"
    style={`left:${split}%`}
    aria-label={`Move comparison split, ${Math.round(split)} percent`}
    onpointerdown={swipeStart}
    onpointermove={swipeMove}
    onpointerup={swipeEnd}
    onpointercancel={swipeEnd}
    onkeydown={(event) => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        split = Math.max(0, Math.min(100, split + (event.key === 'ArrowRight' ? 2 : -2)));
      } else if (event.key === 'Home') {
        event.preventDefault();
        split = 0;
      } else if (event.key === 'End') {
        event.preventDefault();
        split = 100;
      }
    }}
  ></button>
  <div class="v2-compare-legend"><span>Reference</span><span>Selected</span></div>
</div>

<script lang="ts">
  import V2Button from './V2Button.svelte';
  import V2CompareDifference from './V2CompareDifference.svelte';
  import V2CompareSideBySide from './V2CompareSideBySide.svelte';
  import V2CompareSwipe from './V2CompareSwipe.svelte';
  import V2CompareTransparency from './V2CompareTransparency.svelte';
  import V2Segmented from './V2Segmented.svelte';
  import V2ZoomControl from './V2ZoomControl.svelte';
  import type { MediaResource } from '../data/contracts';
  import { mediaResourceSources, nextMediaSourceIndex } from '../data/mediaSources';
  import { ViewerViewportController } from './viewerViewport.svelte';

  export type ComparisonMode = 'Side by side' | 'Swipe' | 'Transparency' | 'Difference';

  let {
    selectedResource,
    referenceResource,
    selectedLabel = 'Selected image',
    referenceLabel = 'Reference / keeper candidate',
    mode = $bindable<ComparisonMode>('Side by side'),
    opacity = $bindable(50),
    split = $bindable(50),
    diffHue = $bindable(190),
    diffContrast = $bindable(180),
    diffBinary = $bindable(true),
    diffTolerance = $bindable(8),
  }: {
    selectedResource: MediaResource;
    referenceResource: MediaResource;
    selectedLabel?: string;
    referenceLabel?: string;
    mode?: ComparisonMode;
    opacity?: number;
    split?: number;
    diffHue?: number;
    diffContrast?: number;
    diffBinary?: boolean;
    diffTolerance?: number;
  } = $props();

  const camera = new ViewerViewportController();
  let dragging = $state(false);
  let dragPointer = $state<number | null>(null);
  let lastX = $state(0);
  let lastY = $state(0);
  let selectedNatural = $state({ width: 0, height: 0 });
  let referenceNatural = $state({ width: 0, height: 0 });
  let selectedSelection = $state({ key: '', index: 0 });
  let referenceSelection = $state({ key: '', index: 0 });
  const selectedSources = $derived(mediaResourceSources(selectedResource));
  const referenceSources = $derived(mediaResourceSources(referenceResource));
  const selectedKey = $derived(selectedSources.join('\u0000'));
  const referenceKey = $derived(referenceSources.join('\u0000'));
  const selectedIndex = $derived(selectedSelection.key === selectedKey ? selectedSelection.index : 0);
  const referenceIndex = $derived(referenceSelection.key === referenceKey ? referenceSelection.index : 0);
  const selectedSrc = $derived(selectedSources[selectedIndex] ?? '');
  const referenceSrc = $derived(referenceSources[referenceIndex] ?? '');

  function selectedFailed(): void {
    const next = nextMediaSourceIndex(selectedIndex, selectedSources.length);
    if (next !== null) selectedSelection = { key: selectedKey, index: next };
  }

  function referenceFailed(): void {
    const next = nextMediaSourceIndex(referenceIndex, referenceSources.length);
    if (next !== null) referenceSelection = { key: referenceKey, index: next };
  }

  function syncNaturalSize(): void {
    camera.setNaturalSize(
      Math.max(selectedNatural.width, referenceNatural.width, 1),
      Math.max(selectedNatural.height, referenceNatural.height, 1),
    );
  }

  function changeMode(next: string): void {
    mode = next as ComparisonMode;
    requestAnimationFrame(() => camera.fit());
  }

  function setViewport(node: HTMLElement | null): void {
    camera.setViewport(node);
  }

  function selectedLoaded(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    selectedNatural = { width: image.naturalWidth, height: image.naturalHeight };
    syncNaturalSize();
    requestAnimationFrame(() => camera.fit());
  }

  function referenceLoaded(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    referenceNatural = { width: image.naturalWidth, height: image.naturalHeight };
    syncNaturalSize();
    requestAnimationFrame(() => camera.fit());
  }

  function shouldIgnore(target: EventTarget | null): boolean {
    return target instanceof Element && !!target.closest('button,input,label,.v2-compare-swipe-hit,.v2-compare-floating-controls');
  }

  function panStart(event: PointerEvent): void {
    if (event.button !== 0 || shouldIgnore(event.target)) return;
    event.preventDefault();
    dragging = true;
    dragPointer = event.pointerId;
    lastX = event.clientX;
    lastY = event.clientY;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
  }

  function panMove(event: PointerEvent): void {
    if (!dragging || dragPointer !== event.pointerId) return;
    event.preventDefault();
    camera.panBy(event.clientX - lastX, event.clientY - lastY);
    lastX = event.clientX;
    lastY = event.clientY;
  }

  function panEnd(event: PointerEvent): void {
    if (!dragging || dragPointer !== event.pointerId) return;
    dragging = false;
    dragPointer = null;
    try { (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId); } catch {}
  }

  function wheel(event: WheelEvent): void {
    event.preventDefault();
    camera.wheel(event);
  }

  $effect(() => {
    selectedSrc;
    referenceSrc;
    selectedNatural = { width: 0, height: 0 };
    referenceNatural = { width: 0, height: 0 };
  });

  $effect(() => {
    const currentMode = mode;
    void currentMode;
    requestAnimationFrame(() => camera.fit());
  });
</script>

<svelte:window onresize={() => requestAnimationFrame(() => camera.fit())} />

<div class="v2-compare-component">
  <div class="v2-compare-component-tools">
    <V2Segmented items={['Side by side','Swipe','Transparency','Difference']} active={mode} onselect={changeMode} ariaLabel="Comparison mode" />
    <div class="v2-compare-zoom-tools">
      <V2ZoomControl
        value={camera.zoom}
        onzoomout={() => camera.setZoom(camera.zoom / 1.25)}
        onzoomin={() => camera.setZoom(camera.zoom * 1.25)}
      />
      <V2Button onclick={() => camera.fit()} title="Fit image to comparison zone">Fit</V2Button>
      <V2Button onclick={() => camera.actual()} title="Show image at actual pixel size">1:1</V2Button>
    </div>
  </div>

  <div
    class="v2-compare-stage"
    class:single={mode !== 'Side by side'}
    class:panning={dragging}
    role="region"
    aria-label="Image comparison viewport"
    onpointerdown={panStart}
    onpointermove={panMove}
    onpointerup={panEnd}
    onpointercancel={panEnd}
    onwheel={wheel}
  >
    {#if mode === 'Side by side'}
      <V2CompareSideBySide
        {selectedSrc}
        {referenceSrc}
        {selectedLabel}
        {referenceLabel}
        transform={camera.transform}
        onselectedload={selectedLoaded}
        onreferenceload={referenceLoaded}
        onselectederror={selectedFailed}
        onreferenceerror={referenceFailed}
        onviewport={setViewport}
      />
    {:else if mode === 'Swipe'}
      <V2CompareSwipe
        {selectedSrc}
        {referenceSrc}
        {selectedLabel}
        {referenceLabel}
        transform={camera.transform}
        bind:split
        onselectedload={selectedLoaded}
        onreferenceload={referenceLoaded}
        onselectederror={selectedFailed}
        onreferenceerror={referenceFailed}
        onviewport={setViewport}
      />
    {:else if mode === 'Transparency'}
      <V2CompareTransparency
        {selectedSrc}
        {referenceSrc}
        {selectedLabel}
        {referenceLabel}
        transform={camera.transform}
        bind:opacity
        onselectedload={selectedLoaded}
        onreferenceload={referenceLoaded}
        onselectederror={selectedFailed}
        onreferenceerror={referenceFailed}
        onviewport={setViewport}
      />
    {:else}
      <V2CompareDifference
        {selectedSrc}
        {referenceSrc}
        {selectedLabel}
        {referenceLabel}
        transform={camera.transform}
        bind:diffHue
        bind:diffContrast
        bind:diffBinary
        bind:diffTolerance
        onselectedload={selectedLoaded}
        onreferenceload={referenceLoaded}
        onselectederror={selectedFailed}
        onreferenceerror={referenceFailed}
        onviewport={setViewport}
      />
    {/if}
  </div>
</div>

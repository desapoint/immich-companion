<script lang="ts">
  import { onDestroy } from 'svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2CompareDifference from './CompareDifference.svelte';
  import V2CompareFlicker from './CompareFlicker.svelte';
  import DuplicateLocalChangesComparison from './DuplicateLocalChangesComparison.svelte';
  import V2CompareSideBySide from './CompareSideBySide.svelte';
  import V2CompareSwipe from './CompareSwipe.svelte';
  import V2CompareTransparency from './CompareTransparency.svelte';
  import ComparisonModeSelector from './ComparisonModeSelector.svelte';
  import V2ZoomControl from '../../../lib/components/ui/ZoomControl.svelte';
  import type { MediaResource } from '../../../lib/types/libraryContracts';
  import type { LocalChangeDiagnostics } from '../utils/localChangeDiagnostics';
  import type { ComparisonImagePair } from '../types/comparisonLayer';
  import type { ComparisonMode } from '../types/comparisonMode';
  import { mediaResourceSources, nextMediaSourceIndex } from '../../../lib/api/mediaSources';
  import { ViewerViewportController } from '../../assets/state/viewportController.svelte';
  import { ViewportRegistrationController } from '../../assets/state/viewportRegistration';

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
    localDiagnostics = null,
    localDiagnosticsLoading = false,
    localDiagnosticsError = '',
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
    localDiagnostics?: LocalChangeDiagnostics | null;
    localDiagnosticsLoading?: boolean;
    localDiagnosticsError?: string;
  } = $props();

  const camera = new ViewerViewportController();
  const viewportRegistration = new ViewportRegistrationController(
    (node) => camera.setViewport(node),
    () => camera.remapViewport(),
  );
  onDestroy(() => viewportRegistration.destroy());

  let dragging = $state(false);
  let dragPointer = $state<number | null>(null);
  let lastX = $state(0);
  let lastY = $state(0);
  let localEmphasis = $state(0);
  let localMinimumDifference = $state(0);
  let localHighlightColor = $state('#00DCFF');
  let localHighlightColorPosition = $state(120);
  let localGridDetailLevel = $state(4);
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
  const comparisonPair = $derived<ComparisonImagePair>({
    selected: { src: selectedSrc, label: selectedLabel, onload: selectedLoaded, onerror: selectedFailed },
    reference: { src: referenceSrc, label: referenceLabel, onload: referenceLoaded, onerror: referenceFailed },
  });

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

  function setViewport(node: HTMLElement | null): void {
    viewportRegistration.set(node);
  }

  function selectedLoaded(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    selectedNatural = { width: image.naturalWidth, height: image.naturalHeight };
    syncNaturalSize();
  }

  function referenceLoaded(event: Event): void {
    const image = event.currentTarget as HTMLImageElement;
    referenceNatural = { width: image.naturalWidth, height: image.naturalHeight };
    syncNaturalSize();
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
    selectedNatural = { width: 0, height: 0 };
  });

  $effect(() => {
    referenceSrc;
    referenceNatural = { width: 0, height: 0 };
  });
</script>

<div class="v2-compare-component">
  <div class="v2-compare-component-tools">
    <ComparisonModeSelector bind:mode />
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
        pair={comparisonPair}
        transform={camera.transform}
        bind:split
        onviewport={setViewport}
      />
    {:else if mode === 'Transparency'}
      <V2CompareTransparency
        pair={comparisonPair}
        transform={camera.transform}
        bind:opacity
        onviewport={setViewport}
      />
    {:else if mode === 'Difference'}
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
    {:else if mode === 'Local changes'}
      <DuplicateLocalChangesComparison
        {selectedSrc}
        {referenceSrc}
        {selectedLabel}
        {referenceLabel}
        transform={camera.transform}
        diagnostics={localDiagnostics}
        loading={localDiagnosticsLoading}
        error={localDiagnosticsError}
        bind:emphasis={localEmphasis}
        bind:minimumDifference={localMinimumDifference}
        bind:highlightColor={localHighlightColor}
        bind:highlightColorPosition={localHighlightColorPosition}
        bind:gridDetailLevel={localGridDetailLevel}
        onselectedload={selectedLoaded}
        onreferenceload={referenceLoaded}
        onselectederror={selectedFailed}
        onreferenceerror={referenceFailed}
        onviewport={setViewport}
      />
    {:else}
      <V2CompareFlicker
        pair={comparisonPair}
        transform={camera.transform}
        onviewport={setViewport}
      />
    {/if}
  </div>
</div>

<script lang="ts">
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
  $effect(() => {
    onviewport?.(viewport);
    return () => onviewport?.(null);
  });
</script>

<div class="v2-compare-pane" bind:this={viewport}>
  <span class="v2-compare-label">{referenceLabel}</span>
  <div class="v2-compare-transform" style={`transform:${transform}`}>
    <img src={referenceSrc} alt={referenceLabel} onload={onreferenceload} onerror={onreferenceerror}>
  </div>
</div>
<div class="v2-compare-pane reference">
  <span class="v2-compare-label">{selectedLabel}</span>
  <div class="v2-compare-transform" style={`transform:${transform}`}>
    <img src={selectedSrc} alt={selectedLabel} onload={onselectedload} onerror={onselectederror}>
  </div>
</div>

<script lang="ts">
  import V2RangeSlider from '../../../v2/components/V2RangeSlider.svelte';

  let {
    highlightColor = $bindable('#00DCFF'),
    highlightColorPosition = $bindable(120),
    gridDetailLevel = $bindable(4),
    gridDetailLabel,
    minimumDifference = $bindable(0),
    emphasis = $bindable(0),
  }: {
    highlightColor?: string;
    highlightColorPosition?: number;
    gridDetailLevel?: number;
    gridDetailLabel: string;
    minimumDifference?: number;
    emphasis?: number;
  } = $props();
</script>

<div class="v2-compare-floating-controls v2-compare-hover v2-local-change-controls">
  <V2RangeSlider
    label="Color"
    min={0}
    max={255}
    bind:value={highlightColor}
    bind:numericValue={highlightColorPosition}
    track="spectrum"
    width={160}
    swatch={highlightColor}
    ariaLabel="Local changes highlight color"
  />
  <V2RangeSlider
    label="Grid detail"
    min={0}
    max={4}
    step={1}
    bind:value={gridDetailLevel}
    valueLabel={gridDetailLabel}
    track="fill"
    width={112}
    ariaLabel="Local changes grid detail"
  />
  <V2RangeSlider
    label="Minimum difference visible"
    min={0}
    max={100}
    step={1}
    bind:value={minimumDifference}
    suffix="%"
    track="fill"
    width={112}
    ariaLabel="Minimum visible local difference"
  />
  <V2RangeSlider
    label="Minimum highlight intensity"
    min={0}
    max={100}
    step={1}
    bind:value={emphasis}
    suffix="%"
    track="fill"
    width={112}
    ariaLabel="Minimum highlight intensity"
  />
</div>

<style>
  .v2-local-change-controls {
    width:min(920px, calc(100% - 28px));
    min-width:0;
    max-width:calc(100% - 28px);
    flex-wrap:wrap;
    justify-content:center;
    border-radius:14px;
    padding:9px 12px;
    box-sizing:border-box;
  }
</style>

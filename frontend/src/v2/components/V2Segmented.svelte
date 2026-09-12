<script lang="ts">
  type SegmentedItem = string | { value: string; label: string };

  let {
    items,
    active,
    onselect,
    ariaLabel = 'Options',
  }: {
    items: SegmentedItem[];
    active: string;
    onselect?: (item: string) => void;
    ariaLabel?: string;
  } = $props();

  const valueOf = (item: SegmentedItem) => typeof item === 'string' ? item : item.value;
  const labelOf = (item: SegmentedItem) => typeof item === 'string' ? item : item.label;
</script>

<div class="v2-segmented" role="group" aria-label={ariaLabel}>
  {#each items as item}
    <button
      type="button"
      aria-pressed={valueOf(item) === active}
      onclick={() => onselect?.(valueOf(item))}
    >{labelOf(item)}</button>
  {/each}
</div>

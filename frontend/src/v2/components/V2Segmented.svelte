<script lang="ts">
  let {
    items,
    active,
    onselect,
    ariaLabel = 'Options',
  }: {
    items: string[];
    active: string;
    onselect?: (item: string) => void;
    ariaLabel?: string;
  } = $props();
</script>

<div class="v2-segmented" role="group" aria-label={ariaLabel}>
  {#each items as item}
    <button type="button" aria-pressed={item === active} onclick={() => onselect?.(item)}>{item}</button>
  {/each}
</div>

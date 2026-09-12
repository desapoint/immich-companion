<script lang="ts">
  let {
    items,
    active,
    onselect,
    ariaLabel = 'Menu',
  }: {
    items: string[];
    active?: string;
    onselect?: (item: string) => void;
    ariaLabel?: string;
  } = $props();
</script>

<nav class="v2-menu" aria-label={ariaLabel}>
  {#each items as item}
    <button type="button" aria-current={item === active ? 'page' : undefined} onclick={() => onselect?.(item)}>{item}</button>
  {/each}
</nav>

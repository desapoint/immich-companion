<script lang="ts">
  let {
    items,
    active = items[0],
    ariaLabel = 'Page sections',
    onselect,
  }: {
    items: string[];
    active?: string;
    ariaLabel?: string;
    onselect?: (item: string) => void;
  } = $props();

  function select(item: string): void {
    if (item !== active) onselect?.(item);
  }

  function handleKeydown(event: KeyboardEvent, index: number): void {
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % items.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + items.length) % items.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = items.length - 1;
    else return;

    event.preventDefault();
    const item = items[next];
    if (!item) return;
    onselect?.(item);
    requestAnimationFrame(() => {
      (event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next])?.focus();
    });
  }
</script>

<div class="v2-tabs" role="tablist" aria-label={ariaLabel}>
  {#each items as item, index}
    <button
      class="v2-tab"
      type="button"
      role="tab"
      aria-selected={item === active}
      tabindex={item === active ? 0 : -1}
      onclick={() => select(item)}
      onkeydown={(event) => handleKeydown(event, index)}
    >{item}</button>
  {/each}
</div>

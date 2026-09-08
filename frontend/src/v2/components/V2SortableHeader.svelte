<script lang="ts">
  import { ArrowDown, ArrowUp } from '@lucide/svelte';

  let {
    field,
    label,
    sort,
    class: className = '',
    onsort,
  }: {
    field: string;
    label: string;
    sort: string;
    class?: string;
    onsort: (value: string) => void;
  } = $props();

  const active = $derived(sort.split(':')[0] === field);
  const direction = $derived(sort.endsWith(':desc') ? 'desc' : 'asc');
  const nextDirection = $derived(active && direction === 'asc' ? 'desc' : 'asc');
  const nextDirectionLabel = $derived(nextDirection === 'asc' ? 'ascending' : 'descending');

  function toggleSort(): void {
    onsort(`${field}:${nextDirection}`);
  }
</script>

<th class={className} aria-sort={active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
  <button type="button" title={`Sort ${label} ${nextDirectionLabel}`} onclick={toggleSort}>
    <span>{label}</span>
    {#if active}
      <span class="v2-sortable-header-icon" aria-hidden="true">
        {#if direction === 'desc'}
          <ArrowUp size={14} />
        {:else}
          <ArrowDown size={14} />
        {/if}
      </span>
    {/if}
  </button>
</th>

<style>
  button {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin: -5px -6px;
    padding: 5px 6px;
    border: 0;
    border-radius: 5px;
    color: inherit;
    background: transparent;
    font: inherit;
    text-transform: inherit;
    cursor: pointer;
  }

  button:hover,
  button:focus-visible {
    color: var(--v2-text);
    background: color-mix(in srgb, currentColor 8%, transparent);
  }

  button:focus-visible {
    outline: 2px solid var(--v2-accent);
    outline-offset: 1px;
  }

  .v2-sortable-header-icon {
    display: inline-flex;
  }
</style>

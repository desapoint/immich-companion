<script lang="ts">
  import { clickOutside } from '../../actions/clickOutside';
  import type { ActionMenuItem } from '../../types/ui';
  import Icon from './Icon.svelte';
  import IconButton from './IconButton.svelte';

  interface Props {
    items: ActionMenuItem[];
    label?: string;
    disabled?: boolean;
    onselect: (itemId: string) => void;
  }

  let { items, label = 'More actions', disabled = false, onselect }: Props = $props();
  let open = $state(false);

  function selectItem(item: ActionMenuItem): void {
    if (item.disabled) return;
    open = false;
    onselect(item.id);
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      open = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  use:clickOutside={{ enabled: open, onoutside: () => (open = false) }}
  class:open
  class="action-menu"
>
  <IconButton
    icon="more"
    {label}
    {disabled}
    tone={open ? 'accent' : 'default'}
    onclick={() => (open = !open)}
  />
  <div class="menu" role="menu" aria-label={label} hidden={!open}>
    {#each items as item (item.id)}
      <button
        class:destructive={item.tone === 'destructive'}
        type="button"
        role="menuitem"
        disabled={item.disabled}
        onclick={() => selectItem(item)}
      >
        <Icon name={item.icon} size="1.05rem" />
        <span>{item.label}</span>
      </button>
    {/each}
  </div>
</div>

<style>
  .action-menu {
    position: relative;
    flex: 0 0 auto;
  }

  .menu {
    position: absolute;
    z-index: 1250;
    top: calc(100% + 0.42rem);
    right: 0;
    display: grid;
    width: max-content;
    min-width: 13.5rem;
    max-width: min(20rem, calc(100vw - 2rem));
    padding: 0.35rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    background: var(--color-surface-raised);
    box-shadow: 0 0.9rem 2.4rem rgb(17 24 19 / 22%);
  }

  .menu[hidden] { display: none; }

  .menu button {
    display: grid;
    width: 100%;
    min-height: 2.35rem;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: 0.65rem;
    padding: 0.5rem 0.62rem;
    border: 0;
    border-radius: calc(var(--radius-sm) - 0.15rem);
    color: var(--color-ink-strong);
    background: transparent;
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 720;
    text-align: left;
  }

  .menu button:hover:not(:disabled),
  .menu button:focus-visible {
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  .menu button.destructive { color: #b45309; }
  .menu button:disabled { cursor: default; opacity: 0.42; }
</style>

<script lang="ts">
  import Icon from './Icon.svelte';
  import type { ShortcutHelpItem } from '../../types/ui';

  interface Props {
    items: readonly ShortcutHelpItem[];
    label?: string;
    title?: string;
    open?: boolean;
    onopenchange?: (open: boolean) => void;
  }

  let {
    items,
    label = 'Keyboard shortcuts',
    title = 'Keyboard shortcuts',
    open = false,
    onopenchange,
  }: Props = $props();

  let hovering = $state(false);
  let focusWithin = $state(false);
  const componentId = $props.id();
  const panelId = `${componentId}-shortcut-help`;
  const visible = $derived(open || hovering || focusWithin);

  function togglePinned(): void {
    onopenchange?.(!open);
  }

  function handleFocusOut(event: FocusEvent): void {
    const currentTarget = event.currentTarget as HTMLElement;
    const nextTarget = event.relatedTarget as Node | null;
    if (!nextTarget || !currentTarget.contains(nextTarget)) focusWithin = false;
  }
</script>

<div
  class="shortcut-help"
  onpointerenter={() => (hovering = true)}
  onpointerleave={() => (hovering = false)}
  onfocusin={() => (focusWithin = true)}
  onfocusout={handleFocusOut}
>
  <button
    type="button"
    class:active={open}
    aria-label={open ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
    aria-expanded={visible}
    aria-controls={panelId}
    onclick={togglePinned}
  >
    <Icon name="keyboard" size="1.08rem" />
    <span class="visually-hidden">{label}</span>
  </button>

  {#if visible}
    <div id={panelId} class="shortcut-panel" role="tooltip" aria-label={label}>
      <strong>{title}</strong>
      <dl>
        {#each items as item (`${item.shortcut}-${item.description}`)}
          <div>
            <dt><kbd>{item.shortcut}</kbd></dt>
            <dd>{item.description}</dd>
          </div>
        {/each}
      </dl>
    </div>
  {/if}
</div>

<style>
  .shortcut-help {
    position: relative;
    display: inline-flex;
  }

  button {
    display: grid;
    width: 2.45rem;
    height: 2.45rem;
    padding: 0;
    place-items: center;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
  }

  button:hover,
  button:focus-visible,
  button.active {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  .shortcut-panel {
    position: absolute;
    z-index: 30;
    top: calc(100% + 0.5rem);
    right: 0;
    width: min(21rem, calc(100vw - 1rem));
    max-height: min(30rem, calc(100dvh - 5rem));
    padding: 0.85rem;
    overflow: auto;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: 0 1rem 2.5rem rgb(0 0 0 / 24%);
  }

  strong {
    font-size: 0.82rem;
  }

  dl {
    display: grid;
    gap: 0.48rem;
    margin: 0.7rem 0 0;
  }

  dl div {
    display: grid;
    grid-template-columns: minmax(6rem, 8rem) 1fr;
    gap: 0.6rem;
    align-items: center;
  }

  dt,
  dd {
    margin: 0;
    font-size: 0.7rem;
  }

  dd {
    color: var(--color-ink-muted);
  }

  kbd {
    display: inline-block;
    padding: 0.15rem 0.32rem;
    border: 1px solid var(--color-border-strong);
    border-radius: 0.28rem;
    background: var(--color-surface-soft);
    box-shadow: 0 0.1rem 0 var(--color-border-strong);
    font-family: var(--font-mono);
    font-size: 0.65rem;
    white-space: nowrap;
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
</style>

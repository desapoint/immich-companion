<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import type { Snippet } from 'svelte';

  import { clickOutside } from '../../../lib/actions/clickOutside';
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import type { IconName } from '../../../lib/types/ui';
  import {
    floatingPopoverLayout,
    type FloatingPopoverLayout,
  } from '../../../lib/utils/floatingPopover';

  interface Props {
    kind: Extract<IconName, 'album' | 'tag' | 'stack' | 'external'>;
    label: string;
    count?: number;
    popoverSizing?: 'default' | 'content';
    children: Snippet;
  }

  let { kind, label, count, popoverSizing = 'default', children }: Props = $props();
  let triggerElement = $state<HTMLButtonElement>();
  let popoverElement = $state<HTMLElement>();
  let pinned = $state(false);
  let hovered = $state(false);
  let hoverExitTimer: ReturnType<typeof setTimeout> | undefined;
  let popoverLayout = $state<FloatingPopoverLayout | null>(null);
  const componentId = $props.id();

  function updatePopoverLayout(): void {
    if (!triggerElement || !popoverElement) return;

    const measuredWidth = popoverElement.getBoundingClientRect().width;
    popoverLayout = floatingPopoverLayout(
      triggerElement.getBoundingClientRect(),
      window.innerWidth,
      window.innerHeight,
      {
        preferredWidth: measuredWidth || (popoverSizing === 'content' ? 384 : 304),
        preferredHeight: Math.min(popoverElement.scrollHeight || 320, 320),
      },
    );
  }

  function cancelHoverExit(): void {
    if (hoverExitTimer === undefined) return;
    clearTimeout(hoverExitTimer);
    hoverExitTimer = undefined;
  }

  function enterPopoverArea(): void {
    cancelHoverExit();
    hovered = true;
    updatePopoverLayout();
  }

  function leavePopoverArea(): void {
    cancelHoverExit();
    hoverExitTimer = setTimeout(() => {
      hovered = false;
      hoverExitTimer = undefined;
    }, 120);
  }

  async function togglePinned(): Promise<void> {
    pinned = !pinned;
    if (!pinned) return;
    await tick();
    updatePopoverLayout();
  }

  $effect(() => {
    if (!pinned && !hovered) return;
    const update = () => updatePopoverLayout();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  });

  onDestroy(cancelHoverExit);
</script>

<div
  use:clickOutside={{ enabled: pinned, onoutside: () => (pinned = false) }}
  class:pinned
  class:hovered
  class="relation-indicator"
  onmouseenter={enterPopoverArea}
  onmouseleave={leavePopoverArea}
  onfocusin={updatePopoverLayout}
>
  <button
    bind:this={triggerElement}
    type="button"
    aria-label={label}
    aria-expanded={pinned}
    aria-controls={`${componentId}-details`}
    title={label}
    onclick={() => void togglePinned()}
  >
    <Icon name={kind} />
    {#if count !== undefined}<span>{count}</span>{/if}
  </button>
  <aside
    bind:this={popoverElement}
    id={`${componentId}-details`}
    class:content-sized={popoverSizing === 'content'}
    class="relation-popover"
    aria-label={`${label} details`}
    style:left={popoverLayout ? `${popoverLayout.left}px` : undefined}
    style:top={popoverLayout?.top === null
      ? 'auto'
      : popoverLayout
        ? `${popoverLayout.top}px`
        : undefined}
    style:bottom={popoverLayout?.bottom === null
      ? 'auto'
      : popoverLayout
        ? `${popoverLayout.bottom}px`
        : undefined}
    style:width={popoverLayout ? `${popoverLayout.width}px` : undefined}
    style:max-height={popoverLayout ? `${popoverLayout.maxHeight}px` : undefined}
    onmouseenter={enterPopoverArea}
    onmouseleave={leavePopoverArea}
  >
    <strong>{label}</strong>
    <div class="popover-content">{@render children()}</div>
  </aside>
</div>

<style>
  .relation-indicator {
    position: relative;
  }

  button {
    display: inline-flex;
    min-width: 2rem;
    min-height: 2rem;
    align-items: center;
    justify-content: center;
    gap: 0.28rem;
    padding: 0.36rem 0.48rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    cursor: pointer;
    font: inherit;
    font-size: 0.62rem;
    font-weight: 800;
  }

  button:hover,
  button:focus-visible,
  .pinned button {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  .relation-popover {
    position: fixed;
    z-index: 1000;
    width: min(19rem, calc(100vw - 2rem));
    padding: 0.7rem;
    overflow: auto;
    visibility: hidden;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: 0 0.9rem 2.4rem rgb(17 24 19 / 22%);
    opacity: 0;
    pointer-events: none;
    transform: translateY(-0.2rem);
    transition: opacity 120ms ease, transform 120ms ease, visibility 120ms ease;
  }

  .relation-popover.content-sized {
    width: max-content;
    max-width: min(24rem, calc(100vw - 2rem));
  }

  .relation-indicator.hovered .relation-popover,
  .relation-indicator:focus-within .relation-popover,
  .relation-indicator.pinned .relation-popover {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
  }

  .relation-popover > strong {
    display: block;
    padding-bottom: 0.45rem;
    border-bottom: 1px solid var(--color-border-subtle);
    color: var(--color-accent-strong);
    font-size: 0.68rem;
  }

  .popover-content {
    padding-top: 0.5rem;
    color: var(--color-ink-muted);
    font-size: 0.67rem;
  }
</style>

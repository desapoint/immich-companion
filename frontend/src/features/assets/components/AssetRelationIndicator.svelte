<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import type { Snippet } from 'svelte';

  import { clickOutside } from '../../../lib/actions/clickOutside';
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import type { IconName } from '../../../lib/types/ui';

  interface Props {
    kind: Extract<IconName, 'album' | 'tag' | 'stack' | 'external'>;
    label: string;
    count?: number;
    popoverSizing?: 'default' | 'content';
    children: Snippet;
  }

  type Placement = 'below-left' | 'below-right' | 'above-left' | 'above-right';

  interface PopoverLayout {
    placement: Placement;
    left: number;
    top: number;
    width: number;
    maxHeight: number;
  }

  const VIEWPORT_PADDING = 12;
  const ANCHOR_GAP = 8;
  const DEFAULT_WIDTH = 304;
  const CONTENT_WIDTH = 384;
  const PREFERRED_HEIGHT = 320;

  let { kind, label, count, popoverSizing = 'default', children }: Props = $props();
  let containerElement = $state<HTMLDivElement>();
  let triggerElement = $state<HTMLButtonElement>();
  let popoverElement = $state<HTMLElement>();
  let pinned = $state(false);
  let hovered = $state(false);
  let focused = $state(false);
  let hoverExitTimer: ReturnType<typeof setTimeout> | undefined;
  let popoverLayout = $state<PopoverLayout | null>(null);
  const componentId = $props.id();

  function clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), Math.max(min, max));
  }

  function isPopoverOpen(): boolean {
    return popoverElement?.matches(':popover-open') ?? false;
  }

  function updatePopoverLayout(): void {
    if (!triggerElement || !popoverElement || !isPopoverOpen()) return;

    const anchor = triggerElement.getBoundingClientRect();
    const availableWidth = Math.max(0, window.innerWidth - VIEWPORT_PADDING * 2);
    const preferredWidth = popoverSizing === 'content' ? CONTENT_WIDTH : DEFAULT_WIDTH;
    const measuredWidth = popoverElement.scrollWidth;
    const width = Math.min(
      popoverSizing === 'content' ? Math.max(measuredWidth, preferredWidth) : preferredWidth,
      availableWidth,
    );
    const desiredHeight = Math.min(popoverElement.scrollHeight || PREFERRED_HEIGHT, PREFERRED_HEIGHT);

    const spaceBelow = Math.max(0, window.innerHeight - VIEWPORT_PADDING - anchor.bottom - ANCHOR_GAP);
    const spaceAbove = Math.max(0, anchor.top - VIEWPORT_PADDING - ANCHOR_GAP);
    const vertical = spaceBelow >= Math.min(desiredHeight, spaceAbove) ? 'below' : 'above';
    const maxHeight = vertical === 'below' ? spaceBelow : spaceAbove;
    const renderedHeight = Math.min(desiredHeight, maxHeight);

    const leftAligned = anchor.left;
    const rightAligned = anchor.right - width;
    const leftFits = leftAligned >= VIEWPORT_PADDING && leftAligned + width <= window.innerWidth - VIEWPORT_PADDING;
    const rightFits = rightAligned >= VIEWPORT_PADDING && rightAligned + width <= window.innerWidth - VIEWPORT_PADDING;

    const anchorCenter = anchor.left + anchor.width / 2;
    const preferLeftAlignment = anchorCenter <= window.innerWidth / 2;

    let alignment: 'left' | 'right';
    if (preferLeftAlignment) {
      alignment = leftFits ? 'left' : rightFits ? 'right' : 'left';
    } else {
      alignment = rightFits ? 'right' : leftFits ? 'left' : 'right';
    }

    const desiredLeft = alignment === 'left' ? leftAligned : rightAligned;
    const left = clamp(desiredLeft, VIEWPORT_PADDING, window.innerWidth - VIEWPORT_PADDING - width);
    const top = vertical === 'below'
      ? anchor.bottom + ANCHOR_GAP
      : anchor.top - ANCHOR_GAP - renderedHeight;

    popoverLayout = {
      placement: `${vertical}-${alignment}`,
      left,
      top: clamp(top, VIEWPORT_PADDING, window.innerHeight - VIEWPORT_PADDING - renderedHeight),
      width,
      maxHeight,
    };
  }

  async function showPopover(): Promise<void> {
    if (!popoverElement) return;
    if (!isPopoverOpen()) popoverElement.showPopover();
    await tick();
    updatePopoverLayout();
  }

  function hidePopoverIfInactive(): void {
    if (pinned || hovered || focused || !popoverElement || !isPopoverOpen()) return;
    popoverElement.hidePopover();
    popoverLayout = null;
  }

  function cancelHoverExit(): void {
    if (hoverExitTimer === undefined) return;
    clearTimeout(hoverExitTimer);
    hoverExitTimer = undefined;
  }

  function enterPopoverArea(): void {
    cancelHoverExit();
    hovered = true;
    void showPopover();
  }

  function leavePopoverArea(): void {
    cancelHoverExit();
    hoverExitTimer = setTimeout(() => {
      hovered = false;
      hoverExitTimer = undefined;
      hidePopoverIfInactive();
    }, 120);
  }

  function handleFocusIn(): void {
    focused = true;
    void showPopover();
  }

  function handleFocusOut(): void {
    queueMicrotask(() => {
      focused = containerElement?.contains(document.activeElement) ?? false;
      hidePopoverIfInactive();
    });
  }

  async function togglePinned(): Promise<void> {
    pinned = !pinned;
    if (pinned) {
      await showPopover();
    } else {
      hidePopoverIfInactive();
    }
  }

  $effect(() => {
    if (!pinned && !hovered && !focused) return;
    const update = () => updatePopoverLayout();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  });

  onDestroy(() => {
    cancelHoverExit();
    if (popoverElement && isPopoverOpen()) popoverElement.hidePopover();
  });
</script>

<div
  bind:this={containerElement}
  use:clickOutside={{ enabled: pinned, onoutside: () => {
    pinned = false;
    hidePopoverIfInactive();
  } }}
  class:pinned
  class="relation-indicator"
  onmouseenter={enterPopoverArea}
  onmouseleave={leavePopoverArea}
  onfocusin={handleFocusIn}
  onfocusout={handleFocusOut}
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
    popover="manual"
    data-placement={popoverLayout?.placement}
    class:content-sized={popoverSizing === 'content'}
    class="relation-popover"
    aria-label={`${label} details`}
    style:left={popoverLayout ? `${popoverLayout.left}px` : '0px'}
    style:top={popoverLayout ? `${popoverLayout.top}px` : '0px'}
    style:width={popoverLayout ? `${popoverLayout.width}px` : undefined}
    style:max-height={popoverLayout ? `${popoverLayout.maxHeight}px` : undefined}
    onmouseenter={enterPopoverArea}
    onmouseleave={leavePopoverArea}
    onfocusin={handleFocusIn}
    onfocusout={handleFocusOut}
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
    inset: auto;
    width: min(19rem, calc(100vw - 1.5rem));
    margin: 0;
    padding: 0.7rem;
    overflow: auto;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: 0 0.9rem 2.4rem rgb(17 24 19 / 22%);
    opacity: 0;
    transition: opacity 120ms ease, transform 120ms ease;
  }

  .relation-popover[data-placement^='below'] {
    transform: translateY(-0.2rem);
  }

  .relation-popover[data-placement^='above'] {
    transform: translateY(0.2rem);
  }

  .relation-popover:popover-open {
    opacity: 1;
    transform: translateY(0);
  }

  .relation-popover.content-sized {
    max-width: calc(100vw - 1.5rem);
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

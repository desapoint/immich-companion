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

  type Placement = 'right' | 'left' | 'below' | 'above';

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
    const availableHeight = Math.max(0, window.innerHeight - VIEWPORT_PADDING * 2);
    const preferredWidth = popoverSizing === 'content' ? CONTENT_WIDTH : DEFAULT_WIDTH;
    const measuredWidth = popoverElement.scrollWidth;
    const width = Math.min(
      popoverSizing === 'content' ? Math.max(measuredWidth, preferredWidth) : preferredWidth,
      availableWidth,
    );
    const desiredHeight = Math.min(popoverElement.scrollHeight || PREFERRED_HEIGHT, PREFERRED_HEIGHT);
    const height = Math.min(desiredHeight, availableHeight);

    const spaceRight = window.innerWidth - VIEWPORT_PADDING - anchor.right - ANCHOR_GAP;
    const spaceLeft = anchor.left - VIEWPORT_PADDING - ANCHOR_GAP;
    const spaceBelow = window.innerHeight - VIEWPORT_PADDING - anchor.bottom - ANCHOR_GAP;
    const spaceAbove = anchor.top - VIEWPORT_PADDING - ANCHOR_GAP;

    const horizontalCenter = anchor.left + anchor.width / 2;
    const verticalCenter = anchor.top + anchor.height / 2;
    const horizontalOrder: Placement[] = horizontalCenter <= window.innerWidth / 2
      ? ['right', 'left']
      : ['left', 'right'];
    const verticalOrder: Placement[] = verticalCenter <= window.innerHeight / 2
      ? ['below', 'above']
      : ['above', 'below'];
    const candidates = [...horizontalOrder, ...verticalOrder];

    const fits = (placement: Placement): boolean => {
      if (placement === 'right') return spaceRight >= width;
      if (placement === 'left') return spaceLeft >= width;
      if (placement === 'below') return spaceBelow >= height;
      return spaceAbove >= height;
    };

    const placement = candidates.find(fits) ?? candidates.reduce((best, candidate) => {
      const available = candidate === 'right'
        ? spaceRight
        : candidate === 'left'
          ? spaceLeft
          : candidate === 'below'
            ? spaceBelow
            : spaceAbove;
      const bestAvailable = best === 'right'
        ? spaceRight
        : best === 'left'
          ? spaceLeft
          : best === 'below'
            ? spaceBelow
            : spaceAbove;
      return available > bestAvailable ? candidate : best;
    }, candidates[0]);

    let left: number;
    let top: number;
    let maxHeight = availableHeight;

    if (placement === 'right') {
      left = anchor.right + ANCHOR_GAP;
      top = clamp(anchor.top, VIEWPORT_PADDING, window.innerHeight - VIEWPORT_PADDING - height);
      maxHeight = availableHeight;
    } else if (placement === 'left') {
      left = anchor.left - ANCHOR_GAP - width;
      top = clamp(anchor.top, VIEWPORT_PADDING, window.innerHeight - VIEWPORT_PADDING - height);
      maxHeight = availableHeight;
    } else if (placement === 'below') {
      left = clamp(anchor.left, VIEWPORT_PADDING, window.innerWidth - VIEWPORT_PADDING - width);
      top = anchor.bottom + ANCHOR_GAP;
      maxHeight = Math.max(0, spaceBelow);
    } else {
      left = clamp(anchor.left, VIEWPORT_PADDING, window.innerWidth - VIEWPORT_PADDING - width);
      top = anchor.top - ANCHOR_GAP - Math.min(height, Math.max(0, spaceAbove));
      maxHeight = Math.max(0, spaceAbove);
    }

    left = clamp(left, VIEWPORT_PADDING, window.innerWidth - VIEWPORT_PADDING - width);
    top = clamp(top, VIEWPORT_PADDING, window.innerHeight - VIEWPORT_PADDING - Math.min(height, maxHeight));

    popoverLayout = {
      placement,
      left,
      top,
      width,
      maxHeight: Math.max(0, maxHeight),
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

  .relation-popover[data-placement='right'] {
    transform: translateX(-0.2rem);
  }

  .relation-popover[data-placement='left'] {
    transform: translateX(0.2rem);
  }

  .relation-popover[data-placement='below'] {
    transform: translateY(-0.2rem);
  }

  .relation-popover[data-placement='above'] {
    transform: translateY(0.2rem);
  }

  .relation-popover:popover-open {
    opacity: 1;
    transform: translate(0);
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

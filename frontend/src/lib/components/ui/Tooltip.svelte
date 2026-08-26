<script lang="ts">
  import { onDestroy, tick } from 'svelte';

  import { calculateTooltipPosition } from '../../state/tooltipPosition';

  interface Props {
    id: string;
    text: string;
    anchor: HTMLElement | null;
    open: boolean;
  }

  let { id, text, anchor, open }: Props = $props();
  let tooltip = $state<HTMLElement>();
  let position = $state('left: 0; top: 0; visibility: hidden;');
  let fallbackVisible = $state(false);

  function isPopoverOpen(): boolean {
    return tooltip?.matches(':popover-open') ?? false;
  }

  function positionTooltip(): void {
    if (!open || !anchor || !tooltip) return;
    const anchorRect = anchor.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const next = calculateTooltipPosition(
      anchorRect,
      tooltipRect.width,
      tooltipRect.height,
      window.innerWidth,
      window.innerHeight,
    );
    position = `left: ${next.left}px; top: ${next.top}px; visibility: visible;`;
  }

  async function show(): Promise<void> {
    await tick();
    if (!open || !anchor || !tooltip) return;
    position = 'left: 0; top: 0; visibility: hidden;';
    try {
      if (typeof tooltip.showPopover === 'function') {
        if (!isPopoverOpen()) tooltip.showPopover();
      } else {
        fallbackVisible = true;
      }
    } catch {
      return;
    }
    await tick();
    positionTooltip();
  }

  function hide(): void {
    if (!tooltip) return;
    fallbackVisible = false;
    position = 'left: 0; top: 0; visibility: hidden;';
    try {
      if (typeof tooltip.hidePopover === 'function' && isPopoverOpen()) {
        tooltip.hidePopover();
      }
    } catch {
      // The owning button may have been removed with its dialog.
    }
  }

  $effect(() => {
    if (open && anchor) void show();
    else hide();
  });

  $effect(() => {
    if (!open) return;
    const reposition = () => positionTooltip();
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  });

  onDestroy(hide);
</script>

<span
  bind:this={tooltip}
  {id}
  class="tooltip"
  class:fallback-visible={fallbackVisible}
  data-open={open}
  role="tooltip"
  popover="manual"
  style={position}
>{text}</span>

<style>
  .tooltip {
    position: fixed;
    z-index: 2000;
    inset: auto;
    width: max-content;
    max-width: min(14rem, calc(100vw - 1rem));
    margin: 0;
    padding: 0.32rem 0.48rem;
    pointer-events: none;
    border: 1px solid var(--color-border-strong);
    border-radius: calc(var(--radius-sm) - 0.15rem);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
    font-family: var(--font-sans);
    font-size: 0.66rem;
    font-weight: 720;
    line-height: 1.25;
  }

  .tooltip.fallback-visible {
    display: block;
  }
</style>

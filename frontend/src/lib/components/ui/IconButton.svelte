<script lang="ts">
  import type { IconName } from '../../types/ui';
  import Icon from './Icon.svelte';
  import Tooltip from './Tooltip.svelte';

  interface Props {
    icon: IconName;
    label: string;
    disabled?: boolean;
    tone?: 'default' | 'accent' | 'destructive';
    size?: 'compact' | 'regular';
    type?: 'button' | 'submit';
    onclick: (event: MouseEvent) => void;
  }

  let {
    icon,
    label,
    disabled = false,
    tone = 'default',
    size = 'regular',
    type = 'button',
    onclick,
  }: Props = $props();
  let button = $state<HTMLButtonElement>();
  let pointerInside = $state(false);
  let keyboardFocused = $state(false);
  const componentId = $props.id();
  const tooltipId = `${componentId}-tooltip`;
  const tooltipOpen = $derived(pointerInside || keyboardFocused);

  function hideTooltip(): void {
    pointerInside = false;
    keyboardFocused = false;
  }

  function handleFocus(): void {
    keyboardFocused = button?.matches(':focus-visible') ?? false;
  }

  function handleClick(event: MouseEvent): void {
    hideTooltip();
    onclick(event);
  }
</script>

<svelte:window onpointerup={hideTooltip} onpointercancel={hideTooltip} onblur={hideTooltip} />

<span class="icon-button-wrap" data-tone={tone}>
  <button
    bind:this={button}
    {type}
    {disabled}
    class:compact={size === 'compact'}
    aria-label={label}
    aria-describedby={tooltipOpen ? tooltipId : undefined}
    onpointerenter={() => (pointerInside = true)}
    onpointerleave={() => (pointerInside = false)}
    onpointerdown={hideTooltip}
    onfocus={handleFocus}
    onblur={() => (keyboardFocused = false)}
    onclick={handleClick}
  >
    <Icon name={icon} size={size === 'compact' ? '0.95rem' : '1.08rem'} />
    <span class="visually-hidden">{label}</span>
  </button>
  <Tooltip id={tooltipId} text={label} anchor={button ?? null} open={tooltipOpen} />
</span>

<style>
  .icon-button-wrap {
    position: relative;
    display: inline-flex;
    flex: 0 0 auto;
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

  button.compact {
    width: 2.1rem;
    height: 2.1rem;
  }

  button:hover:not(:disabled),
  button:focus-visible {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  [data-tone='accent'] button {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  [data-tone='destructive'] button {
    border-color: color-mix(in srgb, #b45309 58%, var(--color-border-strong));
    color: #b45309;
  }

  button:disabled {
    cursor: default;
    opacity: 0.45;
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

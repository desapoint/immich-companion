<script lang="ts">
  import type { IconName } from '../../types/ui';
  import Icon from './Icon.svelte';

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
</script>

<span class="icon-button-wrap" data-tone={tone}>
  <button
    {type}
    {disabled}
    class:compact={size === 'compact'}
    aria-label={label}
    title={label}
    {onclick}
  >
    <Icon name={icon} size={size === 'compact' ? '0.95rem' : '1.08rem'} />
    <span class="visually-hidden">{label}</span>
  </button>
  <span class="legend" aria-hidden="true">{label}</span>
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

  .legend {
    position: absolute;
    z-index: 1200;
    top: calc(100% + 0.38rem);
    left: 50%;
    width: max-content;
    max-width: 14rem;
    padding: 0.32rem 0.48rem;
    pointer-events: none;
    border: 1px solid var(--color-border-strong);
    border-radius: calc(var(--radius-sm) - 0.15rem);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
    font-size: 0.66rem;
    font-weight: 720;
    line-height: 1.25;
    opacity: 0;
    transform: translate(-50%, -0.18rem);
    transition: opacity 110ms ease, transform 110ms ease;
  }

  .icon-button-wrap:hover .legend,
  .icon-button-wrap:focus-within .legend {
    opacity: 1;
    transform: translate(-50%, 0);
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

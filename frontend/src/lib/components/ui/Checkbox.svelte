<script lang="ts">
  import Icon from './Icon.svelte';

  interface Props {
    checked: boolean;
    label: string;
    ariaLabel?: string;
    disabled?: boolean;
    hiddenLabel?: boolean;
    variant?: 'checkbox' | 'switch';
    shape?: 'square' | 'circle';
    onchange?: (checked: boolean) => void;
    onclick?: (event: MouseEvent) => void;
  }

  let {
    checked,
    label,
    ariaLabel,
    disabled = false,
    hiddenLabel = false,
    variant = 'checkbox',
    shape = 'square',
    onchange,
    onclick,
  }: Props = $props();
</script>

<label class:switch={variant === 'switch'} class:circle={variant === 'checkbox' && shape === 'circle'} class="checkbox">
  <input
    type="checkbox"
    role={variant === 'switch' ? 'switch' : undefined}
    {checked}
    {disabled}
    aria-label={hiddenLabel ? (ariaLabel ?? label) : ariaLabel}
    onchange={(event) => onchange?.(event.currentTarget.checked)}
    {onclick}
  />
  <span class="control" aria-hidden="true">
    {#if variant === 'checkbox'}
      <span class:visible={checked} class="checkmark"><Icon name="check" size="0.82rem" strokeWidth={2.4} /></span>
    {:else}
      <span class="switch-thumb"></span>
    {/if}
  </span>
  {#if !hiddenLabel}<span class="label">{label}</span>{/if}
</label>

<style>
  .checkbox {
    display: inline-flex;
    min-height: 1.55rem;
    align-items: center;
    gap: 0.45rem;
    color: var(--color-ink-muted);
    cursor: pointer;
    font: inherit;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.35;
  }

  input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    clip-path: inset(50%);
    white-space: nowrap;
  }

  .control {
    display: grid;
    width: 1.15rem;
    height: 1.15rem;
    box-sizing: border-box;
    flex: 0 0 auto;
    place-items: center;
    border: 1px solid var(--color-border-strong);
    border-radius: calc(var(--radius-sm) - 0.24rem);
    color: var(--color-ink-inverse);
    background: var(--color-canvas);
    box-shadow: inset 0 0 0 0.08rem color-mix(in srgb, var(--color-surface-raised) 45%, transparent);
    transition: border-color 120ms ease, background 120ms ease, box-shadow 120ms ease;
  }

  .circle .control {
    width: 1.3rem;
    height: 1.3rem;
    border-radius: 50%;
  }

  .checkmark {
    display: grid;
    place-items: center;
    opacity: 0;
    transform: scale(0.72);
    transition: opacity 100ms ease, transform 100ms ease;
  }

  .checkmark.visible {
    opacity: 1;
    transform: scale(1);
  }

  .label {
    line-height: 1.35;
  }

  input:checked + .control {
    border-color: var(--color-accent-strong);
    background: var(--color-accent-strong);
    box-shadow: inset 0 0 0 0.08rem color-mix(in srgb, var(--color-canvas) 28%, transparent);
  }

  input:focus-visible + .control {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 55%, transparent);
    outline-offset: 0.15rem;
  }

  .checkbox:hover input:not(:disabled) + .control {
    border-color: var(--color-accent-strong);
  }

  .checkbox:has(input:disabled) {
    cursor: default;
    opacity: 0.5;
  }

  .switch .control {
    display: flex;
    width: 2.8rem;
    height: 1.55rem;
    align-items: center;
    padding: 0.16rem;
    border-radius: 999px;
    background: var(--color-surface-soft);
  }

  .switch-thumb {
    width: 1.08rem;
    height: 1.08rem;
    border-radius: 50%;
    background: var(--color-ink-muted);
    box-shadow: 0 0.1rem 0.3rem rgb(0 0 0 / 18%);
    transition: transform 140ms ease, background 140ms ease;
  }

  .switch input:checked + .control {
    background: color-mix(in srgb, var(--color-accent-strong) 18%, var(--color-surface-soft));
  }

  .switch input:checked + .control .switch-thumb {
    background: var(--color-accent-strong);
    transform: translateX(1.2rem);
  }
</style>

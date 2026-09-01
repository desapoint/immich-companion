<script lang="ts">
  import Icon from '../ui/Icon.svelte';

  interface Props {
    eligible: boolean;
    selected: boolean;
    disabled?: boolean;
    compact?: boolean;
    iconOnly?: boolean;
    eligibleLabel?: string;
    ineligibleLabel?: string;
    onchange?: () => void;
  }

  let {
    eligible,
    selected,
    disabled = false,
    compact = false,
    iconOnly = false,
    eligibleLabel = 'Make stack main',
    ineligibleLabel = 'Choose Stack first',
    onchange,
  }: Props = $props();
  const label = $derived(selected ? 'Stack main' : eligible ? eligibleLabel : ineligibleLabel);
</script>

<button
  type="button"
  class:compact
  class:icon-only={iconOnly}
  class:selected
  disabled={disabled || !eligible}
  aria-pressed={selected}
  aria-label={label}
  title={eligible ? (selected ? 'This image is the stack main image' : eligibleLabel) : ineligibleLabel}
  onclick={() => onchange?.()}
>
  <Icon name="star" size=".8rem" />
  <span class:visually-hidden={iconOnly}>{label}</span>
</button>

<style>
  button { display: inline-flex; width: 100%; min-height: 2.15rem; align-items: center; justify-content: center; gap: .32rem; padding: .35rem .5rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-muted); background: var(--color-canvas); font: inherit; font-size: .68rem; font-weight: 780; cursor: pointer; }
  button:hover:not(:disabled), button.selected { border-color: var(--color-accent-strong); color: var(--color-accent-strong); background: color-mix(in srgb, var(--color-accent-strong) 9%, var(--color-canvas)); }
  button:disabled { cursor: default; opacity: .5; }
  button:focus-visible { outline: .14rem solid color-mix(in srgb, var(--color-accent-strong) 55%, transparent); outline-offset: .12rem; }
  button.compact { min-height: 1.9rem; padding: .25rem .4rem; font-size: .62rem; }
  button.icon-only { width: 2rem; min-height: 2rem; padding: 0; border-radius: 999px; color: white; background: rgb(12 16 18 / .76); box-shadow: 0 2px 8px rgb(0 0 0 / .28); backdrop-filter: blur(5px); }
  button.icon-only:hover:not(:disabled), button.icon-only.selected { color: white; background: var(--color-accent-strong); }
  .visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
</style>

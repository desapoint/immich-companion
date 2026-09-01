<script lang="ts">
  import Icon from '../ui/Icon.svelte';

  interface Props {
    eligible: boolean;
    selected: boolean;
    disabled?: boolean;
    compact?: boolean;
    onchange?: () => void;
  }

  let { eligible, selected, disabled = false, compact = false, onchange }: Props = $props();
</script>

<button
  type="button"
  class:compact
  class:selected
  disabled={disabled || !eligible}
  aria-pressed={selected}
  title={eligible ? (selected ? 'This image is the stack main image' : 'Use this image as the stack main image') : 'Choose Stack for this image first'}
  onclick={() => onchange?.()}
>
  <Icon name="star" size=".8rem" />
  <span>{selected ? 'Stack main' : eligible ? 'Make stack main' : 'Choose Stack first'}</span>
</button>

<style>
  button { display: inline-flex; width: 100%; min-height: 2.15rem; align-items: center; justify-content: center; gap: .32rem; padding: .35rem .5rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-muted); background: var(--color-canvas); font: inherit; font-size: .68rem; font-weight: 780; cursor: pointer; }
  button:hover:not(:disabled), button.selected { border-color: var(--color-accent-strong); color: var(--color-accent-strong); background: color-mix(in srgb, var(--color-accent-strong) 9%, var(--color-canvas)); }
  button:disabled { cursor: default; opacity: .5; }
  button:focus-visible { outline: .14rem solid color-mix(in srgb, var(--color-accent-strong) 55%, transparent); outline-offset: .12rem; }
  button.compact { min-height: 1.9rem; padding: .25rem .4rem; font-size: .62rem; }
</style>

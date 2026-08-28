<script lang="ts">
  import Icon from './Icon.svelte';

  type LayoutMode = 'normal' | 'condensed';

  interface Props {
    mode: LayoutMode;
    disabled?: boolean;
    onchange: (mode: LayoutMode) => void;
  }

  let { mode, disabled = false, onchange }: Props = $props();
</script>

<div class="layout-controls" role="group" aria-label="Asset card layout">
  <span>Card layout</span>
  <button
    class:active={mode === 'normal'}
    type="button"
    {disabled}
    aria-pressed={mode === 'normal'}
    onclick={() => onchange('normal')}
  >
    <Icon name="view" size="0.9rem" />
    Normal
  </button>
  <button
    class:active={mode === 'condensed'}
    type="button"
    {disabled}
    aria-pressed={mode === 'condensed'}
    onclick={() => onchange('condensed')}
  >
    <Icon name="select-page" size="0.9rem" />
    Condensed
  </button>
</div>

<style>
  .layout-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    gap: 0.35rem;
  }

  .layout-controls > span {
    margin-inline-end: 0.15rem;
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
  }

  button {
    display: inline-flex;
    min-height: 2rem;
    align-items: center;
    gap: 0.32rem;
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-muted);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.68rem;
    font-weight: 760;
  }

  button.active {
    border-color: var(--color-accent-strong);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
  }

  button:hover:not(:disabled),
  button:focus-visible {
    border-color: var(--color-accent-hover);
  }

  button:disabled {
    cursor: default;
    opacity: 0.55;
  }
</style>

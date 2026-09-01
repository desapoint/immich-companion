<script lang="ts">
  import type { DuplicateDisposition } from '../../types/duplicateReview';
  import Icon from '../ui/Icon.svelte';

  interface Props {
    value: DuplicateDisposition | null;
    disabled?: boolean;
    compact?: boolean;
    onchange?: (value: DuplicateDisposition) => void;
  }

  let { value, disabled = false, compact = false, onchange }: Props = $props();

  const choices: ReadonlyArray<{
    value: DuplicateDisposition;
    label: string;
    icon: 'select' | 'trash' | 'stack';
  }> = [
    { value: 'keep', label: 'Keep', icon: 'select' },
    { value: 'delete', label: 'Delete', icon: 'trash' },
    { value: 'stack', label: 'Stack', icon: 'stack' },
  ];
</script>

<div class:compact class="disposition-controls" aria-label="Decision for this duplicate">
  {#each choices as choice (choice.value)}
    <button
      type="button"
      class:active={value === choice.value}
      class:delete={choice.value === 'delete'}
      aria-pressed={value === choice.value}
      {disabled}
      onclick={() => onchange?.(choice.value)}
    >
      <Icon name={choice.icon} size=".8rem" />
      <span>{choice.label}</span>
    </button>
  {/each}
</div>

<style>
  .disposition-controls { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); overflow: hidden; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); }
  button { display: inline-flex; min-width: 0; min-height: 2.15rem; align-items: center; justify-content: center; gap: .28rem; padding: .35rem .45rem; border: 0; border-right: 1px solid var(--color-border-subtle); color: var(--color-ink-muted); background: var(--color-canvas); font: inherit; font-size: .68rem; font-weight: 780; cursor: pointer; }
  button:last-child { border-right: 0; }
  button:not(.active):hover:not(:disabled) { color: var(--color-accent-strong); background: var(--color-surface-soft); }
  button.active { color: var(--color-ink-inverse); background: var(--color-accent-strong); }
  button.delete.active { background: var(--color-negative-ink); }
  button:focus-visible { position: relative; z-index: 1; outline: .14rem solid color-mix(in srgb, var(--color-accent-strong) 55%, transparent); outline-offset: -.14rem; }
  button:disabled { cursor: default; opacity: .5; }
  .compact button { min-height: 1.9rem; padding: .25rem .35rem; font-size: .62rem; }
</style>

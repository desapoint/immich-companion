<script lang="ts">
  import type { Snippet } from 'svelte';

  import { clickOutside } from '../../../lib/actions/clickOutside';
  import AssetIcon from './AssetIcon.svelte';

  interface Props {
    kind: 'album' | 'tag' | 'stack' | 'external';
    label: string;
    count?: number;
    children: Snippet;
  }

  let { kind, label, count, children }: Props = $props();
  let pinned = $state(false);
  const componentId = $props.id();
</script>

<div
  use:clickOutside={{ enabled: pinned, onoutside: () => (pinned = false) }}
  class:pinned
  class="relation-indicator"
>
  <button
    type="button"
    aria-label={label}
    aria-expanded={pinned}
    aria-controls={`${componentId}-details`}
    title={label}
    onclick={() => (pinned = !pinned)}
  >
    <AssetIcon {kind} />
    {#if count !== undefined}<span>{count}</span>{/if}
  </button>
  <aside id={`${componentId}-details`} class="relation-popover" aria-label={`${label} details`}>
    <strong>{label}</strong>
    <div class="popover-content">{@render children()}</div>
  </aside>
</div>

<style>
  .relation-indicator {
    position: relative;
  }

  .relation-indicator::after {
    position: absolute;
    z-index: 39;
    top: 100%;
    left: -0.25rem;
    width: calc(100% + 0.5rem);
    height: 0.55rem;
    content: '';
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
    position: absolute;
    z-index: 40;
    top: calc(100% + 0.38rem);
    left: 0;
    width: min(19rem, calc(100vw - 2rem));
    padding: 0.7rem;
    visibility: hidden;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    box-shadow: 0 0.9rem 2.4rem rgb(17 24 19 / 22%);
    opacity: 0;
    pointer-events: none;
    transform: translateY(-0.2rem);
    transition: opacity 120ms ease, transform 120ms ease, visibility 120ms ease;
  }

  .relation-indicator:hover .relation-popover,
  .relation-indicator:focus-within .relation-popover,
  .relation-indicator.pinned .relation-popover {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
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

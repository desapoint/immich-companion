<script lang="ts">
  import {
    duplicateReviewFilters,
    type DuplicateReviewFilter,
  } from '../state/duplicateReviewFilters';

  interface Props {
    active: DuplicateReviewFilter;
    counts: Record<DuplicateReviewFilter, number>;
    disabled?: boolean;
    onchange: (filter: DuplicateReviewFilter) => void;
  }

  let { active, counts, disabled = false, onchange }: Props = $props();
</script>

<nav class="review-filters" aria-label="Filter duplicate groups">
  {#each duplicateReviewFilters as filter (filter.value)}
    <button
      type="button"
      class:active={active === filter.value}
      aria-pressed={active === filter.value}
      {disabled}
      onclick={() => onchange(filter.value)}
    >
      <span>{filter.label}</span>
      <strong>{counts[filter.value]}</strong>
    </button>
  {/each}
</nav>

<style>
  .review-filters {
    display: flex;
    min-width: 0;
    gap: 0.4rem;
    overflow-x: auto;
    padding: 0.15rem 0 0.35rem;
    scrollbar-width: thin;
  }

  button {
    display: inline-flex;
    flex: none;
    min-height: 2.15rem;
    align-items: center;
    gap: 0.45rem;
    padding: 0.38rem 0.55rem;
    border: 1px solid var(--color-border-strong);
    border-radius: 999px;
    color: var(--color-ink-muted);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.67rem;
    font-weight: 760;
    white-space: nowrap;
  }

  button:hover:not(:disabled),
  button:focus-visible,
  button.active {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
  }

  button.active {
    background: color-mix(in srgb, var(--color-accent-strong) 10%, var(--color-surface-raised));
  }

  button:disabled {
    cursor: default;
    opacity: 0.55;
  }

  strong {
    min-width: 1.35rem;
    padding: 0.12rem 0.3rem;
    border-radius: 999px;
    color: currentColor;
    background: var(--color-surface-soft);
    font-size: 0.59rem;
    text-align: center;
  }

  :global(.duplicates-page .group-heading .workflow-status) {
    flex-basis: 100%;
    width: fit-content;
    margin-top: 0.1rem;
    color: var(--color-ink-strong);
    font-size: 0.74rem;
    font-weight: 820;
    line-height: 1.25;
  }

  :global(.duplicates-page .group-heading .decision-status),
  :global(.duplicates-page .group-heading .discovery-source) {
    opacity: 0.78;
  }
</style>

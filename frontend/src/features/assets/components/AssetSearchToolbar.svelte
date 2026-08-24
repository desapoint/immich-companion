<script lang="ts">
  import { copySearchGroup, createSearchGroup } from '../state/assetViewModel';
  import type { AlbumOption, SearchGroup } from '../types/assets';
  import SearchExpressionBuilder from './SearchExpressionBuilder.svelte';

  interface Props {
    expression: SearchGroup;
    albums: AlbumOption[];
    disabled?: boolean;
    onsearch: (expression: SearchGroup) => void;
  }

  let { expression, albums, disabled = false, onsearch }: Props = $props();
  let draft = $state(createSearchGroup());

  $effect(() => {
    draft = copySearchGroup(expression);
  });

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onsearch(copySearchGroup(draft));
  }

  function reset(): void {
    draft = createSearchGroup();
    onsearch(copySearchGroup(draft));
  }
</script>

<form class="search-toolbar" aria-label="Structured Immich asset search" onsubmit={submit}>
  <div class="search-heading">
    <div>
      <span>Advanced search</span>
      <h2>Build album and metadata rules</h2>
      <p>Combine conditions with AND or OR, nest groups, and negate any whole group.</p>
    </div>
    <div class="search-actions">
      <button class="reset-action" type="button" onclick={reset} {disabled}>Clear filters</button>
      <button class="primary-action" type="submit" {disabled}>Search assets</button>
    </div>
  </div>

  <SearchExpressionBuilder expression={draft} {albums} {disabled} />
</form>

<style>
  .search-toolbar {
    display: grid;
    gap: 0.85rem;
    padding: clamp(0.9rem, 2vw, 1.2rem);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-card);
  }

  .search-heading,
  .search-actions {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 0.65rem;
  }

  .search-heading span {
    color: var(--color-accent-strong);
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
  }

  h2 {
    margin: 0.12rem 0 0;
    font-size: clamp(1rem, 2vw, 1.22rem);
  }

  p {
    margin: 0.22rem 0 0;
    color: var(--color-ink-muted);
    font-size: 0.78rem;
  }

  button {
    min-height: 2.65rem;
    padding: 0.6rem 0.86rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font: inherit;
    font-size: 0.78rem;
    font-weight: 780;
    white-space: nowrap;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  .primary-action {
    border-color: var(--color-accent-strong);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
  }

  .reset-action {
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
  }

  @media (max-width: 46rem) {
    .search-heading {
      align-items: stretch;
      flex-direction: column;
    }

    .search-actions button {
      flex: 1;
    }
  }
</style>

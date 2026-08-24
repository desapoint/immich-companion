<script lang="ts">
  import { buildPaginationItems } from '../../utils/pagination';
  import SelectField from './SelectField.svelte';

  interface Props {
    currentPage: number;
    totalPages: number;
    onpagechange: (page: number) => void;
    disabled?: boolean;
    siblingCount?: number;
    boundaryCount?: number;
    showFirstLast?: boolean;
    showPreviousNext?: boolean;
    showSummary?: boolean;
    hideWhenSinglePage?: boolean;
    totalItems?: number;
    pageSize?: number;
    pageSizeOptions?: readonly number[];
    allowPageSizeChange?: boolean;
    onpagesizechange?: (pageSize: number) => void;
    label?: string;
  }

  let {
    currentPage,
    totalPages,
    onpagechange,
    disabled = false,
    siblingCount = 2,
    boundaryCount = 1,
    showFirstLast = true,
    showPreviousNext = true,
    showSummary = true,
    hideWhenSinglePage = false,
    totalItems,
    pageSize = 24,
    pageSizeOptions = [24, 48, 96],
    allowPageSizeChange = false,
    onpagesizechange,
    label = 'Pagination',
  }: Props = $props();
  const componentId = $props.id();

  const normalizedTotalPages = $derived(Math.max(0, Math.floor(totalPages)));
  const normalizedCurrentPage = $derived(
    normalizedTotalPages === 0
      ? 0
      : Math.min(Math.max(1, Math.floor(currentPage)), normalizedTotalPages),
  );
  const items = $derived(buildPaginationItems({
    currentPage: normalizedCurrentPage,
    totalPages: normalizedTotalPages,
    siblingCount,
    boundaryCount,
  }));
  const normalizedPageSizes = $derived(
    [...new Set([...pageSizeOptions, pageSize])]
      .filter((value) => Number.isInteger(value) && value > 0)
      .sort((left, right) => left - right),
  );
  const showPageSize = $derived(
    allowPageSizeChange && normalizedPageSizes.length > 1 && Boolean(onpagesizechange),
  );
  const shouldRender = $derived(
    normalizedTotalPages > 0
      && (!hideWhenSinglePage || normalizedTotalPages > 1 || showPageSize),
  );
  const summary = $derived(
    totalItems === undefined
      ? `Page ${normalizedCurrentPage} of ${normalizedTotalPages}`
      : `Page ${normalizedCurrentPage} of ${normalizedTotalPages} · ${totalItems.toLocaleString()} items`,
  );

  function selectPage(nextPage: number): void {
    if (disabled || normalizedTotalPages === 0) return;
    const normalized = Math.min(Math.max(1, nextPage), normalizedTotalPages);
    if (normalized !== normalizedCurrentPage) onpagechange(normalized);
  }
</script>

{#if shouldRender}
  <nav
    class="pagination"
    class:without-page-size={!showPageSize}
    class:without-summary={!showSummary}
    aria-label={label}
  >
    {#if showPageSize}
      <div class="page-size">
        <SelectField
          id={`${componentId}-page-size`}
          label="Items per page"
          value={String(pageSize)}
          options={normalizedPageSizes.map((value) => ({
            value: String(value),
            label: String(value),
          }))}
          {disabled}
          compact
          onchange={(value) => onpagesizechange?.(Number(value))}
        />
      </div>
    {/if}

    <div class="page-controls">
      {#if showFirstLast}
        <button
          class="direction"
          type="button"
          onclick={() => selectPage(1)}
          disabled={disabled || normalizedCurrentPage <= 1}
          aria-label="First page"
        >First</button>
      {/if}
      {#if showPreviousNext}
        <button
          class="direction"
          type="button"
          onclick={() => selectPage(normalizedCurrentPage - 1)}
          disabled={disabled || normalizedCurrentPage <= 1}
          aria-label="Previous page"
        >Previous</button>
      {/if}

      {#each items as item (item.key)}
        {#if item.kind === 'ellipsis'}
          <span class="ellipsis" aria-hidden="true">…</span>
        {:else}
          <button
            class:current={item.page === normalizedCurrentPage}
            class="page-number"
            type="button"
            onclick={() => selectPage(item.page)}
            disabled={disabled || item.page === normalizedCurrentPage}
            aria-current={item.page === normalizedCurrentPage ? 'page' : undefined}
            aria-label={`Page ${item.page}`}
          >{item.page}</button>
        {/if}
      {/each}

      {#if showPreviousNext}
        <button
          class="direction"
          type="button"
          onclick={() => selectPage(normalizedCurrentPage + 1)}
          disabled={disabled || normalizedCurrentPage >= normalizedTotalPages}
          aria-label="Next page"
        >Next</button>
      {/if}
      {#if showFirstLast}
        <button
          class="direction"
          type="button"
          onclick={() => selectPage(normalizedTotalPages)}
          disabled={disabled || normalizedCurrentPage >= normalizedTotalPages}
          aria-label="Last page"
        >Last</button>
      {/if}
    </div>

    {#if showSummary}
      <p class="summary" aria-live="polite">{summary}</p>
    {/if}
  </nav>
{/if}

<style>
  .pagination {
    display: grid;
    grid-template-columns: minmax(8rem, auto) minmax(0, 1fr) minmax(8rem, auto);
    align-items: end;
    gap: 0.85rem;
    padding: 0.8rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-md);
    background: var(--color-surface-raised);
  }

  .pagination.without-page-size {
    grid-template-columns: minmax(0, 1fr) minmax(8rem, auto);
  }

  .pagination.without-summary {
    grid-template-columns: minmax(8rem, auto) minmax(0, 1fr);
  }

  .pagination.without-page-size.without-summary {
    grid-template-columns: 1fr;
  }

  .page-size {
    min-width: 8rem;
  }

  .page-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 0.32rem;
  }

  button {
    min-width: 2.45rem;
    min-height: 2.45rem;
    padding: 0.48rem 0.62rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.72rem;
    font-weight: 760;
  }

  button:hover:not(:disabled) {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  button.current {
    border-color: var(--color-accent-strong);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
    opacity: 1;
  }

  button:disabled:not(.current) {
    cursor: default;
    opacity: 0.42;
  }

  .direction {
    padding-inline: 0.75rem;
  }

  .ellipsis {
    display: grid;
    width: 1.8rem;
    min-height: 2.45rem;
    place-items: center;
    color: var(--color-ink-muted);
    font-weight: 800;
  }

  .summary {
    margin: 0;
    align-self: center;
    color: var(--color-ink-muted);
    font-size: 0.7rem;
    text-align: right;
    white-space: nowrap;
  }

  @media (max-width: 62rem) {
    .pagination,
    .pagination.without-page-size,
    .pagination.without-summary,
    .pagination.without-page-size.without-summary {
      grid-template-columns: 1fr;
      align-items: center;
    }

    .page-size {
      width: min(10rem, 100%);
      justify-self: center;
    }

    .summary {
      justify-self: center;
      text-align: center;
    }
  }

  @media (max-width: 34rem) {
    .pagination {
      padding-inline: 0.55rem;
    }

    .direction {
      flex: 1 1 4.5rem;
    }

    .page-number {
      flex: 0 0 auto;
    }
  }
</style>

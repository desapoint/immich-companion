<script lang="ts">
  import Pagination from '../../../lib/components/ui/Pagination.svelte';
  import {
    ASSET_PAGE_SIZE_OPTIONS,
    ASSET_PAGINATION_BOUNDARY_COUNT,
    ASSET_PAGINATION_SIBLING_COUNT,
  } from '../state/assetPagination';

  interface Props {
    page: number;
    pages: number;
    total: number;
    pageSize: number;
    disabled?: boolean;
    siblingCount?: number;
    boundaryCount?: number;
    showFirstLast?: boolean;
    showPreviousNext?: boolean;
    showSummary?: boolean;
    hideWhenSinglePage?: boolean;
    allowPageSizeChange?: boolean;
    pageSizeOptions?: readonly number[];
    label?: string;
    onpage: (page: number) => void;
    onpagesizechange?: (pageSize: number) => void;
    mode?: 'paged' | 'infinite';
    onmodechange?: (mode: 'paged' | 'infinite') => void;
    showPagination?: boolean;
    showModeToggle?: boolean;
  }

  let {
    page,
    pages,
    total,
    pageSize,
    disabled = false,
    siblingCount = ASSET_PAGINATION_SIBLING_COUNT,
    boundaryCount = ASSET_PAGINATION_BOUNDARY_COUNT,
    showFirstLast = true,
    showPreviousNext = true,
    showSummary = true,
    hideWhenSinglePage = false,
    allowPageSizeChange = true,
    pageSizeOptions = ASSET_PAGE_SIZE_OPTIONS,
    label = 'Asset result pages',
    onpage,
    onpagesizechange,
    mode = 'paged',
    onmodechange,
    showPagination = true,
    showModeToggle = true,
  }: Props = $props();
</script>

{#if showPagination && mode === 'paged'}
<Pagination
  currentPage={page}
  totalPages={pages}
  totalItems={total}
  {pageSize}
  {pageSizeOptions}
  {siblingCount}
  {boundaryCount}
  {showFirstLast}
  {showPreviousNext}
  {showSummary}
  {hideWhenSinglePage}
  {allowPageSizeChange}
  {disabled}
  {label}
  onpagechange={onpage}
  {onpagesizechange}
/>
{/if}
{#if showModeToggle && onmodechange}
  <div class="mode-controls" role="group" aria-label="Asset list mode">
    <button class:active={mode === 'paged'} type="button" disabled={disabled || mode === 'paged'} onclick={() => onmodechange?.('paged')}>Pages</button>
    <button class:active={mode === 'infinite'} type="button" disabled={disabled || mode === 'infinite'} onclick={() => onmodechange?.('infinite')}>Infinite scroll</button>
  </div>
{/if}

<style>
  .mode-controls {
    display: flex;
    justify-content: flex-end;
    gap: 0.35rem;
    margin-top: 0.45rem;
  }

  .mode-controls button {
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-muted);
    background: var(--color-surface-raised);
    cursor: pointer;
    font: inherit;
    font-size: 0.65rem;
    font-weight: 700;
  }

  .mode-controls button.active {
    border-color: var(--color-accent-strong);
    color: var(--color-accent-strong);
    background: var(--color-canvas);
  }

  .mode-controls button:focus-visible,
  .mode-controls button:hover:not(:disabled) {
    border-color: var(--color-accent-hover);
  }
</style>

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
  }: Props = $props();
</script>

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

<script lang="ts">
  import V2InfiniteFooter from './V2InfiniteFooter.svelte';
  import V2Pagination from './V2Pagination.svelte';
  import type { CollectionResultMode } from '../state/collectionView.svelte';

  let {
    resultMode,
    page,
    pageSize,
    total,
    loaded,
    noun = 'items',
    onpage = () => {},
    onloadmore,
  }: {
    resultMode: CollectionResultMode;
    page: number;
    pageSize: number;
    total: number;
    loaded: number;
    noun?: string;
    onpage?: (page: number) => void;
    onloadmore?: () => void;
  } = $props();
</script>

{#if resultMode === 'Pagination'}
  <V2Pagination {page} {pageSize} {total} {onpage} />
{:else}
  <V2InfiniteFooter loaded={Math.min(loaded, total)} {total} batchSize={pageSize} {noun} {onloadmore} />
{/if}

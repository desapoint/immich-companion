<script lang="ts">
  import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from '@lucide/svelte';
  import V2Button from './V2Button.svelte';
  import V2PageJumpDialog from './V2PageJumpDialog.svelte';
  import { paginationItems } from '../state/pagination';

  let { page, pageSize, total, onpage }: { page:number; pageSize:number; total:number; onpage:(page:number)=>void } = $props();
  const paginationId = $props.id();
  const maxPage = $derived(Math.max(1, Math.ceil(total/pageSize)));
  const items = $derived(paginationItems(page, maxPage));
  const start = $derived((page-1)*pageSize+1);
  const end = $derived(Math.min(total,page*pageSize));
  let jumpOpen = $state(false);
</script>

<div class="v2-results-footer">
  <span class="v2-small v2-muted">Showing {start}–{end} of {total.toLocaleString()}</span>
  <nav class="v2-page-buttons" aria-label="Pagination">
    <V2Button iconOnly title="First page" ariaLabel="First page" disabled={page===1} onclick={()=>onpage(1)}><ChevronsLeft size={17} aria-hidden="true"/></V2Button>
    <V2Button iconOnly title="Previous page" ariaLabel="Previous page" disabled={page===1} onclick={()=>onpage(page-1)}><ChevronLeft size={17} aria-hidden="true"/></V2Button>
    {#each items as item (`${item.kind}-${item.kind==='page'?item.page:`${item.from}-${item.to}`}`)}
      {#if item.kind === 'page'}
        <V2Button active={item.page===page} ariaCurrent={item.page===page?'page':undefined} ariaLabel={item.page===page?`Page ${item.page}, current page`:`Go to page ${item.page}`} onclick={()=>onpage(item.page)}>{item.page}</V2Button>
      {:else}
        <V2Button title={`Jump to a page (hidden pages ${item.from}–${item.to})`} ariaLabel={`Jump to a page; hidden pages ${item.from} through ${item.to}`} onclick={()=>jumpOpen=true}>…</V2Button>
      {/if}
    {/each}
    <V2Button iconOnly title="Next page" ariaLabel="Next page" disabled={page===maxPage} onclick={()=>onpage(page+1)}><ChevronRight size={17} aria-hidden="true"/></V2Button>
    <V2Button iconOnly title="Last page" ariaLabel="Last page" disabled={page===maxPage} onclick={()=>onpage(maxPage)}><ChevronsRight size={17} aria-hidden="true"/></V2Button>
  </nav>
</div>

{#if jumpOpen}
  <V2PageJumpDialog id={`${paginationId}-page-jump`} currentPage={page} {maxPage} {onpage} onclose={()=>jumpOpen=false}/>
{/if}

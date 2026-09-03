<script lang="ts">
  import V2Button from './V2Button.svelte';

  let { page, pageSize, total, onpage }: { page:number; pageSize:number; total:number; onpage:(page:number)=>void } = $props();
  const maxPage = $derived(Math.max(1, Math.ceil(total/pageSize)));
  const pages = $derived(Array.from(new Set([1,page-1,page,page+1,maxPage].filter((p)=>p>=1&&p<=maxPage))));
  const start = $derived((page-1)*pageSize+1);
  const end = $derived(Math.min(total,page*pageSize));
</script>

<div class="v2-results-footer">
  <span class="v2-small v2-muted">Showing {start}–{end} of {total.toLocaleString()}</span>
  <div class="v2-page-buttons">
    <V2Button disabled={page===1} onclick={()=>onpage(page-1)}>← Previous</V2Button>
    {#each pages as p, i}
      {#if i && p-pages[i-1]>1}<span class="v2-muted">…</span>{/if}
      <V2Button active={p===page} onclick={()=>onpage(p)}>{p}</V2Button>
    {/each}
    <V2Button disabled={page===maxPage} onclick={()=>onpage(page+1)}>Next →</V2Button>
  </div>
</div>

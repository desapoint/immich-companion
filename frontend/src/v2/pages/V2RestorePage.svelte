<script lang="ts">
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2InfiniteFooter from '../components/V2InfiniteFooter.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';

  let page = $state(1);
  let pageSize = $state(24);
  let resultMode = $state<ResultMode>('Pagination');
  let loaded = $state(24);
  let sort = $state('deletedAt:desc');
  let viewer = $state(false);
  const total = 126;
  const visibleCount = $derived(resultMode === 'Pagination'
    ? Math.min(pageSize, Math.max(0, total - (page - 1) * pageSize))
    : Math.min(loaded, total));
  const firstIndex = $derived(resultMode === 'Pagination' ? (page - 1) * pageSize : 0);
  const items = $derived(Array.from({ length: visibleCount }, (_, i) => firstIndex + i));

  function setPageSize(next: number): void {
    pageSize = next;
    page = 1;
    loaded = Math.max(next, Math.min(loaded, total));
  }

  function setMode(mode: ResultMode): void {
    resultMode = mode;
    if (mode === 'Pagination') page = 1;
    else loaded = Math.max(pageSize, loaded);
  }
</script>

<V2PageLayout title="Restore" description="Review current Immich trash and restore individual, selected, or all trashed assets.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Restore selected</V2Button><V2Button variant="primary">Restore all</V2Button></V2Inline>{/snippet}

  {#snippet context()}
    <V2Zone>
      <V2Section title="Trash summary"><V2Card><V2Stack gap="sm"><b>{total} items</b><span class="v2-small v2-muted">Loaded directly from current Immich trash.</span></V2Stack></V2Card></V2Section>
      <V2Section title="Selection"><V2Stack gap="sm"><V2Button>Select all loaded</V2Button><V2Button>Clear selection</V2Button></V2Stack></V2Section>
      <V2Card><span class="v2-small v2-muted">Display density is controlled globally from the header.</span></V2Card>
    </V2Zone>
  {/snippet}

  <V2Zone>
    <V2Toolbar>
      <V2Badge text={`${total.toLocaleString()} trashed assets`} />
      {#snippet actions()}
        <V2CollectionControls
          id="restore-results"
          {sort}
          sortFields={[{value:'deletedAt',label:'Deleted date'},{value:'takenAt',label:'Taken date'},{value:'name',label:'Name'}]}
          {pageSize}
          pageSizes={[24,48,96]}
          {resultMode}
          onsort={(value)=>sort=value}
          onpagesize={setPageSize}
          onmode={setMode}
        />
      {/snippet}
    </V2Toolbar>
    <div class="v2-asset-grid">{#each items as i}<V2AssetTile index={i} label={`Trash item ${i + 1}`} sublabel="Deleted recently" onclick={() => viewer = true} />{/each}</div>
    {#if resultMode === 'Pagination'}
      <V2Pagination {page} {pageSize} {total} onpage={(next)=>page=next}/>
    {:else}
      <V2InfiniteFooter loaded={Math.min(loaded,total)} {total} batchSize={pageSize} noun="trashed assets" onloadmore={()=>loaded=Math.min(total,loaded+pageSize)}/>
    {/if}
  </V2Zone>

  {#snippet inspector()}
    <V2Zone><V2Section title="Selected trash"><V2Card><V2Stack gap="sm"><b>4 selected</b><span class="v2-small v2-muted">Restore is the only mutation available in this workspace/viewer.</span><V2Button variant="primary">Restore selected</V2Button></V2Stack></V2Card></V2Section></V2Zone>
  {/snippet}
</V2PageLayout>

<V2Viewer open={viewer} title="Restore Viewer" mode="restore" onclose={() => viewer = false} />

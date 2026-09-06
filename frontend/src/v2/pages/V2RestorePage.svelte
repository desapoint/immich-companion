<script lang="ts">
  import { onMount } from 'svelte';
  import { CheckCheck, ListChecks, RotateCcw } from '@lucide/svelte';
  import V2AssetGrid from '../components/V2AssetGrid.svelte';
  import V2AssetSelectionToolbar from '../components/V2AssetSelectionToolbar.svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2InfiniteFooter from '../components/V2InfiniteFooter.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2RangeSlider from '../components/V2RangeSlider.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { createGridViewportAnchor } from '../components/gridViewportAnchor';
  import { createAssetGridSelectionInteraction } from '../components/assetGridSelectionInteraction';
  import { applyShiftAssetRange, emptyAssetSelection, getAssetSelectionCount, invertAssetSelection, isAllVisibleSelected, isAssetSelected, selectAllMatchingAssets, selectVisibleAssets, toggleAssetSelected, type AssetSelectionState } from '../components/assetSelection';
  import { demoAssetState, initializeDemoAssetState, restoreDemoAssets, selectedDemoAssetIds, trashedDemoAssets } from '../demo/demoAssetState.svelte';

  let page=$state(1), pageSize=$state(24), resultMode=$state<ResultMode>('Pagination'), loaded=$state(24), sort=$state('deletedAt:desc'), viewer=$state(false), assetGrid=$state<HTMLElement|null>(null), assetColumns=$state(4);
  let selection=$state<AssetSelectionState<string>>(emptyAssetSelection<string>());
  const gridViewportAnchor=createGridViewportAnchor(()=>assetGrid);
  const matchingAssets=$derived((demoAssetState.revision, trashedDemoAssets()));
  const total=$derived(matchingAssets.length);
  const visibleCount=$derived(resultMode==='Pagination'?Math.min(pageSize,Math.max(0,total-(page-1)*pageSize)):Math.min(loaded,total));
  const firstIndex=$derived(resultMode==='Pagination'?(page-1)*pageSize:0);
  const items=$derived(matchingAssets.slice(firstIndex,firstIndex+visibleCount));
  const itemIds=$derived(items.map((asset)=>asset.id));
  const matchingIds=$derived(matchingAssets.map((asset)=>asset.id));
  const selectedCount=$derived(getAssetSelectionCount(selection,total));
  const selectionActive=$derived(selectedCount>0);
  const allMatchingSelected=$derived(selection.allMatchingSelected);
  const allVisibleSelected=$derived(isAllVisibleSelected(selection,itemIds));

  const interaction=createAssetGridSelectionInteraction<string>({getItems:()=>itemIds,getSelection:()=>selection,setSelection:(next)=>selection=next,parseAssetId:(value)=>value});

  function setPageSize(next:number){pageSize=next;page=1;loaded=Math.max(next,Math.min(loaded,total))}
  function setMode(mode:ResultMode){resultMode=mode;if(mode==='Pagination')page=1;else loaded=Math.max(pageSize,loaded)}
  function setAssetColumns(next:number|string){assetColumns=Number(next);gridViewportAnchor.adjust()}
  function isSelected(id:string){return isAssetSelected(selection,id)}
  function clearSelection(){selection=emptyAssetSelection<string>()}
  function selectVisible(){selection=selectVisibleAssets(itemIds)}
  function selectAllMatching(){selection=selectAllMatchingAssets(itemIds[0]??null)}
  function invertSelection(){selection=invertAssetSelection(selection)}
  function handleSelectionClick(id:string,event:MouseEvent){selection=event.shiftKey?applyShiftAssetRange(selection,itemIds,id):toggleAssetSelected(selection,id)}
  function handleTileActivate(id:string,event:MouseEvent){if(interaction.consumeSuppressedClick(id))return;if(selectionActive||event.metaKey||event.ctrlKey||event.shiftKey){handleSelectionClick(id,event);return}viewer=true}
  function restoreSelected(){restoreDemoAssets(selectedDemoAssetIds(selection,matchingIds));clearSelection();if(page>1&&(page-1)*pageSize>=total)page=Math.max(1,page-1)}
  function restoreAll(){restoreDemoAssets(matchingIds);clearSelection();page=1}

  onMount(()=>{initializeDemoAssetState();return()=>{gridViewportAnchor.destroy();interaction.destroy()}});
</script>

<svelte:window onpointermove={interaction.move} onpointerup={interaction.finish} onpointercancel={interaction.cancel} onkeydown={(event)=>{if(event.key==='Escape'){if(interaction.isDragging())interaction.cancel();else if(viewer)viewer=false;else if(selectionActive)clearSelection()}}}/>

<V2PageLayout title="Restore" description="Review current Immich trash and restore individual, selected, or all trashed assets.">
  {#snippet headerActions()}<V2Button variant="primary" disabled={total===0} onclick={restoreAll}>Restore all</V2Button>{/snippet}
  <V2Zone>
    {#if selectionActive}
      <V2AssetSelectionToolbar {selectedCount} {total} noun="trashed assets" {allMatchingSelected} {allVisibleSelected} onselectvisible={selectVisible} onselectall={selectAllMatching} oninvert={invertSelection} onclear={clearSelection}>
        {#snippet actions()}<V2Button iconOnly variant="primary" title="Restore selected" ariaLabel="Restore selected" onclick={restoreSelected}><RotateCcw size={18}/></V2Button>{/snippet}
      </V2AssetSelectionToolbar>
    {:else}
      <V2Toolbar>
        <V2Badge text={`${total.toLocaleString()} trashed assets`}/>
        <V2Button iconOnly title="Select visible" ariaLabel="Select visible" disabled={total===0} onclick={selectVisible}><ListChecks size={18}/></V2Button>
        <V2Button iconOnly title={`Select all ${total.toLocaleString()} trashed assets`} ariaLabel={`Select all ${total.toLocaleString()} trashed assets`} disabled={total===0} onclick={selectAllMatching}><CheckCheck size={18}/></V2Button>
        {#snippet actions()}<V2RangeSlider label="Per row" min={2} max={10} step={1} bind:value={assetColumns} valueLabel={`${assetColumns}`} width={92} thumbSize={18} ariaLabel="Images per row" oninteractionstart={()=>gridViewportAnchor.begin(assetColumns)} onchange={setAssetColumns} oninteractionend={gridViewportAnchor.end}/><V2CollectionControls id="restore-results" {sort} sortFields={[{value:'deletedAt',label:'Deleted date'},{value:'takenAt',label:'Taken date'},{value:'name',label:'Name'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={(value)=>sort=value} onpagesize={setPageSize} onmode={setMode}/>{/snippet}
      </V2Toolbar>
    {/if}

    <V2AssetGrid columns={assetColumns} bind:element={assetGrid}>
      {#each items as asset, index}<V2AssetTile index={firstIndex+index} assetId={asset.id} label={asset.original_file_name} sublabel={`Taken ${new Date(asset.file_created_at).toLocaleDateString()}`} selected={isSelected(asset.id)} selectionMode={selectionActive} onactivate={(event)=>handleTileActivate(asset.id,event)} onselect={(event)=>handleSelectionClick(asset.id,event)} onpreview={()=>viewer=true} onpointerdown={(event)=>interaction.start(asset.id,event)}/>{/each}
    </V2AssetGrid>

    {#if total===0}<p class="v2-muted">Trash is empty. Assets moved to trash from the V2 demo will appear here.</p>{:else if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={(next)=>page=next}/>{:else}<V2InfiniteFooter loaded={Math.min(loaded,total)} {total} batchSize={pageSize} noun="trashed assets" onloadmore={()=>loaded=Math.min(total,loaded+pageSize)}/>{/if}
  </V2Zone>
</V2PageLayout>

<V2Viewer open={viewer} title="Restore Viewer" mode="restore" onclose={()=>viewer=false}/>

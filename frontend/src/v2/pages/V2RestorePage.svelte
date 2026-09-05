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

  let page=$state(1), pageSize=$state(24), resultMode=$state<ResultMode>('Pagination'), loaded=$state(24), sort=$state('deletedAt:desc'), viewer=$state(false), assetGrid=$state<HTMLElement|null>(null), assetColumns=$state(4);
  let selection=$state<AssetSelectionState<number>>(emptyAssetSelection<number>());
  const gridViewportAnchor=createGridViewportAnchor(()=>assetGrid);
  const total=126;
  const visibleCount=$derived(resultMode==='Pagination'?Math.min(pageSize,Math.max(0,total-(page-1)*pageSize)):Math.min(loaded,total));
  const firstIndex=$derived(resultMode==='Pagination'?(page-1)*pageSize:0);
  const items=$derived(Array.from({length:visibleCount},(_,i)=>firstIndex+i));
  const selectedCount=$derived(getAssetSelectionCount(selection,total));
  const selectionActive=$derived(selectedCount>0);
  const allMatchingSelected=$derived(selection.allMatchingSelected);
  const allVisibleSelected=$derived(isAllVisibleSelected(selection,items));

  const interaction=createAssetGridSelectionInteraction<number>({getItems:()=>items,getSelection:()=>selection,setSelection:(next)=>selection=next,parseAssetId:(value)=>{const id=Number(value);return Number.isFinite(id)?id:null}});

  function setPageSize(next:number){pageSize=next;page=1;loaded=Math.max(next,Math.min(loaded,total))}
  function setMode(mode:ResultMode){resultMode=mode;if(mode==='Pagination')page=1;else loaded=Math.max(pageSize,loaded)}
  function setAssetColumns(next:number|string){assetColumns=Number(next);gridViewportAnchor.adjust()}
  function isSelected(id:number){return isAssetSelected(selection,id)}
  function clearSelection(){selection=emptyAssetSelection<number>()}
  function selectVisible(){selection=selectVisibleAssets(items)}
  function selectAllMatching(){selection=selectAllMatchingAssets(items[0]??null)}
  function invertSelection(){selection=invertAssetSelection(selection)}
  function handleSelectionClick(id:number,event:MouseEvent){selection=event.shiftKey?applyShiftAssetRange(selection,items,id):toggleAssetSelected(selection,id)}
  function handleTileActivate(id:number,event:MouseEvent){if(interaction.consumeSuppressedClick(id))return;if(selectionActive||event.metaKey||event.ctrlKey||event.shiftKey){handleSelectionClick(id,event);return}viewer=true}
  function restoreSelected(){clearSelection()}
  function restoreAll(){clearSelection()}

  onMount(()=>()=>{gridViewportAnchor.destroy();interaction.destroy()});
</script>

<svelte:window onpointermove={interaction.move} onpointerup={interaction.finish} onpointercancel={interaction.cancel} onkeydown={(event)=>{if(event.key==='Escape'){if(interaction.isDragging())interaction.cancel();else if(viewer)viewer=false;else if(selectionActive)clearSelection()}}}/>

<V2PageLayout title="Restore" description="Review current Immich trash and restore individual, selected, or all trashed assets.">
  {#snippet headerActions()}<V2Button variant="primary" onclick={restoreAll}>Restore all</V2Button>{/snippet}
  <V2Zone>
    {#if selectionActive}
      <V2AssetSelectionToolbar {selectedCount} {total} noun="trashed assets" {allMatchingSelected} {allVisibleSelected} onselectvisible={selectVisible} onselectall={selectAllMatching} oninvert={invertSelection} onclear={clearSelection}>
        {#snippet actions()}<V2Button iconOnly variant="primary" title="Restore selected" ariaLabel="Restore selected" onclick={restoreSelected}><RotateCcw size={18}/></V2Button>{/snippet}
      </V2AssetSelectionToolbar>
    {:else}
      <V2Toolbar>
        <V2Badge text={`${total.toLocaleString()} trashed assets`}/>
        <V2Button iconOnly title="Select visible" ariaLabel="Select visible" onclick={selectVisible}><ListChecks size={18}/></V2Button>
        <V2Button iconOnly title={`Select all ${total.toLocaleString()} trashed assets`} ariaLabel={`Select all ${total.toLocaleString()} trashed assets`} onclick={selectAllMatching}><CheckCheck size={18}/></V2Button>
        {#snippet actions()}<V2RangeSlider label="Per row" min={2} max={10} step={1} bind:value={assetColumns} valueLabel={`${assetColumns}`} width={92} thumbSize={18} ariaLabel="Images per row" oninteractionstart={()=>gridViewportAnchor.begin(assetColumns)} onchange={setAssetColumns} oninteractionend={gridViewportAnchor.end}/><V2CollectionControls id="restore-results" {sort} sortFields={[{value:'deletedAt',label:'Deleted date'},{value:'takenAt',label:'Taken date'},{value:'name',label:'Name'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={(value)=>sort=value} onpagesize={setPageSize} onmode={setMode}/>{/snippet}
      </V2Toolbar>
    {/if}

    <V2AssetGrid columns={assetColumns} bind:element={assetGrid}>
      {#each items as i}<V2AssetTile index={i} assetId={i} label={`Trash item ${i+1}`} sublabel="Deleted recently" selected={isSelected(i)} selectionMode={selectionActive} onactivate={(event)=>handleTileActivate(i,event)} onselect={(event)=>handleSelectionClick(i,event)} onpreview={()=>viewer=true} onpointerdown={(event)=>interaction.start(i,event)}/>{/each}
    </V2AssetGrid>

    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={(next)=>page=next}/>{:else}<V2InfiniteFooter loaded={Math.min(loaded,total)} {total} batchSize={pageSize} noun="trashed assets" onloadmore={()=>loaded=Math.min(total,loaded+pageSize)}/>{/if}
  </V2Zone>
</V2PageLayout>

<V2Viewer open={viewer} title="Restore Viewer" mode="restore" onclose={()=>viewer=false}/>

<script lang="ts">
  import { onMount } from 'svelte';
  import { CheckCheck,ListChecks,RotateCcw } from '@lucide/svelte';
  import ConfirmDialog from '../components/V2ConfirmDialog.svelte';
  import V2AssetGrid from '../components/V2AssetGrid.svelte';
  import V2AssetSelectionToolbar from '../components/V2AssetSelectionToolbar.svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2CollectionFooter from '../components/V2CollectionFooter.svelte';
  import V2ErrorState from '../components/V2ErrorState.svelte';
  import V2OperationFeedback from '../components/V2OperationFeedback.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2RangeSlider from '../components/V2RangeSlider.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { createGridViewportAnchor } from '../components/gridViewportAnchor';
  import { createAssetGridSelectionInteraction } from '../components/assetGridSelectionInteraction';
  import { applyShiftAssetRange,emptyAssetSelection,getAssetSelectionCount,invertAssetSelection,isAllVisibleSelected,isAssetSelected,selectAllMatchingAssets,selectVisibleAssets,toggleAssetSelected,type AssetSelectionState } from '../components/assetSelection';
  import { createCollectionView } from '../state/collectionView.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage, mutationFeedback, type OperationFeedback } from '../data/mutationFeedback';
  import type { TrashAssetRecord, TrashSelectionTarget } from '../data/contracts';

  const collection=createCollectionView({pageSize:24,columns:4,resultModeStorageKey:'immichCompanionRestoreResultMode'});
  let sort=$state('deletedAt:desc'),viewer=$state(false),viewerAssetId=$state<string|null>(null),assetGrid=$state<HTMLElement|null>(null),selection=$state<AssetSelectionState<string>>(emptyAssetSelection<string>()),items=$state<TrashAssetRecord[]>([]),total=$state(0),nextCursor=$state<string|null>(null),loading=$state(false),mutating=$state(false),loadError=$state(''),feedback=$state<OperationFeedback|null>(null),retryTarget=$state<TrashSelectionTarget|null>(null),confirmRestoreAll=$state(false);
  const gridViewportAnchor=createGridViewportAnchor(()=>assetGrid);
  const itemIds=$derived(items.map((asset)=>asset.id));
  const selectedCount=$derived(getAssetSelectionCount(selection,total)),selectionActive=$derived(selectedCount>0),allMatchingSelected=$derived(selection.allMatchingSelected),allVisibleSelected=$derived(isAllVisibleSelected(selection,itemIds));
  const interaction=createAssetGridSelectionInteraction<string>({getItems:()=>itemIds,getSelection:()=>selection,setSelection:(next)=>selection=next,parseAssetId:(value)=>value});

  function parseSort(){const[fieldRaw,directionRaw]=sort.split(':');return{field:(fieldRaw==='takenAt'||fieldRaw==='name'?fieldRaw:'deletedAt') as 'deletedAt'|'takenAt'|'name',direction:(directionRaw==='asc'?'asc':'desc') as 'asc'|'desc'}}
  function target():TrashSelectionTarget{return selection.allMatchingSelected?{kind:'all',excludedIds:[...selection.excludedIds]}:{kind:'ids',ids:[...selection.selectedIds]}}
  async function refresh(reset=true){if(loading&&!reset)return;loading=true;try{if(reset)nextCursor=null;const query=collection.resultMode==='Pagination'?{page:collection.page,pageSize:collection.pageSize,sort:parseSort()}:{pageSize:collection.pageSize,cursor:reset?null:nextCursor,sort:parseSort()};const result=await libraryData.assets.searchTrash(query);items=collection.resultMode==='Infinite'&&!reset?[...items,...result.items]:result.items;total=result.total;nextCursor=result.nextCursor;collection.clampPage(total);loadError=''}catch(error){loadError=errorMessage(error,'Trash could not be loaded.')}finally{loading=false}}
  async function loadMore(){if(collection.resultMode!=='Infinite'||!nextCursor||loading)return;collection.loadMore(total);await refresh(false)}
  function setAssetColumns(next:number|string){collection.setColumns(next);gridViewportAnchor.adjust()}
  function isSelected(id:string){return isAssetSelected(selection,id)}
  function clearSelection(){selection=emptyAssetSelection<string>()}
  function selectVisible(){selection=selectVisibleAssets(itemIds)}function selectAllMatching(){selection=selectAllMatchingAssets(itemIds[0]??null)}function invertSelection(){selection=invertAssetSelection(selection)}
  function handleSelectionClick(id:string,event:MouseEvent){selection=event.shiftKey?applyShiftAssetRange(selection,itemIds,id):toggleAssetSelected(selection,id)}
  function openViewer(id:string){viewerAssetId=id;viewer=true}
  function handleTileActivate(id:string,event:MouseEvent){if(interaction.consumeSuppressedClick(id))return;if(selectionActive||event.metaKey||event.ctrlKey||event.shiftKey){handleSelectionClick(id,event);return}openViewer(id)}
  function setSort(value:string){sort=value;collection.reset();void refresh(true)}
  function setPageSize(value:number){collection.setPageSize(value,total);void refresh(true)}
  function setMode(value:ResultMode){collection.setMode(value);collection.reset();void refresh(true)}
  function setPage(value:number){collection.setPage(value);void refresh(true)}
  async function runRestore(nextTarget:TrashSelectionTarget){if(mutating)return;mutating=true;loadError='';try{const result=await libraryData.assets.restore(nextTarget);feedback=mutationFeedback('Restore',result);retryTarget=result.failed.length?{kind:'ids',ids:result.failed.map((failure)=>failure.id)}:null;clearSelection();await refresh(true)}catch(error){feedback=null;retryTarget=null;loadError=errorMessage(error,'Restore could not be completed.')}finally{mutating=false}}
  async function restoreSelected(){await runRestore(target())}
  async function restoreAll(){if(mutating)return;await runRestore({kind:'all',excludedIds:[]});collection.reset();confirmRestoreAll=false}
  onMount(()=>{void(async()=>{try{await libraryData.initialize();collection.hydrate();await refresh(true)}catch(error){loadError=errorMessage(error,'The trash data source could not be initialized.')}})();return()=>{gridViewportAnchor.destroy();interaction.destroy()}});
</script>

<svelte:window onpointermove={interaction.move} onpointerup={interaction.finish} onpointercancel={interaction.cancel} onkeydown={(event)=>{if(event.key==='Escape'){if(interaction.isDragging())interaction.cancel();else if(confirmRestoreAll){if(!mutating)confirmRestoreAll=false}else if(viewer)viewer=false;else if(selectionActive)clearSelection()}}}/>
<V2PageLayout title="Restore" description="Restore assets from the current trash data source while preserving provider-defined relationships.">
  {#snippet headerActions()}<V2Button variant="primary" disabled={total===0||loading||mutating} onclick={()=>confirmRestoreAll=true}>{mutating?'Restoring…':'Restore all'}</V2Button>{/snippet}
  <V2Zone>
    {#if loadError}<V2ErrorState title="Restore unavailable" message={loadError} onretry={()=>void refresh(true)}/>{/if}
    <V2OperationFeedback {feedback} retryLabel={retryTarget?'Retry failed':''} onretry={retryTarget?()=>void runRestore(retryTarget!):undefined}/>
    {#if selectionActive}<V2AssetSelectionToolbar {selectedCount} {total} noun="trash assets" {allMatchingSelected} {allVisibleSelected} onselectvisible={selectVisible} onselectall={selectAllMatching} oninvert={invertSelection} onclear={clearSelection}>{#snippet actions()}<V2Button iconOnly variant="primary" title="Restore selected" ariaLabel="Restore selected" disabled={mutating} onclick={restoreSelected}><RotateCcw size={18}/></V2Button>{/snippet}</V2AssetSelectionToolbar>{:else}<V2Toolbar><V2Badge text={`${total.toLocaleString()} in trash`}/><V2Badge text={mutating?'Restoring…':loading?'Loading…':'Ready'}/><V2Button iconOnly title="Select visible" ariaLabel="Select visible" disabled={total===0||mutating} onclick={selectVisible}><ListChecks size={18}/></V2Button><V2Button iconOnly title={`Select all ${total.toLocaleString()} trash assets`} ariaLabel={`Select all ${total.toLocaleString()} trash assets`} disabled={total===0||mutating} onclick={selectAllMatching}><CheckCheck size={18}/></V2Button>{#snippet actions()}<V2RangeSlider label="Per row" min={2} max={10} step={1} value={collection.columns} valueLabel={`${collection.columns}`} width={92} thumbSize={18} ariaLabel="Images per row" oninteractionstart={()=>gridViewportAnchor.begin(collection.columns)} onchange={setAssetColumns} oninteractionend={gridViewportAnchor.end}/><V2CollectionControls id="restore-results" {sort} sortFields={[{value:'deletedAt',label:'Deleted date'},{value:'takenAt',label:'Taken date'},{value:'name',label:'Name'}]} pageSize={collection.pageSize} pageSizes={[24,48,96]} resultMode={collection.resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>{/if}
    <V2AssetGrid columns={collection.columns} bind:element={assetGrid}>{#each items as asset,index}<V2AssetTile index={collection.resultMode==='Pagination'?(collection.page-1)*collection.pageSize+index:index} assetId={asset.id} label={asset.original_file_name} sublabel={asset.restore_path??`Taken ${new Date(asset.taken_at).toLocaleDateString()}`} image={()=>libraryData.media.thumbnail(asset)} selected={isSelected(asset.id)} selectionMode={selectionActive} onactivate={(event)=>handleTileActivate(asset.id,event)} onselect={(event)=>handleSelectionClick(asset.id,event)} onpreview={()=>openViewer(asset.id)} onpointerdown={(event)=>interaction.start(asset.id,event)}/>{/each}</V2AssetGrid>
    {#if total===0}<p class="v2-muted">{loading?'Loading trash…':loadError?'Trash could not be loaded.':'Trash is empty.'}</p>{:else}<V2CollectionFooter resultMode={collection.resultMode} page={collection.page} pageSize={collection.pageSize} {total} loaded={items.length} noun="trash assets" onpage={setPage} onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
<V2Viewer open={viewer} mode="restore" assetId={viewerAssetId} assetIds={itemIds} onclose={()=>viewer=false}/>
{#if confirmRestoreAll}<ConfirmDialog title="Restore all trash assets?" message={`Restore all ${total.toLocaleString()} assets currently in trash?`} confirmLabel="Restore all" icon="check" busy={mutating} loading onconfirm={()=>void restoreAll()} onclose={()=>{if(!mutating)confirmRestoreAll=false}}/>{/if}

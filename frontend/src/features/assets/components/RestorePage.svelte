<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { CheckCheck,ListChecks,RotateCcw,Trash2 } from '@lucide/svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import V2AssetGrid from './AssetGrid.svelte';
  import V2AssetSelectionToolbar from './AssetSelectionToolbar.svelte';
  import V2AssetTile from './AssetTile.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2CollectionControls, { type ResultMode } from '../../../lib/components/ui/CollectionControls.svelte';
  import V2CollectionFooter from '../../../lib/components/ui/CollectionFooter.svelte';
  import V2ErrorState from '../../../lib/components/ui/ErrorState.svelte';
  import OperationToast from '../../../lib/components/app/OperationToast.svelte';
  import V2PageLayout from '../../../lib/components/layout/PageLayout.svelte';
  import V2RangeSlider from '../../../lib/components/ui/RangeSlider.svelte';
  import V2Toolbar from '../../../lib/components/layout/Toolbar.svelte';
  import V2Viewer from './Viewer.svelte';
  import V2Zone from '../../../lib/components/layout/Zone.svelte';
  import { createGridViewportAnchor } from '../state/gridViewportAnchor';
  import { createAssetGridSelectionInteraction } from '../state/assetGridSelectionInteraction';
  import { applyShiftAssetRange,getAssetSelectionCount,isAllVisibleSelected,isAssetSelected,selectAllMatchingAssets,selectVisibleAssets,setAssetSelected,toggleAssetSelected } from '../state/assetSelection';
  import { createCollectionView } from '../../../lib/state/collectionView.svelte';
  import { CollectionRequestController } from '../../../lib/state/collectionRequest.svelte';
  import { OperationController } from '../../../lib/state/operationController.svelte';
  import { TransientAssetSelectionController } from '../state/transientAssetSelection.svelte';
  import { scrollViewedAssetIntoView, viewerPageForPosition } from '../state/viewerCollectionNavigation';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import { errorMessage, mutationFeedback, pendingOperationFeedback } from '../../../lib/api/mutationFeedback';
  import type { MutationResult, TrashAssetRecord, TrashPurgeMutationResult, TrashPurgePlan, TrashSelectionTarget, ViewerNavigationWindow } from '../../../lib/types/libraryContracts';

  type RestoreMutationResult = MutationResult & { restoredCount?: number; requestedCount?: number };

  let { selectionController }: { selectionController: TransientAssetSelectionController } = $props();
  const collection=createCollectionView({pageSize:24,columns:4,resultModeStorageKey:'immichCompanionRestoreResultMode'});
  let sort=$state('deletedAt:desc'),viewer=$state(false),viewerAssetId=$state<string|null>(null),assetGrid=$state<HTMLElement|null>(null),items=$state<TrashAssetRecord[]>([]),total=$state(0),nextCursor=$state<string|null>(null),retryTarget=$state<TrashSelectionTarget|null>(null),confirmRestoreAll=$state(false),purgePlanError=$state(''),pendingPurge=$state<{plan:TrashPurgePlan;target:TrashSelectionTarget}|null>(null);
  let viewerLastId:string|null=null,viewerLastPosition:number|null=null,viewerCollectionSync:Promise<void>=Promise.resolve();
  const collectionRequests=new CollectionRequestController();
  const operations=new OperationController();
  const loading=$derived(collectionRequests.loading),loadError=$derived(collectionRequests.error),mutating=$derived(operations.busy),operationError=$derived(operations.error),feedback=$derived(operations.feedback);
  const gridViewportAnchor=createGridViewportAnchor(()=>assetGrid);
  const selection=$derived(selectionController.snapshot());
  const itemIds=$derived(items.map((asset)=>asset.id));
  const selectedCount=$derived(getAssetSelectionCount(selection,total)),selectionActive=$derived(selectedCount>0),allMatchingSelected=$derived(selection.allMatchingSelected),allVisibleSelected=$derived(isAllVisibleSelected(selection,itemIds));
  const interaction=createAssetGridSelectionInteraction<string>({getItems:()=>itemIds,getSelection:()=>selectionController.snapshot(),setSelection:(next)=>selectionController.replace(next),parseAssetId:(value)=>value});

  function parseSort(){const[fieldRaw,directionRaw]=sort.split(':');return{field:(fieldRaw==='takenAt'||fieldRaw==='name'?fieldRaw:'deletedAt') as 'deletedAt'|'takenAt'|'name',direction:(directionRaw==='asc'?'asc':'desc') as 'asc'|'desc'}}
  function target():TrashSelectionTarget{return selection.allMatchingSelected?{kind:'all',excludedIds:[...selection.excludedIds]}:{kind:'ids',ids:[...selection.selectedIds]}}
  async function refresh(reset=true):Promise<boolean>{
    if(loading&&!reset)return false;
    if(reset)nextCursor=null;
    const requestedPage=collection.page;
    const query=collection.resultMode==='Pagination'?{page:requestedPage,pageSize:collection.pageSize,sort:parseSort()}:{pageSize:collection.pageSize,cursor:reset?null:nextCursor,sort:parseSort()};
    let clampedPage=requestedPage;
    const result=await collectionRequests.run((signal)=>libraryData.assets.searchTrash({...query,signal}),{
      fallbackError:'Trash could not be loaded.',
      mode:collection.resultMode==='Infinite'&&!reset?'append':'replace',
      apply:(response,mode)=>{
        items=mode==='append'?[...items,...response.items]:response.items;
        total=response.total;
        nextCursor=response.nextCursor;
        collection.clampPage(total);
        clampedPage=collection.page;
      },
    });
    if(result!==null&&collection.resultMode==='Pagination'&&reset&&clampedPage!==requestedPage)return refresh(true);
    return result!==null;
  }
  async function reconcile():Promise<void>{if(!await refresh(true))throw new Error(collectionRequests.error||'Restore was applied, but trash could not be refreshed.')}
  const restorePending=(phase:'applying'|'reconciling')=>pendingOperationFeedback('Restore',phase==='applying'?'applying':'refreshing');
  function restoreFeedback(result:RestoreMutationResult){
    if(result.restoredCount===undefined)return mutationFeedback('Restore',result);
    const failed=result.failed.length,succeeded=result.restoredCount,requested=result.requestedCount??succeeded+failed;
    if(failed===0)return{tone:'ok' as const,title:'Restore completed',detail:`${succeeded.toLocaleString()} of ${requested.toLocaleString()} assets restored.`,failures:[]};
    if(succeeded===0)return{tone:'bad' as const,title:'Restore failed',detail:`${failed.toLocaleString()} ${failed===1?'asset':'assets'} failed.`,failures:result.failed};
    return{tone:'warn' as const,title:'Restore partially completed',detail:`${succeeded.toLocaleString()} of ${requested.toLocaleString()} assets restored · ${failed.toLocaleString()} failed.`,failures:result.failed};
  }
  async function loadMore(){if(collection.resultMode!=='Infinite'||!nextCursor||loading)return;collection.loadMore(total);await refresh(false)}
  function setAssetColumns(next:number|string){collection.setColumns(next);gridViewportAnchor.adjust()}
  function isSelected(id:string){return isAssetSelected(selection,id)}
  function clearSelection(){selectionController.clear()}
  function selectVisible(){selectionController.replace(selectVisibleAssets(itemIds))}
  function selectAllMatching(){selectionController.replace(selectAllMatchingAssets(itemIds[0]??null))}
  function invertSelection(){let next=selectionController.snapshot();for(const id of itemIds)next=toggleAssetSelected(next,id);selectionController.replace(next)}
  function toggleSelection(id:string){selectionController.replace(toggleAssetSelected(selectionController.snapshot(),id))}
  function handleSelectionClick(id:string,event:MouseEvent){selectionController.replace(event.shiftKey?applyShiftAssetRange(selectionController.snapshot(),itemIds,id):toggleAssetSelected(selectionController.snapshot(),id))}
  function openViewer(id:string){const index=items.findIndex((item)=>item.id===id);viewerAssetId=id;viewerLastId=id;viewerLastPosition=index<0?null:collection.resultMode==='Pagination'?(collection.page-1)*collection.pageSize+index+1:index+1;viewer=true}
  async function synchronizeViewerCollection(id:string,navigation:ViewerNavigationWindow):Promise<void>{
    viewerLastId=id;
    if(navigation.position!==null)viewerLastPosition=navigation.position;
    const position=navigation.position??viewerLastPosition;
    if(position===null)return;
    if(collection.resultMode==='Pagination'){
      const targetPage=viewerPageForPosition(position,collection.pageSize);
      if(targetPage!==null&&(collection.page!==targetPage||!items.some((item)=>item.id===id))){collection.setPage(targetPage);await refresh(true)}
      return;
    }
    while(!items.some((item)=>item.id===id)&&items.length<position&&nextCursor){const before=items.length;await refresh(false);if(items.length===before)break}
  }
  function handleViewerNavigate(id:string,navigation:ViewerNavigationWindow):Promise<void>{const sync=synchronizeViewerCollection(id,navigation);viewerCollectionSync=sync.catch(()=>{});return sync}
  function closeViewer(){viewer=false;const id=viewerLastId;const pending=viewerCollectionSync;void(async()=>{await pending;await tick();scrollViewedAssetIntoView(assetGrid,id)})()}
  function handleTileActivate(id:string,event:MouseEvent){if(interaction.consumeSuppressedClick(id))return;if(selectionActive||event.metaKey||event.ctrlKey||event.shiftKey){handleSelectionClick(id,event);return}openViewer(id)}
  function setSort(value:string){sort=value;collection.reset();void refresh(true)}
  function setPageSize(value:number){collection.setPageSize(value,total);void refresh(true)}
  function setMode(value:ResultMode){collection.setMode(value);collection.reset();void refresh(true)}
  function setPage(value:number){collection.setPage(value);void refresh(true)}
  async function runRestore(nextTarget:TrashSelectionTarget,reconcileSelection:'target'|'single'='target'):Promise<MutationResult|null>{
    if(mutating)return null;
    operations.clearOutcome();
    const result=await operations.run('Restore',()=>libraryData.assets.restore(nextTarget) as Promise<RestoreMutationResult>,{
      pending:restorePending,
      outcome:restoreFeedback,
      reconcile,
      reconcileError:'Restore was applied, but the latest trash state could not be loaded.',
    });
    if(!result)return null;
    const failedIds=result.failed.map((failure)=>failure.id);
    retryTarget=failedIds.length?{kind:'ids',ids:failedIds}:null;
    if(reconcileSelection==='target')selectionController.replace(failedIds.length?selectVisibleAssets(failedIds):selectVisibleAssets([]));
    else if(nextTarget.kind==='ids'){
      let next=selectionController.snapshot();
      for(const id of nextTarget.ids){if(!failedIds.includes(id))next=setAssetSelected(next,id,false)}
      selectionController.replace(next);
    }
    return result;
  }
  async function restoreSelected(){await runRestore(target())}
  async function restoreVisible(id:string):Promise<boolean>{const result=await runRestore({kind:'ids',ids:[id]},'single');return Boolean(result&&result.affectedIds.includes(id)&&!result.failed.some((failure)=>failure.id===id))}
  async function restoreAll(){if(mutating)return;collection.reset();const result=await runRestore({kind:'all',excludedIds:[]});if(result)confirmRestoreAll=false}
  function purgeFeedback(result:TrashPurgeMutationResult){const failed=result.failed.length,succeeded=result.deletedCount,requested=result.requestedCount;if(failed===0&&result.verified)return{tone:'ok' as const,title:'Permanent deletion completed',detail:`${succeeded.toLocaleString()} of ${requested.toLocaleString()} assets permanently deleted.`,failures:[]};if(succeeded===0)return{tone:'bad' as const,title:'Permanent deletion failed',detail:`No assets were verified as deleted. ${failed.toLocaleString()} remain in trash.`,failures:result.failed};return{tone:'warn' as const,title:'Permanent deletion partially completed',detail:`${succeeded.toLocaleString()} of ${requested.toLocaleString()} assets permanently deleted.`,failures:result.failed}}
  async function executePurge(plan:TrashPurgePlan,nextTarget:TrashSelectionTarget):Promise<boolean>{
    const result=await operations.run('Permanent deletion',()=>libraryData.assets.executeTrashPurge(plan.id),{pending:(phase)=>pendingOperationFeedback('Permanent deletion',phase==='applying'?'applying':'refreshing'),outcome:purgeFeedback,reconcile,reconcileError:'Deletion was submitted, but the latest trash state could not be loaded.'});
    if(!result)return false;
    const failedIds=result.failed.map((failure)=>failure.id);
    if(nextTarget.kind==='ids')selectionController.replace(failedIds.length?selectVisibleAssets(failedIds):selectVisibleAssets([]));else selectionController.clear();
    pendingPurge=null;
    return result.deletedCount>0&&failedIds.length===0;
  }
  async function preparePurge(nextTarget:TrashSelectionTarget,executeImmediately=false):Promise<boolean>{
    if(mutating)return false;
    purgePlanError='';
    try{const plan=await libraryData.assets.planTrashPurge(nextTarget);if(executeImmediately)return executePurge(plan,nextTarget);pendingPurge={plan,target:nextTarget};return true}catch(error){purgePlanError=errorMessage(error,'Permanent deletion could not be planned.');return false}
  }
  async function deleteVisible(id:string):Promise<boolean>{return preparePurge({kind:'ids',ids:[id]},true)}
  onMount(()=>{void(async()=>{try{await libraryData.initialize();collection.hydrate();await refresh(true)}catch(error){collectionRequests.setError(errorMessage(error,'The trash data source could not be initialized.'))}})();return()=>{collectionRequests.cancel();gridViewportAnchor.destroy();interaction.destroy()}});
</script>

<svelte:window onpointermove={interaction.move} onpointerup={interaction.finish} onpointercancel={interaction.cancel} onkeydown={(event)=>{if(event.key==='Escape'){if(interaction.isDragging())interaction.cancel();else if(pendingPurge){if(!mutating)pendingPurge=null}else if(confirmRestoreAll){if(!mutating)confirmRestoreAll=false}else if(viewer)closeViewer();else if(selectionActive)clearSelection()}}}/>
<V2PageLayout title="Trash" description="Recover deleted assets or permanently remove them from the current data source.">
  {#snippet headerActions()}<V2Button variant="danger" disabled={total===0||loading||mutating} onclick={()=>void preparePurge({kind:'all',excludedIds:[]})}>Empty trash</V2Button><V2Button variant="primary" disabled={total===0||loading||mutating} onclick={()=>confirmRestoreAll=true}>{mutating?(operations.phase==='reconciling'?'Refreshing…':'Restoring…'):'Restore all'}</V2Button>{/snippet}
  <V2Zone>
    {#if loadError}<V2ErrorState title="Trash unavailable" message={loadError} onretry={()=>void refresh(true)}/>{/if}
    <OperationToast {feedback} error={operationError||purgePlanError} failureTitle="Trash operation failed" retryLabel={retryTarget?'Retry failed':''} onretry={retryTarget?()=>void runRestore(retryTarget!):undefined}/>
    {#if selectionActive}<V2AssetSelectionToolbar {selectedCount} {total} noun="trash assets" {allMatchingSelected} {allVisibleSelected} onselectvisible={selectVisible} onselectall={selectAllMatching} oninvert={invertSelection} onclear={clearSelection}>{#snippet actions()}<V2Button iconOnly variant="danger" title="Permanently delete selected" ariaLabel="Permanently delete selected" disabled={mutating} onclick={()=>void preparePurge(target())}><Trash2 size={18}/></V2Button><V2Button iconOnly variant="primary" title="Restore selected" ariaLabel="Restore selected" disabled={mutating} onclick={restoreSelected}><RotateCcw size={18}/></V2Button>{/snippet}</V2AssetSelectionToolbar>{:else}<V2Toolbar><V2Badge text={`${total.toLocaleString()} in trash`}/><V2Badge text={mutating?(operations.phase==='reconciling'?'Refreshing…':'Applying…'):loading?'Loading…':'Ready'}/><V2Button iconOnly title="Select visible" ariaLabel="Select visible" disabled={total===0||mutating} onclick={selectVisible}><ListChecks size={18}/></V2Button><V2Button iconOnly title={`Select all ${total.toLocaleString()} trash assets`} ariaLabel={`Select all ${total.toLocaleString()} trash assets`} disabled={total===0||mutating} onclick={selectAllMatching}><CheckCheck size={18}/></V2Button>{#snippet actions()}<V2RangeSlider label="Per row" min={2} max={10} step={1} value={collection.columns} valueLabel={`${collection.columns}`} width={92} thumbSize={18} ariaLabel="Images per row" oninteractionstart={()=>gridViewportAnchor.begin(collection.columns)} onchange={setAssetColumns} oninteractionend={gridViewportAnchor.end}/><V2CollectionControls id="restore-results" {sort} sortFields={[{value:'deletedAt',label:'Deleted date'},{value:'takenAt',label:'Taken date'},{value:'name',label:'Name'}]} pageSize={collection.pageSize} pageSizes={[24,48,96]} resultMode={collection.resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>{/if}
    <V2AssetGrid columns={collection.columns} bind:element={assetGrid}>{#each items as asset,index (asset.id)}<V2AssetTile index={collection.resultMode==='Pagination'?(collection.page-1)*collection.pageSize+index:index} assetId={asset.id} label={asset.original_file_name} sublabel={asset.restore_path??`Taken ${new Date(asset.taken_at).toLocaleDateString()}`} image={()=>libraryData.media.thumbnail(asset)} selected={isSelected(asset.id)} selectionMode={selectionActive} onactivate={(event)=>handleTileActivate(asset.id,event)} onselect={(event)=>handleSelectionClick(asset.id,event)} onpreview={()=>openViewer(asset.id)} onpointerdown={(event)=>interaction.start(asset.id,event)}/>{/each}</V2AssetGrid>
    {#if total===0}<p class="v2-muted">{loading?'Loading trash…':loadError?'Trash could not be loaded.':'Trash is empty. Deleted assets will appear here until they are restored or permanently removed.'}</p>{:else}<V2CollectionFooter resultMode={collection.resultMode} page={collection.page} pageSize={collection.pageSize} {total} loaded={items.length} noun="trash assets" onpage={setPage} onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
<V2Viewer open={viewer} mode="restore" assetId={viewerAssetId} assetIds={itemIds} restoreBusy={mutating} onclose={closeViewer} onnavigate={handleViewerNavigate} onrestore={restoreVisible} ondelete={deleteVisible} isselected={isSelected} ontoggleselection={toggleSelection}/>
{#if confirmRestoreAll}<ConfirmDialog title="Restore all trash assets?" message={`Restore all ${total.toLocaleString()} assets currently in trash?`} confirmLabel="Restore all" icon="check" pending={mutating} onconfirm={()=>void restoreAll()} onclose={()=>{if(!mutating)confirmRestoreAll=false}}/>{/if}
{#if pendingPurge}<ConfirmDialog title={pendingPurge.plan.mode==='empty_all'?'Empty trash permanently?':'Permanently delete selected assets?'} message={`${pendingPurge.plan.targetCount.toLocaleString()} ${pendingPurge.plan.targetCount===1?'asset':'assets'} will be permanently deleted from Immich. This cannot be undone.`} confirmLabel={pendingPurge.plan.mode==='empty_all'?'Empty trash':'Delete permanently'} icon="trash" destructive pending={mutating} onconfirm={()=>void executePurge(pendingPurge!.plan,pendingPurge!.target)} onclose={()=>{if(!mutating)pendingPurge=null}}/>{/if}

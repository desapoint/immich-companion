<script lang="ts">
  import { onMount } from 'svelte';
  import ConfirmDialog from '../components/V2ConfirmDialog.svelte';
  import { visibleSelectionState } from '../components/collectionSelection';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2ErrorState from '../components/V2ErrorState.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2InfiniteFooter from '../components/V2InfiniteFooter.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Modal from '../components/V2Modal.svelte';
  import V2OperationToast from '../components/V2OperationToast.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2RoundCheckbox from '../components/V2RoundCheckbox.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2SortableHeader from '../components/V2SortableHeader.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Table from '../components/V2Table.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage, mutationFeedback, pendingOperationFeedback } from '../data/mutationFeedback';
  import type { AlbumRecord, CollectionDeletePlan } from '../data/contracts';
  import { CollectionRequestController } from '../state/collectionRequest.svelte';
  import { OperationController } from '../state/operationController.svelte';
  import { SelectionWorkspaceController } from '../state/assetSelectionWorkspace.svelte';

  let { onfilterassets }: { onfilterassets: (albumIds: string[]) => void } = $props();

  type AlbumModal={id:number;mode:'create'|'edit';albumId:string;name:string;description:string};
  let page=$state(1),pageSize=$state(24),resultMode=$state<ResultMode>('Pagination'),sort=$state('name:asc'),query=$state(''),queryDraft=$state(''),total=$state(0),albums=$state<AlbumRecord[]>([]),nextCursor=$state<string|null>(null),retryDeleteIds=$state<string[]>([]),deleteDialogOpen=$state(false),pendingPlan=$state<CollectionDeletePlan|null>(null),selectionScope=$state<'Current page'|'All matching'>(typeof sessionStorage!=='undefined'&&sessionStorage.getItem('immich-companion:v2:album-selection-scope')==='All matching'?'All matching':'Current page'),searchSelectionDialog=$state(false);
  let modalSequence=0,modals=$state<AlbumModal[]>([]);
  const selection=new SelectionWorkspaceController(libraryData.albums,typeof sessionStorage==='undefined'?null:sessionStorage,'immich-companion:v2:album-selection');
  const collectionRequests=new CollectionRequestController();
  const operations=new OperationController();
  const loading=$derived(collectionRequests.loading),loadError=$derived(collectionRequests.error),mutating=$derived(operations.busy),operationError=$derived(operations.error),feedback=$derived(operations.feedback);
  const visibleIds=$derived(albums.map((album)=>album.id));
  const visibleSelection=$derived(visibleSelectionState([...selection.visibleSelectedIds],visibleIds));
  const selectedIds=$derived([...selection.visibleSelectedIds]);
  $effect(()=>{if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immich-companion:v2:album-selection-scope',selectionScope)});

  function parseSort(){const[fieldRaw,directionRaw]=sort.split(':');return{field:(fieldRaw==='assets'||fieldRaw==='description'?fieldRaw:'name') as 'name'|'assets'|'description',direction:(directionRaw==='desc'?'desc':'asc') as 'asc'|'desc'}}
  async function refresh(reset=true):Promise<boolean>{
    if(loading&&!reset)return false;
    const mode=resultMode,requestedPage=page,requestedPageSize=pageSize,requestedQuery=query,requestedSort=parseSort(),cursor=reset?null:nextCursor;
    if(reset)nextCursor=null;
    const response=await collectionRequests.run((signal)=>libraryData.albums.search(mode==='Pagination'
      ?{page:requestedPage,pageSize:requestedPageSize,query:requestedQuery,sort:requestedSort,signal}
      :{pageSize:requestedPageSize,query:requestedQuery,sort:requestedSort,cursor,signal}),{
        fallbackError:'Albums could not be loaded.',
        mode:mode==='Infinite'&&!reset?'append':'replace',
        apply:(result,loadMode)=>{
          albums=loadMode==='append'?[...albums,...result.items]:result.items;
          total=result.total;
          nextCursor=result.nextCursor;
        },
      });
    if(!response)return false;
    await selection.refreshVisible(albums.map((album)=>album.id));
    await selection.refreshMatching({query:requestedQuery});
    const lastPage=Math.max(1,Math.ceil(total/requestedPageSize));
    if(mode==='Pagination'&&requestedPage>lastPage){page=lastPage;return refresh(true)}
    return true;
  }
  async function reconcile(action:string):Promise<void>{if(!await refresh(true))throw new Error(collectionRequests.error||`${action} was applied, but albums could not be refreshed.`)}
  function pending(action:string){return(phase:'applying'|'reconciling')=>pendingOperationFeedback(action,phase==='applying'?'applying':'refreshing')}
  function setPageSize(next:number){pageSize=next;page=1;void refresh(true)}
  function setMode(mode:ResultMode){resultMode=mode;page=1;void refresh(true)}
  function setSort(value:string){sort=value;page=1;void refresh(true)}
  function setPage(next:number){page=next;void refresh(true)}
  function applySearch(dismiss:boolean){if(dismiss)selection.clear();query=queryDraft;page=1;searchSelectionDialog=false;void refresh(true)}
  function submitSearch(){if(loading||mutating)return;if(selection.active&&queryDraft!==query){searchSelectionDialog=true;return}applySearch(false)}
  function handleSearchKeydown(event:KeyboardEvent){if(event.key!=='Enter'||event.isComposing)return;event.preventDefault();submitSearch()}
  async function loadMore(){if(resultMode!=='Infinite'||!nextCursor||loading)return;await refresh(false)}
  function toggleSelection(id:string,checked:boolean){selection.setMembers([id],checked,id)}
  function toggleVisible(){if(selectionScope==='All matching'){void selection.setMatching({query},visibleIds,!selection.allMatchingSelected).catch((error)=>operations.setError(error,'Matching albums could not be selected.'));return}selection.setMembers(visibleIds,visibleSelection!=='all',visibleIds[0]??null)}
  async function requestDelete(ids:string[]=[]){if(mutating)return;try{let selectionId:string;if(ids.length){const temporary=await libraryData.albums.createSelection();await libraryData.albums.updateSelectionMembers(temporary.id,ids,true,temporary.revision);selectionId=temporary.id}else{await selection.flush();if(!selection.selectionId)return;selectionId=selection.selectionId}pendingPlan=await libraryData.albums.planDelete(selectionId);deleteDialogOpen=true}catch(error){operations.setError(error,'Albums could not be prepared for deletion.')}}
  async function deleteIds(ids:string[]){
    if(!ids.length||mutating)return;
    operations.clearOutcome();
    const result=await operations.run('Delete albums',()=>libraryData.albums.delete(ids),{
      pending:pending('Delete albums'),
      outcome:(value)=>mutationFeedback('Delete albums',value),
      reconcile:()=>reconcile('Delete albums'),
      reconcileError:'Albums were deleted, but the latest album list could not be loaded.',
    });
    if(!result)return;
    retryDeleteIds=result.failed.map((failure)=>failure.id);
    await selection.refreshVisible(visibleIds);
  }
  async function confirmDelete(){const plan=pendingPlan;if(!plan||mutating)return;try{const result=await libraryData.albums.executeDelete(plan.id);retryDeleteIds=result.results.filter((item)=>item.status==='failed').map((item)=>item.id);const removed=result.results.filter((item)=>item.status!=='failed').map((item)=>item.id);if(removed.length)selection.setMembers(removed,false);deleteDialogOpen=false;pendingPlan=null;await refresh(true)}catch(error){operations.setError(error,'Albums could not be deleted.')}}
  function deleteSelected(){void requestDelete()}
  function openCreate(){modals=[...modals,{id:++modalSequence,mode:'create',albumId:'',name:'',description:''}]}
  function openEdit(album:AlbumRecord){modals=[...modals,{id:++modalSequence,mode:'edit',albumId:album.id,name:album.album_name,description:album.description}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<AlbumModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  async function saveModal(modal:AlbumModal){
    if(!modal.name.trim()||mutating)return;
    operations.clearOutcome();
    if(modal.mode==='create'){
      const created=await operations.run('Create album',async()=>{const value=await libraryData.albums.create(modal.name,modal.description);if(!value)throw new Error('The album was not created.');return value},{
        pending:pending('Create album'),
        outcome:(value)=>({tone:'ok',title:'Album created',detail:`${value.album_name} was created.`,failures:[]}),
        reconcile:()=>reconcile('Create album'),
        reconcileError:'The album was created, but the latest album list could not be loaded.',
      });
      if(created)closeModal(modal.id);
      return;
    }
    const result=await operations.run('Update album',()=>libraryData.albums.update(modal.albumId,{name:modal.name,description:modal.description}),{
      pending:pending('Update album'),
      outcome:(value)=>mutationFeedback('Update album',value),
      reconcile:()=>reconcile('Update album'),
      reconcileError:'The album was updated, but the latest album list could not be loaded.',
    });
    if(result&&!result.failed.length)closeModal(modal.id);
  }
  function deleteRow(id:string){void requestDelete([id])}
  function filterAssets(album:AlbumRecord){onfilterassets([album.id])}
  onMount(()=>{let mounted=true;void(async()=>{try{await libraryData.initialize();if(mounted)await refresh(true)}catch(error){if(mounted)collectionRequests.setError(errorMessage(error,'The album data source could not be initialized.'))}})();return()=>{mounted=false;collectionRequests.cancel()}});
</script>

<V2PageLayout title="Albums" description="Search, sort, create, edit, delete and use albums to filter the current asset workspace.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={!selection.active||mutating} onclick={deleteSelected}>Delete selected{selection.selectedCount?` (${selection.selectedCount})`:''}</V2Button><V2Button variant="primary" disabled={mutating} onclick={openCreate}>Create album</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={queryDraft} placeholder="Search albums…" oninput={(event)=>queryDraft=event.currentTarget.value} onkeydown={handleSearchKeydown}><V2Button variant="primary" disabled={loading||mutating} onclick={submitSearch}>Search</V2Button></V2Stack></V2Section></V2Zone>{/snippet}
  <V2Zone>
    {#if loadError}<V2ErrorState title="Albums could not be loaded" message={loadError} onretry={()=>void refresh(true)}/>{/if}
    <V2OperationToast {feedback} error={operationError} failureTitle="Album operation failed" retryLabel={retryDeleteIds.length?'Retry failed':''} onretry={retryDeleteIds.length?()=>requestDelete([...retryDeleteIds]):undefined}/>
    <V2Toolbar><V2Badge text={`${total} album${total===1?'':'s'}`}/><V2Badge text={`${selection.selectedCount} selected`}/><V2Badge text={mutating?(operations.phase==='reconciling'?'Refreshing…':'Applying change…'):loading?'Loading…':'Ready'}/>{#snippet actions()}<V2Segmented items={['Current page','All matching']} active={selectionScope} onselect={(value)=>selectionScope=value as typeof selectionScope} ariaLabel="Album selection scope"/><V2CollectionControls id="album-results" {sort} sortFields={[{value:'name',label:'Name'},{value:'assets',label:'Assets'},{value:'description',label:'Description'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table layout="fixed"><thead><tr><th class="v2-collection-check-column"><V2RoundCheckbox size="sm" checked={selectionScope==='All matching'?selection.allMatchingSelected:visibleSelection==='all'} indeterminate={selectionScope==='All matching'?selection.matchingSelectedCount>0&&!selection.allMatchingSelected:visibleSelection==='some'} disabled={!albums.length||mutating} ariaLabel={selectionScope==='All matching'?(selection.allMatchingSelected?'Unselect all matching albums':'Select all matching albums'):(visibleSelection==='all'?'Unselect all visible albums':'Select all visible albums')} onclick={toggleVisible}/></th><V2SortableHeader field="name" label="Name" {sort} onsort={setSort}/><V2SortableHeader field="assets" label="Assets" {sort} class="v2-collection-count-column" onsort={setSort}/><V2SortableHeader field="description" label="Description" {sort} class="v2-collection-description-column" onsort={setSort}/><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>{#each albums as album (album.id)}<tr><td class="v2-collection-check-column"><V2RoundCheckbox size="sm" checked={selectedIds.includes(album.id)} disabled={mutating} ariaLabel={`${selectedIds.includes(album.id)?'Unselect':'Select'} ${album.album_name}`} onclick={()=>toggleSelection(album.id,!selectedIds.includes(album.id))}/></td><td><b class="v2-collection-title">{album.album_name}</b></td><td class="v2-collection-count-column">{album.asset_count.toLocaleString()}</td><td class="v2-collection-description-column v2-muted"><span class="v2-collection-description">{album.description||'—'}</span></td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button disabled={mutating} onclick={()=>filterAssets(album)}>Filter assets</V2Button><V2Button disabled={mutating} onclick={()=>openEdit(album)}>Edit</V2Button><V2Button variant="danger" disabled={mutating} onclick={()=>deleteRow(album.id)}>Delete</V2Button></V2Inline></td></tr>{:else}<tr><td colspan="5" class="v2-muted">{loading?'Loading albums…':loadError?'Albums could not be loaded.':'No albums match this search.'}</td></tr>{/each}</tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={setPage}/>{:else}<V2InfiniteFooter loaded={albums.length} {total} batchSize={pageSize} noun="albums" onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
{#each modals as modal (modal.id)}<V2Modal id={`album-modal-${modal.id}`} title={modal.mode==='create'?'Create album':`Edit ${modal.name}`} description={modal.mode==='create'?'Add an album to the current data source.':'Update this album.'} size="md" onclose={()=>{if(!mutating)closeModal(modal.id)}}><V2Stack gap="md"><V2Field label="Name" value={modal.name} onvalueinput={(value)=>updateModal(modal.id,{name:value})}/><V2Field label="Description" value={modal.description} multiline={true} onchange={(value)=>updateModal(modal.id,{description:value})}/><V2Section title="Shared data"><V2Card><span class="v2-small v2-muted">Changes are reflected in Assets relationship filters and counts after the repository refreshes.</span></V2Card></V2Section></V2Stack>{#snippet footer()}<V2Button disabled={mutating} onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={mutating||!modal.name.trim()} onclick={()=>void saveModal(modal)}>{mutating?(operations.phase==='reconciling'?'Refreshing…':'Saving…'):modal.mode==='create'?'Create album':'Save changes'}</V2Button>{/snippet}</V2Modal>{/each}
{#if deleteDialogOpen&&pendingPlan}<ConfirmDialog title={pendingPlan.targetCount===1?'Delete album?':'Delete albums?'} message={pendingPlan.targetCount===1?'This album will be deleted. Assets are not deleted.':`Delete ${pendingPlan.targetCount} selected albums? Assets are not deleted.`} confirmLabel={pendingPlan.targetCount===1?'Delete album':`Delete ${pendingPlan.targetCount} albums`} icon="trash" destructive={true} pending={mutating} onconfirm={()=>void confirmDelete()} onclose={()=>{if(!mutating){deleteDialogOpen=false;pendingPlan=null}}}/>{/if}
{#if searchSelectionDialog}<ConfirmDialog title="Selection and search" message="Keep the current album selection while applying this search, or dismiss it first." confirmLabel="Dismiss selection" cancelLabel="Keep selection" destructive={true} onconfirm={()=>applySearch(true)} onclose={()=>applySearch(false)}/>{/if}

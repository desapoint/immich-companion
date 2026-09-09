<script lang="ts">
  import { onMount } from 'svelte';
  import ConfirmDialog from '../components/V2ConfirmDialog.svelte';
  import { toggleVisibleSelection, visibleSelectionState } from '../components/collectionSelection';
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
  import V2SortableHeader from '../components/V2SortableHeader.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Table from '../components/V2Table.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage, mutationFeedback, pendingOperationFeedback } from '../data/mutationFeedback';
  import type { AlbumRecord } from '../data/contracts';
  import { CollectionRequestController } from '../state/collectionRequest.svelte';
  import { OperationController } from '../state/operationController.svelte';

  let { onfilterassets }: { onfilterassets: (albumIds: string[]) => void } = $props();

  type AlbumModal={id:number;mode:'create'|'edit';albumId:string;name:string;description:string};
  let page=$state(1),pageSize=$state(24),resultMode=$state<ResultMode>('Pagination'),sort=$state('name:asc'),query=$state(''),total=$state(0),albums=$state<AlbumRecord[]>([]),nextCursor=$state<string|null>(null),retryDeleteIds=$state<string[]>([]),pendingDeleteIds=$state<string[]>([]),deleteDialogOpen=$state(false);
  let modalSequence=0,modals=$state<AlbumModal[]>([]),selectedIds=$state<string[]>([]);
  const collectionRequests=new CollectionRequestController();
  const operations=new OperationController();
  const loading=$derived(collectionRequests.loading),loadError=$derived(collectionRequests.error),mutating=$derived(operations.busy),operationError=$derived(operations.error),feedback=$derived(operations.feedback);
  const visibleIds=$derived(albums.map((album)=>album.id));
  const visibleSelection=$derived(visibleSelectionState(selectedIds,visibleIds));

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
  function submitSearch(){if(loading||mutating)return;page=1;void refresh(true)}
  function handleSearchKeydown(event:KeyboardEvent){if(event.key!=='Enter'||event.isComposing)return;event.preventDefault();submitSearch()}
  async function loadMore(){if(resultMode!=='Infinite'||!nextCursor||loading)return;await refresh(false)}
  function toggleSelection(id:string,checked:boolean){selectedIds=checked?[...new Set([...selectedIds,id])]:selectedIds.filter((value)=>value!==id)}
  function toggleVisible(){selectedIds=toggleVisibleSelection(selectedIds,visibleIds)}
  function requestDelete(ids:string[]){if(!ids.length||mutating)return;pendingDeleteIds=[...ids];deleteDialogOpen=true}
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
    selectedIds=selectedIds.filter((id)=>retryDeleteIds.includes(id));
  }
  async function confirmDelete(){const ids=[...pendingDeleteIds];if(!ids.length||mutating)return;await deleteIds(ids);deleteDialogOpen=false;pendingDeleteIds=[]}
  function deleteSelected(){requestDelete([...selectedIds])}
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
  function deleteRow(id:string){requestDelete([id])}
  function filterAssets(album:AlbumRecord){onfilterassets([album.id])}
  onMount(()=>{let mounted=true;void(async()=>{try{await libraryData.initialize();if(mounted)await refresh(true)}catch(error){if(mounted)collectionRequests.setError(errorMessage(error,'The album data source could not be initialized.'))}})();return()=>{mounted=false;collectionRequests.cancel()}});
</script>

<V2PageLayout title="Albums" description="Search, sort, create, edit, delete and use albums to filter the current asset workspace.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={!selectedIds.length||mutating} onclick={deleteSelected}>Delete selected{selectedIds.length?` (${selectedIds.length})`:''}</V2Button><V2Button variant="primary" disabled={mutating} onclick={openCreate}>Create album</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder="Search albums…" oninput={(event)=>query=event.currentTarget.value} onkeydown={handleSearchKeydown}><V2Button variant="primary" disabled={loading||mutating} onclick={submitSearch}>Search</V2Button></V2Stack></V2Section></V2Zone>{/snippet}
  <V2Zone>
    {#if loadError}<V2ErrorState title="Albums could not be loaded" message={loadError} onretry={()=>void refresh(true)}/>{/if}
    <V2OperationToast {feedback} error={operationError} failureTitle="Album operation failed" retryLabel={retryDeleteIds.length?'Retry failed':''} onretry={retryDeleteIds.length?()=>requestDelete([...retryDeleteIds]):undefined}/>
    <V2Toolbar><V2Badge text={`${total} album${total===1?'':'s'}`}/><V2Badge text={mutating?(operations.phase==='reconciling'?'Refreshing…':'Applying change…'):loading?'Loading…':'Ready'}/>{#snippet actions()}<V2CollectionControls id="album-results" {sort} sortFields={[{value:'name',label:'Name'},{value:'assets',label:'Assets'},{value:'description',label:'Description'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table layout="fixed"><thead><tr><th class="v2-collection-check-column"><V2RoundCheckbox size="sm" checked={visibleSelection==='all'} indeterminate={visibleSelection==='some'} disabled={!albums.length||mutating} ariaLabel={visibleSelection==='all'?'Unselect all visible albums':'Select all visible albums'} onclick={toggleVisible}/></th><V2SortableHeader field="name" label="Name" {sort} onsort={setSort}/><V2SortableHeader field="assets" label="Assets" {sort} class="v2-collection-count-column" onsort={setSort}/><V2SortableHeader field="description" label="Description" {sort} class="v2-collection-description-column" onsort={setSort}/><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>{#each albums as album (album.id)}<tr><td class="v2-collection-check-column"><V2RoundCheckbox size="sm" checked={selectedIds.includes(album.id)} disabled={mutating} ariaLabel={`${selectedIds.includes(album.id)?'Unselect':'Select'} ${album.album_name}`} onclick={()=>toggleSelection(album.id,!selectedIds.includes(album.id))}/></td><td><b class="v2-collection-title">{album.album_name}</b></td><td class="v2-collection-count-column">{album.asset_count.toLocaleString()}</td><td class="v2-collection-description-column v2-muted"><span class="v2-collection-description">{album.description||'—'}</span></td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button disabled={mutating} onclick={()=>filterAssets(album)}>Filter assets</V2Button><V2Button disabled={mutating} onclick={()=>openEdit(album)}>Edit</V2Button><V2Button variant="danger" disabled={mutating} onclick={()=>deleteRow(album.id)}>Delete</V2Button></V2Inline></td></tr>{:else}<tr><td colspan="5" class="v2-muted">{loading?'Loading albums…':loadError?'Albums could not be loaded.':'No albums match this search.'}</td></tr>{/each}</tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={setPage}/>{:else}<V2InfiniteFooter loaded={albums.length} {total} batchSize={pageSize} noun="albums" onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
{#each modals as modal (modal.id)}<V2Modal id={`album-modal-${modal.id}`} title={modal.mode==='create'?'Create album':`Edit ${modal.name}`} description={modal.mode==='create'?'Add an album to the current data source.':'Update this album.'} size="md" onclose={()=>{if(!mutating)closeModal(modal.id)}}><V2Stack gap="md"><V2Field label="Name" value={modal.name} onvalueinput={(value)=>updateModal(modal.id,{name:value})}/><V2Field label="Description" value={modal.description} multiline={true} onchange={(value)=>updateModal(modal.id,{description:value})}/><V2Section title="Shared data"><V2Card><span class="v2-small v2-muted">Changes are reflected in Assets relationship filters and counts after the repository refreshes.</span></V2Card></V2Section></V2Stack>{#snippet footer()}<V2Button disabled={mutating} onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={mutating||!modal.name.trim()} onclick={()=>void saveModal(modal)}>{mutating?(operations.phase==='reconciling'?'Refreshing…':'Saving…'):modal.mode==='create'?'Create album':'Save changes'}</V2Button>{/snippet}</V2Modal>{/each}
{#if deleteDialogOpen}<ConfirmDialog title={pendingDeleteIds.length===1?'Delete album?':'Delete albums?'} message={pendingDeleteIds.length===1?'This album will be deleted. Assets are not deleted.':`Delete ${pendingDeleteIds.length} selected albums? Assets are not deleted.`} confirmLabel={pendingDeleteIds.length===1?'Delete album':`Delete ${pendingDeleteIds.length} albums`} icon="trash" destructive={true} pending={mutating} onconfirm={()=>void confirmDelete()} onclose={()=>{if(!mutating){deleteDialogOpen=false;pendingDeleteIds=[]}}}/>{/if}

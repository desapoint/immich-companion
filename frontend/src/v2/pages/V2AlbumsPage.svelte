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
  import V2OperationFeedback from '../components/V2OperationFeedback.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2RoundCheckbox from '../components/V2RoundCheckbox.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Table from '../components/V2Table.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage, mutationFeedback, type OperationFeedback } from '../data/mutationFeedback';
  import type { AlbumRecord } from '../data/contracts';
  import { LatestRequestController } from '../state/latestRequest';

  type AlbumModal={id:number;mode:'create'|'edit';albumId:string;name:string;description:string};
  let page=$state(1),pageSize=$state(24),resultMode=$state<ResultMode>('Pagination'),sort=$state('name:asc'),query=$state(''),total=$state(0),albums=$state<AlbumRecord[]>([]),nextCursor=$state<string|null>(null),loading=$state(false),mutating=$state(false),loadError=$state(''),feedback=$state<OperationFeedback|null>(null),retryDeleteIds=$state<string[]>([]),pendingDeleteIds=$state<string[]>([]),deleteDialogOpen=$state(false);
  let modalSequence=0,modals=$state<AlbumModal[]>([]),selectedIds=$state<string[]>([]);
  const requests=new LatestRequestController();
  const visibleIds=$derived(albums.map((album)=>album.id));
  const visibleSelection=$derived(visibleSelectionState(selectedIds,visibleIds));

  function parseSort(){const[fieldRaw,directionRaw]=sort.split(':');return{field:(fieldRaw==='assets'||fieldRaw==='description'?fieldRaw:'name') as 'name'|'assets'|'description',direction:(directionRaw==='desc'?'desc':'asc') as 'asc'|'desc'}}
  async function refresh(reset=true):Promise<void>{
    if(loading&&!reset)return;
    const mode=resultMode,requestedPage=page,requestedPageSize=pageSize,requestedQuery=query,requestedSort=parseSort(),cursor=reset?null:nextCursor;
    const request=requests.begin();
    loading=true;
    if(reset)nextCursor=null;
    try{
      const response=await libraryData.albums.search(mode==='Pagination'
        ?{page:requestedPage,pageSize:requestedPageSize,query:requestedQuery,sort:requestedSort,signal:request.signal}
        :{pageSize:requestedPageSize,query:requestedQuery,sort:requestedSort,cursor,signal:request.signal});
      if(!requests.isCurrent(request))return;
      albums=mode==='Infinite'&&!reset?[...albums,...response.items]:response.items;
      total=response.total;
      nextCursor=response.nextCursor;
      loadError='';
      const lastPage=Math.max(1,Math.ceil(total/requestedPageSize));
      if(mode==='Pagination'&&requestedPage>lastPage){page=lastPage;await refresh(true)}
    }catch(error){if(requests.isCurrent(request))loadError=errorMessage(error,'Albums could not be loaded.')}
    finally{if(requests.finish(request))loading=false}
  }
  function setPageSize(next:number){pageSize=next;page=1;void refresh(true)}
  function setMode(mode:ResultMode){resultMode=mode;page=1;void refresh(true)}
  function setSort(value:string){sort=value;page=1;void refresh(true)}
  function setPage(next:number){page=next;void refresh(true)}
  async function loadMore(){if(resultMode!=='Infinite'||!nextCursor||loading)return;await refresh(false)}
  function toggleSelection(id:string,checked:boolean){selectedIds=checked?[...new Set([...selectedIds,id])]:selectedIds.filter((value)=>value!==id)}
  function toggleVisible(){selectedIds=toggleVisibleSelection(selectedIds,visibleIds)}
  function requestDelete(ids:string[]){if(!ids.length||mutating)return;pendingDeleteIds=[...ids];deleteDialogOpen=true}
  async function deleteIds(ids:string[]){if(!ids.length||mutating)return;mutating=true;loadError='';try{const result=await libraryData.albums.delete(ids);feedback=mutationFeedback('Delete albums',result);retryDeleteIds=result.failed.map((failure)=>failure.id);selectedIds=selectedIds.filter((id)=>retryDeleteIds.includes(id));await refresh(true)}catch(error){feedback=null;retryDeleteIds=[];loadError=errorMessage(error,'Albums could not be deleted.')}finally{mutating=false}}
  async function confirmDelete(){const ids=[...pendingDeleteIds];if(!ids.length||mutating)return;await deleteIds(ids);deleteDialogOpen=false;pendingDeleteIds=[]}
  function deleteSelected(){requestDelete([...selectedIds])}
  function openCreate(){modals=[...modals,{id:++modalSequence,mode:'create',albumId:'',name:'',description:''}]}
  function openEdit(album:AlbumRecord){modals=[...modals,{id:++modalSequence,mode:'edit',albumId:album.id,name:album.album_name,description:album.description}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<AlbumModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  async function saveModal(modal:AlbumModal){if(!modal.name.trim()||mutating)return;mutating=true;loadError='';try{if(modal.mode==='create'){const created=await libraryData.albums.create(modal.name,modal.description);if(!created)throw new Error('The album was not created.');feedback={tone:'ok',title:'Album created',detail:`${created.album_name} was created.`,failures:[]}}else{const result=await libraryData.albums.update(modal.albumId,{name:modal.name,description:modal.description});feedback=mutationFeedback('Update album',result);if(result.failed.length)return}closeModal(modal.id);await refresh(true)}catch(error){feedback=null;loadError=errorMessage(error,'The album could not be saved.')}finally{mutating=false}}
  function deleteRow(id:string){requestDelete([id])}
  function filterAssets(albumId:string){if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immichCompanionV2AssetFilterHandoff',JSON.stringify({albumIds:[albumId],tagIds:[]}));window.location.assign('/v2/assets')}
  onMount(()=>{let mounted=true;void(async()=>{try{await libraryData.initialize();if(mounted)await refresh(true)}catch(error){if(mounted)loadError=errorMessage(error,'The album data source could not be initialized.')}})();return()=>{mounted=false;requests.cancel()}});
</script>

<V2PageLayout title="Albums" description="Search, sort, create, edit, delete and use albums to filter the current asset workspace.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={!selectedIds.length||mutating} onclick={deleteSelected}>Delete selected{selectedIds.length?` (${selectedIds.length})`:''}</V2Button><V2Button variant="primary" disabled={mutating} onclick={openCreate}>Create album</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder="Search albums…" oninput={(event)=>query=event.currentTarget.value}><V2Button variant="primary" disabled={loading||mutating} onclick={()=>{page=1;void refresh(true)}}>Search</V2Button></V2Stack></V2Section></V2Zone>{/snippet}
  <V2Zone>
    {#if loadError}<V2ErrorState title="Album operation unavailable" message={loadError} onretry={()=>void refresh(true)}/>{/if}
    <V2OperationFeedback {feedback} retryLabel={retryDeleteIds.length?'Retry failed':''} onretry={retryDeleteIds.length?()=>requestDelete([...retryDeleteIds]):undefined}/>
    <V2Toolbar><V2Badge text={`${total} album${total===1?'':'s'}`}/><V2Badge text={mutating?'Applying change…':loading?'Loading…':'Ready'}/>{#snippet actions()}<V2CollectionControls id="album-results" {sort} sortFields={[{value:'name',label:'Name'},{value:'assets',label:'Assets'},{value:'description',label:'Description'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table layout="fixed"><thead><tr><th class="v2-collection-check-column"><V2RoundCheckbox size="sm" checked={visibleSelection==='all'} indeterminate={visibleSelection==='some'} disabled={!albums.length||mutating} ariaLabel={visibleSelection==='all'?'Unselect all visible albums':'Select all visible albums'} onclick={toggleVisible}/></th><th>Name</th><th class="v2-collection-count-column">Assets</th><th class="v2-collection-description-column">Description</th><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>{#each albums as album (album.id)}<tr><td class="v2-collection-check-column"><V2RoundCheckbox size="sm" checked={selectedIds.includes(album.id)} disabled={mutating} ariaLabel={`${selectedIds.includes(album.id)?'Unselect':'Select'} ${album.album_name}`} onclick={()=>toggleSelection(album.id,!selectedIds.includes(album.id))}/></td><td><b class="v2-collection-title">{album.album_name}</b></td><td class="v2-collection-count-column">{album.asset_count.toLocaleString()}</td><td class="v2-collection-description-column v2-muted"><span class="v2-collection-description">{album.description||'—'}</span></td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button disabled={mutating} onclick={()=>filterAssets(album.id)}>Filter assets</V2Button><V2Button disabled={mutating} onclick={()=>openEdit(album)}>Edit</V2Button><V2Button variant="danger" disabled={mutating} onclick={()=>deleteRow(album.id)}>Delete</V2Button></V2Inline></td></tr>{:else}<tr><td colspan="5" class="v2-muted">{loading?'Loading albums…':loadError?'Albums could not be loaded.':'No albums match this search.'}</td></tr>{/each}</tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={setPage}/>{:else}<V2InfiniteFooter loaded={albums.length} {total} batchSize={pageSize} noun="albums" onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
{#each modals as modal (modal.id)}<V2Modal id={`album-modal-${modal.id}`} title={modal.mode==='create'?'Create album':`Edit ${modal.name}`} description={modal.mode==='create'?'Add an album to the current data source.':'Update this album.'} size="md" onclose={()=>closeModal(modal.id)}><V2Stack gap="md"><V2Field label="Name" value={modal.name} onchange={(value)=>updateModal(modal.id,{name:value})}/><V2Field label="Description" value={modal.description} multiline={true} onchange={(value)=>updateModal(modal.id,{description:value})}/><V2Section title="Shared data"><V2Card><span class="v2-small v2-muted">Changes are reflected in Assets relationship filters and counts after the repository refreshes.</span></V2Card></V2Section></V2Stack>{#snippet footer()}<V2Button disabled={mutating} onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={mutating||!modal.name.trim()} onclick={()=>void saveModal(modal)}>{mutating?'Saving…':modal.mode==='create'?'Create album':'Save changes'}</V2Button>{/snippet}</V2Modal>{/each}
{#if deleteDialogOpen}<ConfirmDialog title={pendingDeleteIds.length===1?'Delete album?':'Delete albums?'} message={pendingDeleteIds.length===1?'This album will be deleted. Assets are not deleted.':`Delete ${pendingDeleteIds.length} selected albums? Assets are not deleted.`} confirmLabel={pendingDeleteIds.length===1?'Delete album':`Delete ${pendingDeleteIds.length} albums`} icon="trash" destructive={true} busy={mutating} loading onconfirm={()=>void confirmDelete()} onclose={()=>{if(!mutating){deleteDialogOpen=false;pendingDeleteIds=[]}}}/>{/if}

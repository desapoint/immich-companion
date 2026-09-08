<script lang="ts">
  import { onMount } from 'svelte';
  import ConfirmDialog from '../components/V2ConfirmDialog.svelte';
  import { toggleVisibleSelection, visibleSelectionState } from '../components/collectionSelection';
  import SelectField from '../components/SelectField.svelte';
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
  import V2Toggle from '../components/V2Toggle.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage, mutationFeedback, type OperationFeedback } from '../data/mutationFeedback';
  import type { TagHierarchyRow } from '../data/contracts';
  import { LatestRequestController } from '../state/latestRequest';

  type TagModal={id:number;mode:'create'|'edit';tagId:string;name:string;color:string;parent:string;parentOptions:Array<{value:string;label:string;subtitle:string}>};
  let query=$state(''),includeHierarchy=$state(false),selectedIds=$state<string[]>([]),page=$state(1),pageSize=$state(24),resultMode=$state<ResultMode>('Pagination'),sort=$state('name:asc'),rows=$state<TagHierarchyRow[]>([]),resultTotal=$state(0),nextCursor=$state<string|null>(null),loading=$state(false),mutating=$state(false),loadError=$state(''),feedback=$state<OperationFeedback|null>(null),retryDeleteIds=$state<string[]>([]),pendingDeleteIds=$state<string[]>([]),deleteDialogOpen=$state(false);
  let modalSequence=0,modals=$state<TagModal[]>([]);
  const requests=new LatestRequestController();
  const visibleIds=$derived(rows.map((tag)=>tag.id));
  const visibleSelection=$derived(visibleSelectionState(selectedIds,visibleIds));

  function parseSort(){const[fieldRaw,directionRaw]=sort.split(':');return{field:(['path','assets','children'].includes(fieldRaw)?fieldRaw:'name') as 'name'|'path'|'assets'|'children',direction:(directionRaw==='desc'?'desc':'asc') as 'asc'|'desc'}}
  async function refresh(reset=true):Promise<void>{
    if(loading&&!reset)return;
    const mode=resultMode,requestedPage=page,requestedPageSize=pageSize,requestedQuery=query,requestedHierarchy=includeHierarchy,requestedSort=parseSort(),cursor=reset?null:nextCursor;
    const request=requests.begin();
    loading=true;
    if(reset)nextCursor=null;
    try{
      const result=await libraryData.tags.search(mode==='Pagination'
        ?{page:requestedPage,pageSize:requestedPageSize,query:requestedQuery,includeHierarchy:requestedHierarchy,sort:requestedSort,signal:request.signal}
        :{pageSize:requestedPageSize,query:requestedQuery,includeHierarchy:requestedHierarchy,sort:requestedSort,cursor,signal:request.signal});
      if(!requests.isCurrent(request))return;
      rows=mode==='Infinite'&&!reset?[...rows,...result.items]:result.items;
      resultTotal=result.total;
      nextCursor=result.nextCursor;
      loadError='';
      const lastPage=Math.max(1,Math.ceil(resultTotal/requestedPageSize));
      if(mode==='Pagination'&&requestedPage>lastPage){page=lastPage;await refresh(true)}
    }catch(error){if(requests.isCurrent(request))loadError=errorMessage(error,'Tags could not be loaded.')}
    finally{if(requests.finish(request))loading=false}
  }
  function setPageSize(next:number){pageSize=next;page=1;void refresh(true)}
  function setMode(mode:ResultMode){resultMode=mode;page=1;void refresh(true)}
  function setSort(value:string){sort=value;page=1;void refresh(true)}
  function setPage(next:number){page=next;void refresh(true)}
  async function loadMore(){if(resultMode!=='Infinite'||!nextCursor||loading)return;await refresh(false)}
  function toggleSelection(id:string,checked:boolean){selectedIds=checked?[...new Set([...selectedIds,id])]:selectedIds.filter((value)=>value!==id)}
  function toggleVisible(){selectedIds=toggleVisibleSelection(selectedIds,visibleIds)}
  function realTagIdsFor(row:TagHierarchyRow){return row.realTagIds}
  function selectedRealTagIds(){const ids:string[]=[];for(const id of selectedIds){const row=rows.find((tag)=>tag.id===id);if(row)for(const realId of row.realTagIds)if(!ids.includes(realId))ids.push(realId)}return ids}
  function requestDelete(ids:string[]){if(!ids.length||mutating)return;pendingDeleteIds=[...ids];deleteDialogOpen=true}
  async function deleteIds(ids:string[]){if(!ids.length||mutating)return;mutating=true;loadError='';try{const result=await libraryData.tags.delete(ids);feedback=mutationFeedback('Delete tags',result);retryDeleteIds=result.failed.map((failure)=>failure.id);selectedIds=selectedIds.filter((id)=>{const row=rows.find((tag)=>tag.id===id);return row?.realTagIds.some((realId)=>retryDeleteIds.includes(realId))??false});await refresh(true)}catch(error){feedback=null;retryDeleteIds=[];loadError=errorMessage(error,'Tags could not be deleted.')}finally{mutating=false}}
  async function confirmDelete(){const ids=[...pendingDeleteIds];if(!ids.length||mutating)return;await deleteIds(ids);deleteDialogOpen=false;pendingDeleteIds=[]}
  function deleteSelected(){requestDelete(selectedRealTagIds())}
  async function openCreate(){if(mutating)return;try{modals=[...modals,{id:++modalSequence,mode:'create',tagId:'',name:'',color:'#9A78FF',parent:'',parentOptions:await libraryData.tags.parentOptions()}]}catch(error){loadError=errorMessage(error,'Parent tag options could not be loaded.')}}
  function openEdit(tag:TagHierarchyRow){if(tag.synthetic||mutating)return;modals=[...modals,{id:++modalSequence,mode:'edit',tagId:tag.id,name:tag.name,color:tag.color??'#9A78FF',parent:tag.parent,parentOptions:[]}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<TagModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  async function saveModal(modal:TagModal){if((modal.mode==='create'&&!modal.name.trim())||mutating)return;mutating=true;loadError='';try{if(modal.mode==='create'){const created=await libraryData.tags.create(modal.name,modal.color||null,modal.parent);if(!created)throw new Error('The tag was not created.');feedback={tone:'ok',title:'Tag created',detail:`${created.tag_name} was created.`,failures:[]}}else{const result=await libraryData.tags.update(modal.tagId,{color:modal.color||null});feedback=mutationFeedback('Update tag color',result);if(result.failed.length)return}closeModal(modal.id);await refresh(true)}catch(error){feedback=null;loadError=errorMessage(error,'The tag could not be saved.')}finally{mutating=false}}
  function deleteRow(tag:TagHierarchyRow){requestDelete(realTagIdsFor(tag))}
  function filterAssets(tag:TagHierarchyRow){if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immichCompanionV2AssetFilterHandoff',JSON.stringify({albumIds:[],tagIds:realTagIdsFor(tag)}));window.location.assign('/v2/assets')}
  onMount(()=>{let mounted=true;void(async()=>{try{await libraryData.initialize();if(mounted)await refresh(true)}catch(error){if(mounted)loadError=errorMessage(error,'The tag data source could not be initialized.')}})();return()=>{mounted=false;requests.cancel()}});
</script>

<V2PageLayout title="Tags" description="Search and manage hierarchical tags through the active data source.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={selectedIds.length===0||mutating} onclick={deleteSelected}>Delete selected{selectedIds.length?` (${selectedIds.length})`:''}</V2Button><V2Button variant="primary" disabled={mutating} onclick={()=>void openCreate()}>Create tag</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder="Search tags…" oninput={(event)=>query=event.currentTarget.value}><V2Toggle label="Match through parent hierarchy" checked={includeHierarchy} onchange={(checked)=>{includeHierarchy=checked;page=1;void refresh(true)}}/><V2Button variant="primary" disabled={loading||mutating} onclick={()=>{page=1;void refresh(true)}}>Search</V2Button><p class="v2-text-block v2-small v2-muted">{includeHierarchy?'Matches tag names and canonical parent paths.':'Matches tag names only.'}</p></V2Stack></V2Section><V2Section title="Hierarchy"><V2Card><V2Stack gap="xs"><b>{resultTotal} matching hierarchy rows</b><span class="v2-small v2-muted">Hierarchy construction, descendant IDs and aggregate counts come from the data provider.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
  <V2Zone>
    {#if loadError}<V2ErrorState title="Tag operation unavailable" message={loadError} onretry={()=>void refresh(true)}/>{/if}
    <V2OperationFeedback {feedback} retryLabel={retryDeleteIds.length?'Retry failed':''} onretry={retryDeleteIds.length?()=>requestDelete([...retryDeleteIds]):undefined}/>
    <V2Toolbar><V2Inline gap="sm" wrap={true}><V2Badge text={`${resultTotal} matches`}/><V2Badge text={includeHierarchy?'Name + hierarchy':'Name only'}/><V2Badge text={mutating?'Applying change…':loading?'Loading…':'Ready'}/></V2Inline>{#snippet actions()}<V2CollectionControls id="tag-results" {sort} sortFields={[{value:'name',label:'Tag'},{value:'path',label:'Path'},{value:'assets',label:'Assets'},{value:'children',label:'Children'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table compact={true} layout="fixed"><thead><tr><th class="v2-tag-check-column"><V2RoundCheckbox size="sm" checked={visibleSelection==='all'} indeterminate={visibleSelection==='some'} disabled={!rows.length||mutating} ariaLabel={visibleSelection==='all'?'Unselect all visible tags':'Select all visible tags'} onclick={toggleVisible}/></th><th>Tag</th><th class="v2-tag-path-column">Path</th><th class="v2-collection-count-column">Assets</th><th class="v2-tag-children-column">Children</th><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>{#each rows as tag (tag.id)}<tr><td class="v2-tag-check-column"><V2RoundCheckbox size="sm" checked={selectedIds.includes(tag.id)} disabled={mutating} ariaLabel={`${selectedIds.includes(tag.id)?'Unselect':'Select'} ${tag.name}`} onclick={()=>toggleSelection(tag.id,!selectedIds.includes(tag.id))}/></td><td><span class="v2-tag-name"><span class="v2-tag-swatch" style:background={tag.color??'#6f7d8e'}></span><b>{tag.name}</b></span><span class="v2-tag-path v2-tag-path-condensed" title={tag.path}>{tag.parent||'Root'}</span></td><td class="v2-tag-path-column"><span class="v2-tag-path" title={tag.path}>{tag.path}</span></td><td class="v2-collection-count-column">{tag.assets.toLocaleString()}</td><td class="v2-tag-children-column">{tag.children.toLocaleString()}</td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button disabled={mutating} onclick={()=>filterAssets(tag)}>Filter assets</V2Button><V2Button disabled={mutating||tag.synthetic} title={tag.synthetic?'Generated parent node':'Edit tag color'} onclick={()=>openEdit(tag)}>Edit</V2Button><V2Button variant="danger" disabled={mutating} onclick={()=>deleteRow(tag)}>Delete</V2Button></V2Inline></td></tr>{:else}<tr><td colspan="6" class="v2-tag-empty">{loading?'Loading tags…':loadError?'Tags could not be loaded.':'No tags match this search mode.'}</td></tr>{/each}</tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} total={resultTotal} onpage={setPage}/>{:else}<V2InfiniteFooter loaded={rows.length} total={resultTotal} batchSize={pageSize} noun="tags" onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
{#each modals as modal (modal.id)}<V2Modal id={`tag-modal-${modal.id}`} title={modal.mode==='create'?'Create tag':`Edit ${modal.name}`} description={modal.mode==='create'?'Create a tag with an optional parent.':'Immich only supports changing a tag’s color. Its name and parent hierarchy are read-only.'} size="md" onclose={()=>closeModal(modal.id)}><V2Stack gap="md"><V2Field label="Name" value={modal.name} disabled={modal.mode==='edit'} onchange={(value)=>updateModal(modal.id,{name:value})}/><V2Field label="Color" value={modal.color} onchange={(value)=>updateModal(modal.id,{color:value})}/>{#if modal.mode==='create'}<SelectField id={`tag-parent-modal-${modal.id}`} label="Parent" value={modal.parent} options={modal.parentOptions} allowEmpty={true} searchable={true} searchPlaceholder="Search parent tags or paths…" placeholder="No parent — root tag" onchange={(value)=>updateModal(modal.id,{parent:value})}/><V2Section title="Hierarchy preview"><V2Card><span class="v2-small">{modal.parent?`${modal.parent} / ${modal.name||'New tag'}`:modal.name||'Root tag'}</span></V2Card></V2Section>{:else}<V2Section title="Current hierarchy"><V2Card><V2Stack gap="xs"><span class="v2-small">{modal.parent?`${modal.parent} / ${modal.name}`:modal.name}</span><span class="v2-small v2-muted">Immich does not support moving an existing tag to another parent.</span></V2Stack></V2Card></V2Section>{/if}</V2Stack>{#snippet footer()}<V2Button disabled={mutating} onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={mutating||(modal.mode==='create'&&!modal.name.trim())} onclick={()=>void saveModal(modal)}>{mutating?'Saving…':modal.mode==='create'?'Create tag':'Save color'}</V2Button>{/snippet}</V2Modal>{/each}
{#if deleteDialogOpen}<ConfirmDialog title={pendingDeleteIds.length===1?'Delete tag?':'Delete tags?'} message={pendingDeleteIds.length===1?'This tag will be deleted from the current data source.':`Delete ${pendingDeleteIds.length} tags? This can affect hierarchical tag relationships.`} confirmLabel={pendingDeleteIds.length===1?'Delete tag':`Delete ${pendingDeleteIds.length} tags`} icon="trash" destructive={true} busy={mutating} loading onconfirm={()=>void confirmDelete()} onclose={()=>{if(!mutating){deleteDialogOpen=false;pendingDeleteIds=[]}}}/>{/if}

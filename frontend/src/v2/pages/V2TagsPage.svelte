<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '../../lib/components/ui/LoadingSpinner.svelte';
  import ConfirmDialog from '../components/V2ConfirmDialog.svelte';
  import { visibleSelectionState } from '../components/collectionSelection';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2ColorField from '../components/V2ColorField.svelte';
  import V2ColorSwatch from '../components/V2ColorSwatch.svelte';
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
  import V2Toggle from '../components/V2Toggle.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { errorMessage, mutationFeedback, pendingOperationFeedback } from '../data/mutationFeedback';
  import type { CollectionDeletePlan, TagHierarchyRow } from '../data/contracts';
  import { normalizeHex } from '../state/color';
  import { CollectionRequestController } from '../state/collectionRequest.svelte';
  import { OperationController } from '../state/operationController.svelte';
  import { SelectionWorkspaceController } from '../state/assetSelectionWorkspace.svelte';

  let { onfilterassets }: { onfilterassets: (tagIds: string[]) => void } = $props();

  type TagModal={id:number;mode:'create'|'edit';tagId:string;name:string;color:string|null;parent:string;parentOptions:Array<{value:string;label:string;subtitle:string}>};
  let query=$state(''),appliedQuery=$state(''),includeHierarchy=$state(false),appliedHierarchy=$state(false),page=$state(1),pageSize=$state(24),resultMode=$state<ResultMode>('Pagination'),sort=$state('name:asc'),rows=$state<TagHierarchyRow[]>([]),resultTotal=$state(0),nextCursor=$state<string|null>(null),preparingCreate=$state(false),retryDeleteIds=$state<string[]>([]),retryDeletePlan=$state<CollectionDeletePlan|null>(null),executingDelete=$state(false),deleteDialogOpen=$state(false),pendingPlan=$state<CollectionDeletePlan|null>(null),selectionScope=$state<'Current page'|'All matching'>(typeof sessionStorage!=='undefined'&&sessionStorage.getItem('immich-companion:v2:tag-selection-scope')==='All matching'?'All matching':'Current page'),searchSelectionDialog=$state(false);
  let modalSequence=0,modals=$state<TagModal[]>([]);
  const collectionRequests=new CollectionRequestController();
  const operations=new OperationController();
  const selection=new SelectionWorkspaceController(libraryData.tags,typeof sessionStorage==='undefined'?null:sessionStorage,'immich-companion:v2:tag-selection');
  const loading=$derived(collectionRequests.loading),loadError=$derived(collectionRequests.error),mutating=$derived(operations.busy||executingDelete),operationError=$derived(operations.error),feedback=$derived(operations.feedback);
  const visibleIds=$derived(rows.map((tag)=>tag.id));
  const visibleRealIds=$derived([...new Set(rows.flatMap((tag)=>tag.realTagIds))]);
  const selectedIds=$derived(rows.filter((tag)=>tag.realTagIds.length>0&&tag.realTagIds.every((id)=>selection.visibleSelectedIds.has(id))).map((tag)=>tag.id));
  const partiallySelectedIds=$derived(rows.filter((tag)=>tag.realTagIds.some((id)=>selection.visibleSelectedIds.has(id))&&!tag.realTagIds.every((id)=>selection.visibleSelectedIds.has(id))).map((tag)=>tag.id));
  $effect(()=>{if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immich-companion:v2:tag-selection-scope',selectionScope)});
  const visibleSelection=$derived(visibleSelectionState([...selection.visibleSelectedIds],visibleRealIds));
  const colorsInView=$derived.by(()=>{const counts=new Map<string,number>();for(const tag of rows){if(tag.synthetic||!tag.color)continue;const color=normalizeHex(tag.color);if(color)counts.set(color,(counts.get(color)??0)+1)}return[...counts].map(([color,count])=>({color,count})).sort((a,b)=>b.count-a.count)});

  function parseSort(){const[fieldRaw,directionRaw]=sort.split(':');return{field:(['path','assets','children'].includes(fieldRaw)?fieldRaw:'name') as 'name'|'path'|'assets'|'children',direction:(directionRaw==='desc'?'desc':'asc') as 'asc'|'desc'}}
  async function refresh(reset=true):Promise<boolean>{
    if(loading&&!reset)return false;
    const mode=resultMode,requestedPage=page,requestedPageSize=pageSize,requestedQuery=appliedQuery,requestedHierarchy=appliedHierarchy,requestedSort=parseSort(),cursor=reset?null:nextCursor;
    if(reset)nextCursor=null;
    const result=await collectionRequests.run((signal)=>libraryData.tags.search(mode==='Pagination'
      ?{page:requestedPage,pageSize:requestedPageSize,query:requestedQuery,includeHierarchy:requestedHierarchy,sort:requestedSort,signal}
      :{pageSize:requestedPageSize,query:requestedQuery,includeHierarchy:requestedHierarchy,sort:requestedSort,cursor,signal}),{
        fallbackError:'Tags could not be loaded.',
        mode:mode==='Infinite'&&!reset?'append':'replace',
        apply:(response,loadMode)=>{
          rows=loadMode==='append'?[...rows,...response.items]:response.items;
          resultTotal=response.total;
          nextCursor=response.nextCursor;
        },
      });
    if(!result)return false;
    await selection.refreshVisible(visibleRealIds);
    await selection.refreshMatching({query:requestedQuery,includeHierarchy:requestedHierarchy});
    const lastPage=Math.max(1,Math.ceil(resultTotal/requestedPageSize));
    if(mode==='Pagination'&&requestedPage>lastPage){page=lastPage;return refresh(true)}
    return true;
  }
  async function reconcile(action:string):Promise<void>{if(!await refresh(true))throw new Error(collectionRequests.error||`${action} was applied, but tags could not be refreshed.`)}
  function pending(action:string){return(phase:'applying'|'reconciling')=>pendingOperationFeedback(action,phase==='applying'?'applying':'refreshing')}
  function setPageSize(next:number){pageSize=next;page=1;void refresh(true)}
  function setMode(mode:ResultMode){resultMode=mode;page=1;void refresh(true)}
  function setSort(value:string){sort=value;page=1;void refresh(true)}
  function setPage(next:number){page=next;void refresh(true)}
  function applySearch(dismiss:boolean){if(dismiss)selection.clear();appliedQuery=query;appliedHierarchy=includeHierarchy;page=1;searchSelectionDialog=false;void refresh(true)}
  function submitSearch(){if(loading||mutating)return;if(selection.active&&(query!==appliedQuery||includeHierarchy!==appliedHierarchy)){searchSelectionDialog=true;return}applySearch(false)}
  function handleSearchKeydown(event:KeyboardEvent){if(event.key!=='Enter'||event.isComposing)return;event.preventDefault();submitSearch()}
  async function loadMore(){if(resultMode!=='Infinite'||!nextCursor||loading)return;await refresh(false)}
  function toggleSelection(id:string,checked:boolean){const row=rows.find((tag)=>tag.id===id);if(row)selection.setMembers(row.realTagIds,checked,row.realTagIds[0]??null)}
  function toggleVisible(){if(selectionScope==='All matching'){void selection.setMatching({query:appliedQuery,includeHierarchy:appliedHierarchy},visibleRealIds,!selection.allMatchingSelected).catch((error)=>operations.setError(error,'Matching tags could not be selected.'));return}selection.setMembers(visibleRealIds,visibleSelection!=='all',visibleRealIds[0]??null)}
  function realTagIdsFor(row:TagHierarchyRow){return row.realTagIds}
  async function requestDelete(ids:string[]=[]){if(mutating)return;try{let selectionId:string;if(ids.length){let temporary=await libraryData.tags.createSelection();for(let offset=0;offset<ids.length;offset+=2000)temporary=await libraryData.tags.updateSelectionMembers(temporary.id,ids.slice(offset,offset+2000),true,temporary.revision);selectionId=temporary.id}else{await selection.flush();if(!selection.selectionId)return;selectionId=selection.selectionId}pendingPlan=await libraryData.tags.planDelete(selectionId);retryDeletePlan=null;deleteDialogOpen=true}catch(error){operations.setError(error,'Tags could not be prepared for deletion.')}}
  async function deleteIds(ids:string[]){
    if(!ids.length||mutating)return;
    operations.clearOutcome();
    const result=await operations.run('Delete tags',()=>libraryData.tags.delete(ids),{
      pending:pending('Delete tags'),
      outcome:(value)=>mutationFeedback('Delete tags',value),
      reconcile:()=>reconcile('Delete tags'),
      reconcileError:'Tags were deleted, but the latest tag list could not be loaded.',
    });
    if(!result)return;
    retryDeleteIds=result.failed.map((failure)=>failure.id);
    await selection.refreshVisible(visibleRealIds);
  }
  async function confirmDelete(){const plan=pendingPlan;if(!plan||mutating)return;executingDelete=true;try{const result=await libraryData.tags.executeDelete(plan.id);retryDeleteIds=result.results.filter((item)=>item.status==='failed').map((item)=>item.id);const removed=result.results.filter((item)=>item.status!=='failed').map((item)=>item.id);if(removed.length)selection.setMembers(removed,false);retryDeletePlan=result.status==='failed'?result:null;deleteDialogOpen=false;pendingPlan=null;await refresh(true);if(retryDeletePlan)operations.setError(new Error(`${retryDeleteIds.length} tag deletion${retryDeleteIds.length===1?'':'s'} failed. The saved plan can be retried.`))}catch(error){operations.setError(error,'Tags could not be deleted.')}finally{executingDelete=false}}
  function deleteSelected(){void requestDelete()}
  async function openCreate(){if(mutating||preparingCreate)return;preparingCreate=true;operations.clearError();try{const parentOptions=await libraryData.tags.parentOptions();modals=[...modals,{id:++modalSequence,mode:'create',tagId:'',name:'',color:'#9A78FF',parent:'',parentOptions}]}catch(error){operations.setError(error,'Parent tag options could not be loaded.')}finally{preparingCreate=false}}
  function openEdit(tag:TagHierarchyRow){if(tag.synthetic||mutating)return;modals=[...modals,{id:++modalSequence,mode:'edit',tagId:tag.id,name:tag.name,color:tag.color,parent:tag.parent,parentOptions:[]}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<TagModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  async function saveModal(modal:TagModal){
    if((modal.mode==='create'&&!modal.name.trim())||mutating)return;
    operations.clearOutcome();
    if(modal.mode==='create'){
      const created=await operations.run('Create tag',async()=>{const value=await libraryData.tags.create(modal.name,modal.color,modal.parent);if(!value)throw new Error('The tag was not created.');return value},{
        pending:pending('Create tag'),
        outcome:(value)=>({tone:'ok',title:'Tag created',detail:`${value.tag_name} was created.`,failures:[]}),
        reconcile:()=>reconcile('Create tag'),
        reconcileError:'The tag was created, but the latest tag list could not be loaded.',
      });
      if(created)closeModal(modal.id);
      return;
    }
    const result=await operations.run('Update tag color',()=>libraryData.tags.update(modal.tagId,{color:modal.color}),{
      pending:pending('Update tag color'),
      outcome:(value)=>mutationFeedback('Update tag color',value),
      reconcile:()=>reconcile('Update tag color'),
      reconcileError:'The tag was updated, but the latest tag list could not be loaded.',
    });
    if(result&&!result.failed.length)closeModal(modal.id);
  }
  function deleteRow(tag:TagHierarchyRow){void requestDelete(realTagIdsFor(tag))}
  function filterAssets(tag:TagHierarchyRow){onfilterassets(realTagIdsFor(tag))}
  onMount(()=>{let mounted=true;void(async()=>{try{await libraryData.initialize();if(mounted)await refresh(true)}catch(error){if(mounted)collectionRequests.setError(errorMessage(error,'The tag data source could not be initialized.'))}})();return()=>{mounted=false;collectionRequests.cancel()}});
</script>

<V2PageLayout title="Tags" description="Search and manage hierarchical tags through the active data source.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={!selection.active||mutating} onclick={deleteSelected}>Delete selected{selection.selectedCount?` (${selection.selectedCount})`:''}</V2Button><V2Button variant="primary" disabled={mutating||preparingCreate} onclick={()=>void openCreate()}>{#if preparingCreate}<span class="v2-tag-create-pending"><LoadingSpinner size="0.9rem" thickness="0.11rem"/><span>Preparing…</span></span>{:else}Create tag{/if}</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder="Search tags…" oninput={(event)=>query=event.currentTarget.value} onkeydown={handleSearchKeydown}><V2Toggle label="Match through parent hierarchy" checked={includeHierarchy} onchange={(checked)=>includeHierarchy=checked}/><V2Button variant="primary" disabled={loading||mutating} onclick={submitSearch}>Search</V2Button><p class="v2-text-block v2-small v2-muted">{includeHierarchy?'Matches tag names and canonical parent paths.':'Matches tag names only.'}</p></V2Stack></V2Section><V2Section title="Hierarchy"><V2Card><V2Stack gap="xs"><b>{resultTotal} matching hierarchy rows</b><span class="v2-small v2-muted">Hierarchy construction, descendant IDs and aggregate counts come from the data provider.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
  <V2Zone>
    {#if loadError}<V2ErrorState title="Tags could not be loaded" message={loadError} onretry={()=>void refresh(true)}/>{/if}
    <V2OperationToast {feedback} error={operationError} failureTitle="Tag operation failed" retryLabel={retryDeletePlan?'Retry saved plan':retryDeleteIds.length?'Retry failed':''} onretry={retryDeletePlan?()=>{pendingPlan=retryDeletePlan;deleteDialogOpen=true}:retryDeleteIds.length?()=>requestDelete([...retryDeleteIds]):undefined}/>
    <V2Toolbar><V2Inline gap="sm" wrap={true}><V2Badge text={`${resultTotal} matches`}/><V2Badge text={`${selection.selectedCount} selected`}/><V2Badge text={appliedHierarchy?'Name + hierarchy':'Name only'}/><V2Badge text={preparingCreate?'Preparing tag…':mutating?(operations.phase==='reconciling'?'Refreshing…':'Applying change…'):loading?'Loading…':'Ready'}/></V2Inline>{#snippet actions()}<V2Segmented items={['Current page','All matching']} active={selectionScope} onselect={(value)=>selectionScope=value as typeof selectionScope} ariaLabel="Tag selection scope"/><V2CollectionControls id="tag-results" {sort} sortFields={[{value:'name',label:'Tag'},{value:'path',label:'Path'},{value:'assets',label:'Assets'},{value:'children',label:'Children'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table compact={true} layout="fixed"><thead><tr><th class="v2-tag-check-column"><V2RoundCheckbox size="sm" checked={selectionScope==='All matching'?selection.allMatchingSelected:visibleSelection==='all'} indeterminate={selectionScope==='All matching'?selection.matchingSelectedCount>0&&!selection.allMatchingSelected:visibleSelection==='some'} disabled={!rows.length||mutating} ariaLabel={selectionScope==='All matching'?(selection.allMatchingSelected?'Unselect all matching tags':'Select all matching tags'):(visibleSelection==='all'?'Unselect all visible tags':'Select all visible tags')} onclick={toggleVisible}/></th><V2SortableHeader field="name" label="Tag" {sort} onsort={setSort}/><V2SortableHeader field="path" label="Path" {sort} class="v2-tag-path-column" onsort={setSort}/><V2SortableHeader field="assets" label="Assets" {sort} class="v2-collection-count-column" onsort={setSort}/><V2SortableHeader field="children" label="Children" {sort} class="v2-tag-children-column" onsort={setSort}/><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>{#each rows as tag (tag.id)}<tr><td class="v2-tag-check-column"><V2RoundCheckbox size="sm" checked={selectedIds.includes(tag.id)} indeterminate={partiallySelectedIds.includes(tag.id)} disabled={mutating} ariaLabel={`${selectedIds.includes(tag.id)?'Unselect':'Select'} ${tag.name}`} onclick={()=>toggleSelection(tag.id,!selectedIds.includes(tag.id))}/></td><td><span class="v2-tag-name"><V2ColorSwatch color={tag.color} size="sm"/><b>{tag.name}</b></span><span class="v2-tag-path v2-tag-path-condensed" title={tag.path}>{tag.parent||'Root'}</span></td><td class="v2-tag-path-column"><span class="v2-tag-path" title={tag.path}>{tag.path}</span></td><td class="v2-collection-count-column">{tag.assets.toLocaleString()}</td><td class="v2-tag-children-column">{tag.children.toLocaleString()}</td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button disabled={mutating} onclick={()=>filterAssets(tag)}>Filter assets</V2Button><V2Button disabled={mutating||tag.synthetic} title={tag.synthetic?'Generated parent node':'Edit tag color'} onclick={()=>openEdit(tag)}>Edit</V2Button><V2Button variant="danger" disabled={mutating} onclick={()=>deleteRow(tag)}>Delete</V2Button></V2Inline></td></tr>{:else}<tr><td colspan="6" class="v2-tag-empty">{loading?'Loading tags…':loadError?'Tags could not be loaded.':'No tags match this search mode.'}</td></tr>{/each}</tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} total={resultTotal} onpage={setPage}/>{:else}<V2InfiniteFooter loaded={rows.length} total={resultTotal} batchSize={pageSize} noun="tags" onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
{#each modals as modal (modal.id)}<V2Modal id={`tag-modal-${modal.id}`} title={modal.mode==='create'?'Create tag':`Edit ${modal.name}`} description={modal.mode==='create'?'Create a tag with an optional parent.':'Immich only supports changing a tag’s color. Its name and parent hierarchy are read-only.'} size="md" onclose={()=>{if(!mutating)closeModal(modal.id)}}><V2Stack gap="md"><V2Field label="Name" value={modal.name} disabled={modal.mode==='edit'} onvalueinput={(value)=>updateModal(modal.id,{name:value})}/><V2ColorField id={`tag-color-${modal.id}`} label="Color" value={modal.color} usedColors={colorsInView} usedColorsLabel="Colors in view" onchange={(color)=>updateModal(modal.id,{color})}/>{#if modal.mode==='create'}<SelectField id={`tag-parent-modal-${modal.id}`} label="Parent" value={modal.parent} options={modal.parentOptions} allowEmpty={true} searchable={true} searchPlaceholder="Search parent tags or paths…" placeholder="No parent — root tag" onchange={(value)=>updateModal(modal.id,{parent:value})}/><V2Section title="Hierarchy preview"><V2Card><span class="v2-tag-preview"><V2ColorSwatch color={modal.color} size="sm"/><span class="v2-small">{modal.parent?`${modal.parent} / ${modal.name||'New tag'}`:modal.name||'Root tag'}</span></span></V2Card></V2Section>{:else}<V2Section title="Current hierarchy"><V2Card><V2Stack gap="xs"><span class="v2-tag-preview"><V2ColorSwatch color={modal.color} size="sm"/><span class="v2-small">{modal.parent?`${modal.parent} / ${modal.name}`:modal.name}</span></span><span class="v2-small v2-muted">Immich does not support moving an existing tag to another parent.</span></V2Stack></V2Card></V2Section>{/if}</V2Stack>{#snippet footer()}<V2Button disabled={mutating} onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={mutating||(modal.mode==='create'&&!modal.name.trim())} onclick={()=>void saveModal(modal)}>{mutating?(operations.phase==='reconciling'?'Refreshing…':'Saving…'):modal.mode==='create'?'Create tag':'Save color'}</V2Button>{/snippet}</V2Modal>{/each}

<style>.v2-tag-preview{display:inline-flex;align-items:center;gap:8px;min-width:0}.v2-tag-create-pending{display:inline-flex;align-items:center;gap:8px}</style>
{#if deleteDialogOpen&&pendingPlan}<ConfirmDialog title={pendingPlan.status==='failed'?'Retry tag deletion?':pendingPlan.targetCount===1?'Delete tag?':'Delete tags?'} message={pendingPlan.status==='failed'?`Retry ${pendingPlan.results.filter((item)=>item.status==='failed').length} failed items from the frozen ${pendingPlan.targetCount}-tag plan. Completed items will not be repeated.`:pendingPlan.targetCount===1?'This tag will be deleted from the current data source.':`Delete ${pendingPlan.targetCount} tags? This can affect hierarchical tag relationships.`} confirmLabel={pendingPlan.status==='failed'?'Retry failed tags':pendingPlan.targetCount===1?'Delete tag':`Delete ${pendingPlan.targetCount} tags`} icon="trash" destructive={true} pending={mutating} onconfirm={()=>void confirmDelete()} onclose={()=>{if(!mutating){deleteDialogOpen=false;pendingPlan=null}}}/>{/if}
{#if searchSelectionDialog}<ConfirmDialog title="Selection and search" message="Keep the current tag selection while applying this search, or dismiss it first." confirmLabel="Dismiss selection" cancelLabel="Keep selection" destructive={true} onconfirm={()=>applySearch(true)} onclose={()=>applySearch(false)}/>{/if}

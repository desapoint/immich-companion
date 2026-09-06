<script lang="ts">
  import { onMount } from 'svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2CollectionControls, { type ResultMode } from '../components/V2CollectionControls.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2InfiniteFooter from '../components/V2InfiniteFooter.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Modal from '../components/V2Modal.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Pagination from '../components/V2Pagination.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Table from '../components/V2Table.svelte';
  import V2Toggle from '../components/V2Toggle.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { TagHierarchyRow } from '../data/contracts';

  type TagModal={id:number;mode:'create'|'edit';tagId:string;name:string;color:string;parent:string;parentOptions:Array<{value:string;label:string;subtitle:string}>};
  let query=$state(''),includeHierarchy=$state(false),selectedIds=$state<string[]>([]),page=$state(1),pageSize=$state(24),resultMode=$state<ResultMode>('Pagination'),loaded=$state(24),sort=$state('name:asc'),rows=$state<TagHierarchyRow[]>([]),resultTotal=$state(0),loading=$state(false);
  let modalSequence=0,modals=$state<TagModal[]>([]);

  function parseSort(){const[fieldRaw,directionRaw]=sort.split(':');return{field:(['path','assets','children'].includes(fieldRaw)?fieldRaw:'name') as 'name'|'path'|'assets'|'children',direction:(directionRaw==='desc'?'desc':'asc') as 'asc'|'desc'}}
  async function refresh(){loading=true;try{const result=await libraryData.tags.search({page:resultMode==='Pagination'?page:1,pageSize:resultMode==='Pagination'?pageSize:loaded,query,includeHierarchy,sort:parseSort()});rows=result.items;resultTotal=result.total;if(page>Math.max(1,Math.ceil(resultTotal/pageSize))){page=Math.max(1,Math.ceil(resultTotal/pageSize));await refresh()}}finally{loading=false}}
  function setPageSize(next:number){pageSize=next;page=1;loaded=Math.max(next,loaded);void refresh()}
  function setMode(mode:ResultMode){resultMode=mode;if(mode==='Pagination')page=1;else loaded=Math.max(pageSize,loaded);void refresh()}
  function setSort(value:string){sort=value;page=1;void refresh()}
  function setPage(next:number){page=next;void refresh()}
  function loadMore(){loaded=Math.min(resultTotal,loaded+pageSize);void refresh()}
  function toggleSelection(id:string,checked:boolean){selectedIds=checked?[...new Set([...selectedIds,id])]:selectedIds.filter((value)=>value!==id)}
  function realTagIdsFor(row:TagHierarchyRow){return row.realTagIds}
  function selectedRealTagIds(){const ids=new Set<string>();for(const id of selectedIds){const row=rows.find((tag)=>tag.id===id);if(row)for(const realId of row.realTagIds)ids.add(realId)}return[...ids]}
  async function deleteSelected(){const ids=selectedRealTagIds();if(ids.length)await libraryData.tags.delete(ids);selectedIds=[];await refresh()}
  async function openCreate(){modals=[...modals,{id:++modalSequence,mode:'create',tagId:'',name:'',color:'#9A78FF',parent:'',parentOptions:await libraryData.tags.parentOptions()}]}
  async function openEdit(tag:TagHierarchyRow){if(tag.synthetic)return;modals=[...modals,{id:++modalSequence,mode:'edit',tagId:tag.id,name:tag.name,color:tag.color??'#9A78FF',parent:tag.parent,parentOptions:await libraryData.tags.parentOptions(tag.id)}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<TagModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  async function saveModal(modal:TagModal){if(!modal.name.trim())return;if(modal.mode==='create')await libraryData.tags.create(modal.name,modal.color||null,modal.parent);else await libraryData.tags.update(modal.tagId,{name:modal.name,color:modal.color||null,parentPath:modal.parent});closeModal(modal.id);await refresh()}
  async function deleteRow(tag:TagHierarchyRow){await libraryData.tags.delete(realTagIdsFor(tag));selectedIds=selectedIds.filter((id)=>id!==tag.id);await refresh()}
  function filterAssets(tag:TagHierarchyRow){if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immichCompanionV2AssetFilterHandoff',JSON.stringify({albumIds:[],tagIds:realTagIdsFor(tag)}));window.location.hash='assets'}
  onMount(()=>{void(async()=>{await libraryData.initialize();await refresh()})()});
</script>

<V2PageLayout title="Tags" description="Search and manage hierarchical tags through the active data source.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={selectedIds.length===0} onclick={deleteSelected}>Delete selected{selectedIds.length?` (${selectedIds.length})`:''}</V2Button><V2Button variant="primary" onclick={()=>void openCreate()}>Create tag</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder={`Search tags…`} oninput={(event)=>query=event.currentTarget.value}><V2Toggle label="Match through parent hierarchy" checked={includeHierarchy} onchange={(checked)=>{includeHierarchy=checked;page=1;void refresh()}}/><V2Button variant="primary" disabled={loading} onclick={()=>{page=1;loaded=pageSize;void refresh()}}>Search</V2Button><p class="v2-text-block v2-small v2-muted">{includeHierarchy?'Matches tag names and canonical parent paths.':'Matches tag names only.'}</p></V2Stack></V2Section><V2Section title="Hierarchy"><V2Card><V2Stack gap="xs"><b>{resultTotal} matching hierarchy rows</b><span class="v2-small v2-muted">Hierarchy construction, descendant IDs and aggregate counts come from the data provider.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
  <V2Zone><V2Toolbar><V2Inline gap="sm" wrap={true}><V2Badge text={`${resultTotal} matches`}/><V2Badge text={includeHierarchy?'Name + hierarchy':'Name only'}/></V2Inline>{#snippet actions()}<V2CollectionControls id="tag-results" {sort} sortFields={[{value:'name',label:'Tag'},{value:'path',label:'Path'},{value:'assets',label:'Assets'},{value:'children',label:'Children'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={setSort} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table compact={true} layout="fixed"><thead><tr><th class="v2-tag-check-column"><span class="v2-visually-hidden">Select</span></th><th>Tag</th><th class="v2-tag-path-column">Path</th><th class="v2-collection-count-column">Assets</th><th class="v2-tag-children-column">Children</th><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>{#each rows as tag (tag.id)}<tr><td class="v2-tag-check-column"><input type="checkbox" aria-label={`Select ${tag.name}`} checked={selectedIds.includes(tag.id)} onchange={(event)=>toggleSelection(tag.id,event.currentTarget.checked)}></td><td><span class="v2-tag-name"><span class="v2-tag-swatch" style:background={tag.color??'#6f7d8e'}></span><b>{tag.name}</b></span><span class="v2-tag-path v2-tag-path-condensed" title={tag.path}>{tag.parent||'Root'}</span></td><td class="v2-tag-path-column"><span class="v2-tag-path" title={tag.path}>{tag.path}</span></td><td class="v2-collection-count-column">{tag.assets.toLocaleString()}</td><td class="v2-tag-children-column">{tag.children.toLocaleString()}</td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button onclick={()=>filterAssets(tag)}>Filter assets</V2Button><V2Button disabled={tag.synthetic} title={tag.synthetic?'Generated parent node':'Edit tag'} onclick={()=>void openEdit(tag)}>Edit</V2Button><V2Button variant="danger" onclick={()=>void deleteRow(tag)}>Delete</V2Button></V2Inline></td></tr>{:else}<tr><td colspan="6" class="v2-tag-empty">{loading?'Loading tags…':'No tags match this search mode.'}</td></tr>{/each}</tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} total={resultTotal} onpage={setPage}/>{:else}<V2InfiniteFooter loaded={rows.length} total={resultTotal} batchSize={pageSize} noun="tags" onloadmore={loadMore}/>{/if}
  </V2Zone>
</V2PageLayout>
{#each modals as modal (modal.id)}<V2Modal id={`tag-modal-${modal.id}`} title={modal.mode==='create'?'Create tag':`Edit ${modal.name}`} description={modal.mode==='create'?'Create a tag with an optional parent.':'Update this tag and move its descendant branch when its path changes.'} size="md" onclose={()=>closeModal(modal.id)}><V2Stack gap="md"><V2Field label="Name" value={modal.name} onchange={(value)=>updateModal(modal.id,{name:value})}/><V2Field label="Color" value={modal.color} onchange={(value)=>updateModal(modal.id,{color:value})}/><SelectField id={`tag-parent-modal-${modal.id}`} label="Parent" value={modal.parent} options={modal.parentOptions} allowEmpty={true} searchable={true} searchPlaceholder="Search parent tags or paths…" placeholder="No parent — root tag" onchange={(value)=>updateModal(modal.id,{parent:value})}/><V2Section title="Hierarchy preview"><V2Card><span class="v2-small">{modal.parent?`${modal.parent} / ${modal.name||'New tag'}`:modal.name||'Root tag'}</span></V2Card></V2Section></V2Stack>{#snippet footer()}<V2Button onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={!modal.name.trim()} onclick={()=>void saveModal(modal)}>{modal.mode==='create'?'Create tag':'Save changes'}</V2Button>{/snippet}</V2Modal>{/each}

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
  import { createDemoTag, deleteDemoTags, demoAssetState, initializeDemoAssetState, updateDemoTag } from '../demo/demoAssetState.svelte';

  type Tag = { id:string; name:string; path:string; parent:string; assets:number; children:number; color:string | null; synthetic?:boolean };
  type TagModal = { id:number; mode:'create'|'edit'; tagId:string; name:string; color:string; parent:string };

  const tags=$derived.by(()=>{
    const leaves:Tag[]=demoAssetState.tags.map((tag)=>{
      const parts=tag.tag_name.split(' / ');
      return {id:tag.id,name:parts.at(-1)??tag.tag_name,path:tag.tag_name,parent:parts.length>1?parts.slice(0,-1).join(' / '):'',assets:tag.asset_count,children:0,color:tag.color};
    });
    const byPath=new Map(leaves.map((tag)=>[tag.path,tag]));
    for(const leaf of leaves){const parts=leaf.path.split(' / ');for(let depth=1;depth<parts.length;depth+=1){const path=parts.slice(0,depth).join(' / ');if(byPath.has(path))continue;byPath.set(path,{id:`hierarchy:${path}`,name:parts[depth-1],path,parent:depth>1?parts.slice(0,depth-1).join(' / '):'',assets:0,children:0,color:leaf.color,synthetic:true})}}
    const rows=[...byPath.values()];
    for(const row of rows){row.children=rows.filter((candidate)=>candidate.parent===row.path).length;if(row.synthetic){const assetIds=new Set(demoAssetState.tag_assets.filter((membership)=>{const tag=demoAssetState.tags.find((candidate)=>candidate.id===membership.tag_id);return tag?.tag_name.startsWith(`${row.path} / `)}).map((membership)=>membership.asset_id));row.assets=assetIds.size}}
    return rows;
  });

  let query=$state(''),includeHierarchy=$state(false),selectedIds=$state<string[]>([]),page=$state(1),pageSize=$state(24),resultMode=$state<ResultMode>('Pagination'),loaded=$state(24),sort=$state('name:asc');
  let modalSequence=0,modals=$state<TagModal[]>([]);
  const normalizedQuery=$derived(query.trim().toLocaleLowerCase());
  const filteredTags=$derived(tags.filter((tag)=>{if(!normalizedQuery)return true;const direct=tag.name.toLocaleLowerCase().includes(normalizedQuery);return includeHierarchy?direct||tag.path.toLocaleLowerCase().includes(normalizedQuery):direct}));
  const sortedTags=$derived([...filteredTags].sort((a,b)=>{const [field,direction]=sort.split(':'),multiplier=direction==='desc'?-1:1;if(field==='assets')return(a.assets-b.assets)*multiplier;if(field==='children')return(a.children-b.children)*multiplier;if(field==='path')return a.path.localeCompare(b.path)*multiplier;return a.name.localeCompare(b.name)*multiplier}));
  const resultTotal=$derived(sortedTags.length);
  const visibleTags=$derived(resultMode==='Pagination'?sortedTags.slice((page-1)*pageSize,(page-1)*pageSize+pageSize):sortedTags.slice(0,Math.min(loaded,resultTotal)));

  function setPageSize(next:number){pageSize=next;page=1;loaded=Math.max(next,Math.min(loaded,resultTotal))}
  function setMode(mode:ResultMode){resultMode=mode;if(mode==='Pagination')page=1;else loaded=Math.max(pageSize,loaded)}
  function toggleSelection(id:string,checked:boolean){selectedIds=checked?[...new Set([...selectedIds,id])]:selectedIds.filter((value)=>value!==id)}
  function realTagIdsFor(row:Tag):string[]{if(!row.synthetic)return[row.id];return demoAssetState.tags.filter((tag)=>tag.tag_name.startsWith(`${row.path} / `)).map((tag)=>tag.id)}
  function selectedRealTagIds():string[]{const ids=new Set<string>();for(const id of selectedIds){const row=tags.find((tag)=>tag.id===id);if(row)for(const realId of realTagIdsFor(row))ids.add(realId)}return[...ids]}
  function deleteSelected(){const ids=selectedRealTagIds();if(ids.length)deleteDemoTags(ids);selectedIds=[];page=Math.min(page,Math.max(1,Math.ceil(resultTotal/pageSize)))}
  function openCreate(){modals=[...modals,{id:++modalSequence,mode:'create',tagId:'',name:'',color:'#9A78FF',parent:''}]}
  function openEdit(tag:Tag){if(tag.synthetic)return;modals=[...modals,{id:++modalSequence,mode:'edit',tagId:tag.id,name:tag.name,color:tag.color??'#9A78FF',parent:tag.parent}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<TagModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  function parentOptionsFor(modal:TagModal){const editing=demoAssetState.tags.find((tag)=>tag.id===modal.tagId)?.tag_name??'';return tags.filter((tag)=>tag.children>0&&tag.path!==editing&&!tag.path.startsWith(`${editing} / `)).map((tag)=>({value:tag.path,label:tag.name,subtitle:tag.parent||'Root'}))}
  function saveModal(modal:TagModal){if(!modal.name.trim())return;if(modal.mode==='create')createDemoTag(modal.name,modal.color||null,modal.parent);else updateDemoTag(modal.tagId,{name:modal.name,color:modal.color||null,parentPath:modal.parent});closeModal(modal.id)}
  function deleteRow(tag:Tag){deleteDemoTags(realTagIdsFor(tag));selectedIds=selectedIds.filter((id)=>id!==tag.id)}
  function filterAssets(tag:Tag){const tagIds=realTagIdsFor(tag);if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immichCompanionV2AssetFilterHandoff',JSON.stringify({albumIds:[],tagIds}));window.location.hash='assets'}

  onMount(()=>initializeDemoAssetState());
</script>

<V2PageLayout title="Tags" description="Search and manage hierarchical tags from the same shared V2 demo state used by Assets filters and asset relationships.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={selectedIds.length===0} onclick={deleteSelected}>Delete selected{selectedIds.length?` (${selectedIds.length})`:''}</V2Button><V2Button variant="primary" onclick={openCreate}>Create tag</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder={`Search ${tags.length} tags…`} oninput={(event)=>{query=event.currentTarget.value;page=1;loaded=pageSize}}><V2Toggle label="Match through parent hierarchy" checked={includeHierarchy} onchange={(checked)=>{includeHierarchy=checked;page=1;loaded=pageSize}}/><p class="v2-text-block v2-small v2-muted">{includeHierarchy?'Matches tag names and canonical parent paths. Searching “Family” also finds descendants several levels below it.':'Matches tag names only.'}</p></V2Stack></V2Section><V2Section title="Hierarchy"><V2Card><V2Stack gap="xs"><b>{tags.length} visible hierarchy rows</b><span class="v2-small v2-muted">Backed by {demoAssetState.tags.length} shared tag records plus generated display-only parent nodes.</span><span class="v2-small v2-muted">Parent asset counts use unique descendant assets, so assets with multiple child tags are not double-counted.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar><V2Inline gap="sm" wrap={true}><V2Badge text={`${filteredTags.length} matches`}/><V2Badge text={includeHierarchy?'Name + hierarchy':'Name only'}/><V2Badge text={`${demoAssetState.tags.length} shared tags`}/></V2Inline>{#snippet actions()}<V2CollectionControls id="tag-results" {sort} sortFields={[{value:'name',label:'Tag'},{value:'path',label:'Path'},{value:'assets',label:'Assets'},{value:'children',label:'Children'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={(value)=>sort=value} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table compact={true} layout="fixed"><thead><tr><th class="v2-tag-check-column"><span class="v2-visually-hidden">Select</span></th><th>Tag</th><th class="v2-tag-path-column">Path</th><th class="v2-collection-count-column">Assets</th><th class="v2-tag-children-column">Children</th><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>
      {#each visibleTags as tag (tag.id)}<tr><td class="v2-tag-check-column"><input type="checkbox" aria-label={`Select ${tag.name}`} checked={selectedIds.includes(tag.id)} onchange={(event)=>toggleSelection(tag.id,event.currentTarget.checked)}></td><td><span class="v2-tag-name"><span class="v2-tag-swatch" style:background={tag.color??'#6f7d8e'}></span><b>{tag.name}</b></span><span class="v2-tag-path v2-tag-path-condensed" title={tag.path}>{tag.parent||'Root'}</span></td><td class="v2-tag-path-column"><span class="v2-tag-path" title={tag.path}>{tag.path}</span></td><td class="v2-collection-count-column">{tag.assets.toLocaleString()}</td><td class="v2-tag-children-column">{tag.children.toLocaleString()}</td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button onclick={()=>filterAssets(tag)}>Filter assets</V2Button><V2Button disabled={tag.synthetic} title={tag.synthetic?'Generated parent node':'Edit tag'} onclick={()=>openEdit(tag)}>Edit</V2Button><V2Button variant="danger" onclick={()=>deleteRow(tag)}>Delete</V2Button></V2Inline></td></tr>
      {:else}<tr><td colspan="6" class="v2-tag-empty">No tags match this search mode.</td></tr>{/each}
    </tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} total={resultTotal} onpage={(next)=>(page=next)}/>{:else}<V2InfiniteFooter loaded={Math.min(loaded,resultTotal)} total={resultTotal} batchSize={pageSize} noun="tags" onloadmore={()=>loaded=Math.min(resultTotal,loaded+pageSize)}/>{/if}
  </V2Zone>
</V2PageLayout>

{#each modals as modal (modal.id)}
  <V2Modal id={`tag-modal-${modal.id}`} title={modal.mode==='create'?'Create tag':`Edit ${modal.name}`} description={modal.mode==='create'?'Create a shared demo tag with an optional parent.':'Update this shared tag and move its descendant branch when its path changes.'} size="md" onclose={()=>closeModal(modal.id)}>
    <V2Stack gap="md"><V2Field label="Name" value={modal.name} onchange={(value)=>updateModal(modal.id,{name:value})}/><V2Field label="Color" value={modal.color} onchange={(value)=>updateModal(modal.id,{color:value})}/><SelectField id={`tag-parent-modal-${modal.id}`} label="Parent" value={modal.parent} options={parentOptionsFor(modal)} allowEmpty={true} searchable={true} searchPlaceholder="Search parent tags or paths…" placeholder="No parent — root tag" onchange={(value)=>updateModal(modal.id,{parent:value})}/><V2Section title="Hierarchy preview"><V2Card><span class="v2-small">{modal.parent?`${modal.parent} / ${modal.name||'New tag'}`:modal.name||'Root tag'}</span></V2Card></V2Section></V2Stack>
    {#snippet footer()}<V2Button onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={!modal.name.trim()} onclick={()=>saveModal(modal)}>{modal.mode==='create'?'Create tag':'Save changes'}</V2Button>{/snippet}
  </V2Modal>
{/each}

<script lang="ts">
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Field from '../components/V2Field.svelte';
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

  type Tag = { id:string; name:string; path:string; parent:string; assets:number; children:number; color:string };
  type TagModal = { id:number; mode:'create'|'edit'; tagId:string; name:string; color:string; parent:string };

  const tags: Tag[] = [
    { id:'people',name:'People',path:'People',parent:'',assets:4892,children:2104,color:'#66c6a3' },
    { id:'family',name:'Family',path:'People / Family',parent:'People',assets:430,children:28,color:'#9a78ff' },
    { id:'events',name:'Events',path:'People / Family / Events',parent:'Family',assets:118,children:4,color:'#9a78ff' },
    { id:'birthday',name:'Birthday',path:'People / Family / Events / Birthday',parent:'Events',assets:42,children:0,color:'#9a78ff' },
    { id:'friends',name:'Friends',path:'People / Friends',parent:'People',assets:126,children:0,color:'#66c6a3' },
    { id:'places',name:'Places',path:'Places',parent:'',assets:7211,children:1802,color:'#6ca8ff' },
    { id:'canada',name:'Canada',path:'Places / Canada',parent:'Places',assets:1204,children:184,color:'#6ca8ff' },
    { id:'quebec',name:'Québec',path:'Places / Canada / Québec',parent:'Canada',assets:404,children:31,color:'#6ca8ff' },
    { id:'montreal',name:'Montréal',path:'Places / Canada / Québec / Montréal',parent:'Québec',assets:84,children:2,color:'#6ca8ff' },
    { id:'plateau',name:'Plateau Mont-Royal',path:'Places / Canada / Québec / Montréal / Plateau Mont-Royal',parent:'Montréal',assets:31,children:0,color:'#6ca8ff' },
    { id:'projects',name:'Projects',path:'Projects',parent:'',assets:3941,children:642,color:'#efaa67' },
    { id:'immich',name:'Immich Companion',path:'Projects / Immich Companion',parent:'Projects',assets:892,children:0,color:'#efaa67' },
    { id:'workflow',name:'Workflow',path:'Workflow',parent:'',assets:806,children:94,color:'#dd82c7' },
    { id:'favorite-edits',name:'Favorite edits',path:'Workflow / Favorite edits',parent:'Workflow',assets:64,children:0,color:'#dd82c7' },
    { id:'receipts',name:'Receipts 2024',path:'Receipts 2024',parent:'',assets:52,children:0,color:'#d9c66b' },
    { id:'screenshots',name:'Reference screenshots',path:'Reference screenshots',parent:'',assets:412,children:0,color:'#9a78ff' },
  ];

  let query=$state(''), includeHierarchy=$state(false), selectedIds=$state<string[]>([]), page=$state(1);
  let modalSequence=0, modals=$state<TagModal[]>([]);
  const pageSize=100, total=60184;
  const normalizedQuery=$derived(query.trim().toLocaleLowerCase());
  const filteredTags=$derived(tags.filter((tag)=>{if(!normalizedQuery)return true;const direct=tag.name.toLocaleLowerCase().includes(normalizedQuery);return includeHierarchy?direct||tag.path.toLocaleLowerCase().includes(normalizedQuery):direct}));
  const paginationTotal=$derived(normalizedQuery ? Math.max(filteredTags.length,1) : total);

  function toggleSelection(id:string,checked:boolean){selectedIds=checked?[...new Set([...selectedIds,id])]:selectedIds.filter((value)=>value!==id)}
  function openCreate(){modals=[...modals,{id:++modalSequence,mode:'create',tagId:'',name:'',color:'#9A78FF',parent:''}]}
  function openEdit(tag:Tag){modals=[...modals,{id:++modalSequence,mode:'edit',tagId:tag.id,name:tag.name,color:tag.color,parent:tag.parent}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<TagModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  function parentOptionsFor(modal:TagModal){return tags.filter((tag)=>tag.children>0&&tag.id!==modal.tagId).map((tag)=>({value:tag.name,label:tag.name,subtitle:tag.path}))}
</script>

<V2PageLayout title="Tags" description="Search and manage large hierarchical tag libraries with optional parent-path matching.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={selectedIds.length===0}>Delete selected{selectedIds.length?` (${selectedIds.length})`:''}</V2Button><V2Button variant="primary" onclick={openCreate}>Create tag</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder="Search 60,000 tags…" oninput={(event)=>{query=event.currentTarget.value;page=1}}><V2Toggle label="Match through parent hierarchy" checked={includeHierarchy} onchange={(checked)=>{includeHierarchy=checked;page=1}}/><p class="v2-text-block v2-small v2-muted">{includeHierarchy?'Matches tag names and full parent paths. “Family” also finds descendants under People / Family.':'Matches tag names only. “Family” only returns tags whose own name matches.'}</p></V2Stack></V2Section><V2Section title="Scale"><V2Card><V2Stack gap="xs"><b>60,184 tags</b><span class="v2-small v2-muted">Demo rows represent a server-paged large library.</span><span class="v2-small v2-muted">Parent relationships may be multiple levels deep.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar><V2Inline gap="sm" wrap={true}><V2Badge text={`${filteredTags.length} demo matches`}/><V2Badge text={includeHierarchy?'Name + hierarchy':'Name only'}/><V2Badge text="60,184 total"/></V2Inline>{#snippet actions()}<V2Button>Name ↑</V2Button><V2Button>Assets</V2Button>{/snippet}</V2Toolbar>
    <V2Card><V2Table compact={true} layout="fixed"><thead><tr><th class="v2-tag-check-column"><span class="v2-visually-hidden">Select</span></th><th>Tag</th><th class="v2-tag-path-column">Path</th><th class="v2-collection-count-column">Assets</th><th class="v2-tag-children-column">Children</th><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>{#each filteredTags as tag (tag.id)}<tr><td class="v2-tag-check-column"><input type="checkbox" aria-label={`Select ${tag.name}`} checked={selectedIds.includes(tag.id)} onchange={(event)=>toggleSelection(tag.id,event.currentTarget.checked)}></td><td><span class="v2-tag-name"><span class="v2-tag-swatch" style:background={tag.color}></span><b>{tag.name}</b></span><span class="v2-tag-path v2-tag-path-condensed" title={tag.path}>{tag.parent?tag.path:'Root'}</span></td><td class="v2-tag-path-column"><span class="v2-tag-path" title={tag.path}>{tag.parent?tag.path:'Root'}</span></td><td class="v2-collection-count-column">{tag.assets.toLocaleString()}</td><td class="v2-tag-children-column">{tag.children.toLocaleString()}</td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button>Filter assets</V2Button><V2Button onclick={()=>openEdit(tag)}>Edit</V2Button><V2Button variant="danger">Delete</V2Button></V2Inline></td></tr>{:else}<tr><td colspan="6" class="v2-tag-empty">No demo tags match this search mode.</td></tr>{/each}</tbody></V2Table></V2Card>
    <V2Pagination {page} {pageSize} total={paginationTotal} onpage={(next)=>(page=next)}/>
  </V2Zone>
</V2PageLayout>

{#each modals as modal (modal.id)}
  <V2Modal
    id={`tag-modal-${modal.id}`}
    title={modal.mode==='create'?'Create tag':`Edit ${modal.name}`}
    description={modal.mode==='create'?'Create a demo tag with an optional parent.':'Update this demo tag and its parent relationship.'}
    size="md"
    onclose={()=>closeModal(modal.id)}
  >
    <V2Stack gap="md">
      <V2Field label="Name" value={modal.name} onchange={(value)=>updateModal(modal.id,{name:value})}/>
      <V2Field label="Color" value={modal.color} onchange={(value)=>updateModal(modal.id,{color:value})}/>
      <SelectField
        id={`tag-parent-modal-${modal.id}`}
        label="Parent"
        value={modal.parent}
        options={parentOptionsFor(modal)}
        allowEmpty={true}
        searchable={true}
        searchPlaceholder="Search parent tags or paths…"
        placeholder="No parent — root tag"
        onchange={(value)=>updateModal(modal.id,{parent:value})}
      />
      <V2Section title="Modal behavior demo">
        <V2Card><V2Stack gap="sm"><span class="v2-small v2-muted">Only the middle content region scrolls when the dialog is tall. The header and footer remain visible while dragging is constrained to the viewport.</span><V2Field label="Long-form notes" value="Use this field to make the modal taller at smaller viewport sizes and validate content-only scrolling." multiline={true}/></V2Stack></V2Card>
      </V2Section>
    </V2Stack>
    {#snippet footer()}<V2Button onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" onclick={()=>closeModal(modal.id)}>{modal.mode==='create'?'Create tag':'Save changes'}</V2Button>{/snippet}
  </V2Modal>
{/each}

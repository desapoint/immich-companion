<script lang="ts">
  import { onMount } from 'svelte';
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
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { createDemoAlbum, deleteDemoAlbums, demoAssetState, initializeDemoAssetState, updateDemoAlbum, type DemoAlbumRecord } from '../demo/demoAssetState.svelte';

  type AlbumModal = { id:number; mode:'create'|'edit'; albumId:string; name:string; description:string };

  let page=$state(1), pageSize=$state(24), resultMode=$state<ResultMode>('Pagination'), loaded=$state(24), sort=$state('name:asc'), query=$state('');
  let modalSequence=0, modals=$state<AlbumModal[]>([]), selectedIds=$state<string[]>([]);

  const normalizedQuery=$derived(query.trim().toLocaleLowerCase());
  const albums=$derived(demoAssetState.albums.filter((album)=>!normalizedQuery||`${album.album_name}\n${album.description}`.toLocaleLowerCase().includes(normalizedQuery)));
  const sortedAlbums=$derived([...albums].sort((a,b)=>{
    const [field,direction]=sort.split(':'), multiplier=direction==='desc'?-1:1;
    if(field==='assets') return (a.asset_count-b.asset_count)*multiplier;
    if(field==='description') return a.description.localeCompare(b.description)*multiplier;
    return a.album_name.localeCompare(b.album_name)*multiplier;
  }));
  const total=$derived(sortedAlbums.length);
  const visibleAlbums=$derived(resultMode==='Pagination' ? sortedAlbums.slice((page-1)*pageSize,(page-1)*pageSize+pageSize) : sortedAlbums.slice(0,Math.min(loaded,total)));

  function setPageSize(next:number){pageSize=next;page=1;loaded=Math.max(next,Math.min(loaded,total))}
  function setMode(mode:ResultMode){resultMode=mode;if(mode==='Pagination')page=1;else loaded=Math.max(pageSize,loaded)}
  function toggleSelection(id:string,checked:boolean){selectedIds=checked?[...new Set([...selectedIds,id])]:selectedIds.filter((value)=>value!==id)}
  function selectLoaded(){selectedIds=[...new Set([...selectedIds,...visibleAlbums.map((album)=>album.id)])]}
  function deleteSelected(){if(!selectedIds.length)return;deleteDemoAlbums(selectedIds);selectedIds=[];page=Math.min(page,Math.max(1,Math.ceil(total/pageSize)))}
  function openCreate(){modals=[...modals,{id:++modalSequence,mode:'create',albumId:'',name:'',description:''}]}
  function openEdit(album:DemoAlbumRecord){modals=[...modals,{id:++modalSequence,mode:'edit',albumId:album.id,name:album.album_name,description:album.description}]}
  function closeModal(id:number){modals=modals.filter((modal)=>modal.id!==id)}
  function updateModal(id:number,patch:Partial<AlbumModal>){modals=modals.map((modal)=>modal.id===id?{...modal,...patch}:modal)}
  function saveModal(modal:AlbumModal){if(!modal.name.trim())return;if(modal.mode==='create')createDemoAlbum(modal.name,modal.description);else updateDemoAlbum(modal.albumId,{name:modal.name,description:modal.description});closeModal(modal.id)}
  function filterAssets(albumId:string){if(typeof sessionStorage!=='undefined')sessionStorage.setItem('immichCompanionV2AssetFilterHandoff',JSON.stringify({albumIds:[albumId],tagIds:[]}));window.location.hash='assets'}

  onMount(()=>initializeDemoAssetState());
</script>

<V2PageLayout title="Albums" description="Search, sort, create, edit, delete and use albums to filter the shared demo asset workspace.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button disabled={!selectedIds.length} onclick={deleteSelected}>Delete selected{selectedIds.length?` (${selectedIds.length})`:''}</V2Button><V2Button variant="primary" onclick={openCreate}>Create album</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input value={query} placeholder="Search albums…" oninput={(event)=>{query=event.currentTarget.value;page=1;loaded=pageSize}}><V2Button variant="primary" onclick={()=>{page=1;loaded=pageSize}}>Search</V2Button></V2Stack></V2Section><V2Section title="Selection"><V2Button disabled={!visibleAlbums.length} onclick={selectLoaded}>Select loaded</V2Button></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar><V2Badge text={`${total} album${total===1?'':'s'}`}/>{#snippet actions()}<V2CollectionControls id="album-results" {sort} sortFields={[{value:'name',label:'Name'},{value:'assets',label:'Assets'},{value:'description',label:'Description'}]} {pageSize} pageSizes={[24,48,96]} {resultMode} onsort={(value)=>sort=value} onpagesize={setPageSize} onmode={setMode}/>{/snippet}</V2Toolbar>
    <V2Card><V2Table layout="fixed"><thead><tr><th class="v2-collection-check-column"><span class="v2-visually-hidden">Select</span></th><th>Name</th><th class="v2-collection-count-column">Assets</th><th class="v2-collection-description-column">Description</th><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead><tbody>
      {#each visibleAlbums as album (album.id)}<tr><td class="v2-collection-check-column"><input type="checkbox" aria-label={`Select ${album.album_name}`} checked={selectedIds.includes(album.id)} onchange={(event)=>toggleSelection(album.id,event.currentTarget.checked)}></td><td><b class="v2-collection-title">{album.album_name}</b></td><td class="v2-collection-count-column">{album.asset_count.toLocaleString()}</td><td class="v2-collection-description-column v2-muted"><span class="v2-collection-description">{album.description||'—'}</span></td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button onclick={()=>filterAssets(album.id)}>Filter assets</V2Button><V2Button onclick={()=>openEdit(album)}>Edit</V2Button><V2Button variant="danger" onclick={()=>deleteDemoAlbums([album.id])}>Delete</V2Button></V2Inline></td></tr>
      {:else}<tr><td colspan="5" class="v2-muted">No albums match this search.</td></tr>{/each}
    </tbody></V2Table></V2Card>
    {#if resultMode==='Pagination'}<V2Pagination {page} {pageSize} {total} onpage={(next)=>(page=next)}/>{:else}<V2InfiniteFooter loaded={Math.min(loaded,total)} {total} batchSize={pageSize} noun="albums" onloadmore={()=>loaded=Math.min(total,loaded+pageSize)}/>{/if}
  </V2Zone>
</V2PageLayout>

{#each modals as modal (modal.id)}
  <V2Modal id={`album-modal-${modal.id}`} title={modal.mode==='create'?'Create album':`Edit ${modal.name}`} description={modal.mode==='create'?'Add an album to the shared V2 demo state.':'Update this shared demo album.'} size="md" onclose={()=>closeModal(modal.id)}>
    <V2Stack gap="md"><V2Field label="Name" value={modal.name} onchange={(value)=>updateModal(modal.id,{name:value})}/><V2Field label="Description" value={modal.description} multiline={true} onchange={(value)=>updateModal(modal.id,{description:value})}/><V2Section title="Shared state"><V2Card><span class="v2-small v2-muted">Changes are reflected immediately in Assets relationship filters and asset counts.</span></V2Card></V2Section></V2Stack>
    {#snippet footer()}<V2Button onclick={()=>closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" disabled={!modal.name.trim()} onclick={()=>saveModal(modal)}>{modal.mode==='create'?'Create album':'Save changes'}</V2Button>{/snippet}
  </V2Modal>
{/each}

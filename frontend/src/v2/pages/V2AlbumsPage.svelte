<script lang="ts">
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

  type AlbumModal = { id:number; mode:'create'|'edit'; name:string; description:string };
  type AlbumRow = { name:string; assets:number; description:string };

  let page = $state(1);
  let pageSize = $state(24);
  let resultMode = $state<ResultMode>('Pagination');
  let loaded = $state(24);
  let sort = $state('name:asc');
  let modalSequence = 0;
  let modals = $state<AlbumModal[]>([]);
  const total = 42;
  const albums: AlbumRow[] = [
    {name:'Family',assets:822,description:'Family photos'},
    {name:'Trips',assets:416,description:'Travel albums'},
    {name:'Screenshots',assets:201,description:'Captured screenshots'},
    {name:'Favorites Export',assets:99,description:'Export-ready favorites'},
    {name:'Projects',assets:64,description:'Project references'},
    {name:'Camera Imports',assets:1204,description:'Camera import batches'},
  ];
  const sortedAlbums = $derived([...albums].sort((a,b)=>{
    const [field,direction] = sort.split(':');
    const multiplier = direction === 'desc' ? -1 : 1;
    if (field === 'assets') return (a.assets-b.assets)*multiplier;
    if (field === 'description') return a.description.localeCompare(b.description)*multiplier;
    return a.name.localeCompare(b.name)*multiplier;
  }));

  function setPageSize(next: number): void {
    pageSize = next;
    page = 1;
    loaded = Math.max(next, Math.min(loaded, total));
  }

  function setMode(mode: ResultMode): void {
    resultMode = mode;
    if (mode === 'Pagination') page = 1;
    else loaded = Math.max(pageSize, loaded);
  }

  function openCreate(): void {
    modals = [...modals, { id: ++modalSequence, mode:'create', name:'', description:'' }];
  }

  function openEdit(name: string): void {
    const album = albums.find((item)=>item.name===name);
    modals = [...modals, { id: ++modalSequence, mode:'edit', name, description:album?.description ?? `${name} album description` }];
  }

  function closeModal(id: number): void {
    modals = modals.filter((modal) => modal.id !== id);
  }

  function updateModal(id: number, patch: Partial<AlbumModal>): void {
    modals = modals.map((modal) => modal.id === id ? { ...modal, ...patch } : modal);
  }
</script>

<V2PageLayout title="Albums" description="Search, sort, create, edit, delete and use albums to filter the Assets workspace.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Delete selected</V2Button><V2Button variant="primary" onclick={openCreate}>Create album</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input placeholder="Search albums…"><V2Button variant="primary">Search</V2Button></V2Stack></V2Section><V2Section title="Selection"><V2Button>Select loaded</V2Button></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar>
      <V2Badge text={`${total} albums`} />
      {#snippet actions()}
        <V2CollectionControls
          id="album-results"
          {sort}
          sortFields={[{value:'name',label:'Name'},{value:'assets',label:'Assets'},{value:'description',label:'Description'}]}
          {pageSize}
          pageSizes={[24,48,96]}
          {resultMode}
          onsort={(value)=>sort=value}
          onpagesize={setPageSize}
          onmode={setMode}
        />
      {/snippet}
    </V2Toolbar>
    <V2Card>
      <V2Table layout="fixed">
        <thead><tr><th class="v2-collection-check-column"></th><th>Name</th><th class="v2-collection-count-column">Assets</th><th class="v2-collection-description-column">Description</th><th class="v2-table-actions v2-collection-actions-column">Actions</th></tr></thead>
        <tbody>{#each sortedAlbums as album}<tr><td class="v2-collection-check-column"><input type="checkbox" aria-label={`Select ${album.name}`}></td><td><b class="v2-collection-title">{album.name}</b></td><td class="v2-collection-count-column">{album.assets}</td><td class="v2-collection-description-column v2-muted"><span class="v2-collection-description">{album.description}</span></td><td class="v2-table-actions v2-collection-actions-column"><V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}><V2Button>Filter assets</V2Button><V2Button onclick={() => openEdit(album.name)}>Edit</V2Button><V2Button variant="danger">Delete</V2Button></V2Inline></td></tr>{/each}</tbody>
      </V2Table>
    </V2Card>
    {#if resultMode === 'Pagination'}
      <V2Pagination {page} {pageSize} {total} onpage={(next) => (page = next)} />
    {:else}
      <V2InfiniteFooter loaded={Math.min(loaded,total)} {total} batchSize={pageSize} noun="albums" onloadmore={()=>loaded=Math.min(total,loaded+pageSize)}/>
    {/if}
  </V2Zone>
</V2PageLayout>

{#each modals as modal (modal.id)}
  <V2Modal
    id={`album-modal-${modal.id}`}
    title={modal.mode === 'create' ? 'Create album' : `Edit ${modal.name}`}
    description={modal.mode === 'create' ? 'Add a demo album.' : 'Update this demo album.'}
    size="md"
    onclose={() => closeModal(modal.id)}
  >
    <V2Stack gap="md">
      <V2Field label="Name" value={modal.name} onchange={(value) => updateModal(modal.id, { name:value })}/>
      <V2Field label="Description" value={modal.description} multiline={true} onchange={(value) => updateModal(modal.id, { description:value })}/>
      <V2Section title="Modal behavior demo">
        <V2Card><V2Stack gap="sm"><span class="v2-small v2-muted">Drag the header. The modal stays inside the viewport; only this content region scrolls if it becomes too tall.</span><V2Field label="Extra notes" value="This extra field makes the content area easier to test at smaller viewport heights." multiline={true}/></V2Stack></V2Card>
      </V2Section>
    </V2Stack>
    {#snippet footer()}<V2Button onclick={() => closeModal(modal.id)}>Cancel</V2Button><V2Button variant="primary" onclick={() => closeModal(modal.id)}>{modal.mode === 'create' ? 'Create album' : 'Save changes'}</V2Button>{/snippet}
  </V2Modal>
{/each}

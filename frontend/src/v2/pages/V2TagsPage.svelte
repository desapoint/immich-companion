<script lang="ts">
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Table from '../components/V2Table.svelte';
  import V2TagEditor from '../components/V2TagEditor.svelte';
  import V2Toggle from '../components/V2Toggle.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';

  type Tag = {
    id: string;
    name: string;
    path: string;
    parent: string;
    assets: number;
    children: number;
    color: string;
  };

  const tags: Tag[] = [
    { id: 'people', name: 'People', path: 'People', parent: '', assets: 4892, children: 2104, color: '#66c6a3' },
    { id: 'family', name: 'Family', path: 'People / Family', parent: 'People', assets: 430, children: 28, color: '#9a78ff' },
    { id: 'events', name: 'Events', path: 'People / Family / Events', parent: 'Family', assets: 118, children: 4, color: '#9a78ff' },
    { id: 'birthday', name: 'Birthday', path: 'People / Family / Events / Birthday', parent: 'Events', assets: 42, children: 0, color: '#9a78ff' },
    { id: 'friends', name: 'Friends', path: 'People / Friends', parent: 'People', assets: 126, children: 0, color: '#66c6a3' },
    { id: 'places', name: 'Places', path: 'Places', parent: '', assets: 7211, children: 1802, color: '#6ca8ff' },
    { id: 'canada', name: 'Canada', path: 'Places / Canada', parent: 'Places', assets: 1204, children: 184, color: '#6ca8ff' },
    { id: 'quebec', name: 'Québec', path: 'Places / Canada / Québec', parent: 'Canada', assets: 404, children: 31, color: '#6ca8ff' },
    { id: 'montreal', name: 'Montréal', path: 'Places / Canada / Québec / Montréal', parent: 'Québec', assets: 84, children: 2, color: '#6ca8ff' },
    { id: 'plateau', name: 'Plateau Mont-Royal', path: 'Places / Canada / Québec / Montréal / Plateau Mont-Royal', parent: 'Montréal', assets: 31, children: 0, color: '#6ca8ff' },
    { id: 'projects', name: 'Projects', path: 'Projects', parent: '', assets: 3941, children: 642, color: '#efaa67' },
    { id: 'immich', name: 'Immich Companion', path: 'Projects / Immich Companion', parent: 'Projects', assets: 892, children: 0, color: '#efaa67' },
    { id: 'workflow', name: 'Workflow', path: 'Workflow', parent: '', assets: 806, children: 94, color: '#dd82c7' },
    { id: 'favorite-edits', name: 'Favorite edits', path: 'Workflow / Favorite edits', parent: 'Workflow', assets: 64, children: 0, color: '#dd82c7' },
    { id: 'receipts', name: 'Receipts 2024', path: 'Receipts 2024', parent: '', assets: 52, children: 0, color: '#d9c66b' },
    { id: 'screenshots', name: 'Reference screenshots', path: 'Reference screenshots', parent: '', assets: 412, children: 0, color: '#9a78ff' },
  ];

  let query = $state('');
  let includeHierarchy = $state(false);
  let selectedIds = $state<string[]>([]);
  let editorMode = $state<'create' | 'edit' | null>(null);
  let editorTag = $state<Tag | null>(null);

  const normalizedQuery = $derived(query.trim().toLocaleLowerCase());
  const filteredTags = $derived(tags.filter((tag) => {
    if (!normalizedQuery) return true;
    const directMatch = tag.name.toLocaleLowerCase().includes(normalizedQuery);
    if (!includeHierarchy) return directMatch;
    return directMatch || tag.path.toLocaleLowerCase().includes(normalizedQuery);
  }));

  const parentOptions = $derived(tags
    .filter((tag) => tag.children > 0 && tag.id !== editorTag?.id)
    .map((tag) => ({ value: tag.name, label: tag.path })));

  function toggleSelection(id: string, checked: boolean): void {
    selectedIds = checked
      ? [...selectedIds, id].filter((value, index, all) => all.indexOf(value) === index)
      : selectedIds.filter((value) => value !== id);
  }

  function openCreate(): void {
    editorTag = null;
    editorMode = 'create';
  }

  function openEdit(tag: Tag): void {
    editorTag = tag;
    editorMode = 'edit';
  }

  function closeEditor(): void {
    editorMode = null;
    editorTag = null;
  }
</script>

<V2PageLayout title="Tags" description="Search and manage large hierarchical tag libraries with optional parent-path matching.">
  {#snippet headerActions()}
    <V2Inline gap="sm">
      <V2Button disabled={selectedIds.length === 0}>Delete selected{selectedIds.length ? ` (${selectedIds.length})` : ''}</V2Button>
      <V2Button variant="primary" onclick={openCreate}>Create tag</V2Button>
    </V2Inline>
  {/snippet}

  {#snippet context()}
    <V2Zone>
      <V2Section title="Search">
        <V2Stack gap="sm">
          <input
            value={query}
            placeholder="Search 60,000 tags…"
            oninput={(event) => (query = event.currentTarget.value)}
          >
          <V2Toggle
            label="Match through parent hierarchy"
            checked={includeHierarchy}
            onchange={(checked) => (includeHierarchy = checked)}
          />
          <p class="v2-text-block v2-small v2-muted">
            {includeHierarchy
              ? 'Matches tag names and full parent paths. “Family” also finds descendants under People / Family.'
              : 'Matches tag names only. “Family” only returns tags whose own name matches.'}
          </p>
        </V2Stack>
      </V2Section>

      <V2Section title="Scale">
        <V2Card>
          <V2Stack gap="xs">
            <b>60,184 tags</b>
            <span class="v2-small v2-muted">Demo rows represent a server-paged large library.</span>
            <span class="v2-small v2-muted">Parent relationships may be multiple levels deep.</span>
          </V2Stack>
        </V2Card>
      </V2Section>
    </V2Zone>
  {/snippet}

  <V2Zone>
    <V2Toolbar>
      <V2Inline gap="sm" wrap={true}>
        <V2Badge text={`${filteredTags.length} demo matches`} />
        <V2Badge text={includeHierarchy ? 'Name + hierarchy' : 'Name only'} />
        <V2Badge text="60,184 total" />
      </V2Inline>
      {#snippet actions()}
        <V2Button>Name ↑</V2Button>
        <V2Button>Assets</V2Button>
      {/snippet}
    </V2Toolbar>

    <V2Card>
      <V2Table compact={true}>
        <thead>
          <tr>
            <th class="v2-tag-check-column"><span class="v2-visually-hidden">Select</span></th>
            <th>Tag</th>
            <th class="v2-tag-path-column">Path</th>
            <th>Assets</th>
            <th>Children</th>
            <th class="v2-table-actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredTags as tag (tag.id)}
            <tr>
              <td class="v2-tag-check-column">
                <input
                  type="checkbox"
                  aria-label={`Select ${tag.name}`}
                  checked={selectedIds.includes(tag.id)}
                  onchange={(event) => toggleSelection(tag.id, event.currentTarget.checked)}
                >
              </td>
              <td>
                <span class="v2-tag-name"><span class="v2-tag-swatch" style:background={tag.color}></span><b>{tag.name}</b></span>
                <span class="v2-tag-path v2-tag-path-condensed" title={tag.path}>{tag.parent ? tag.path : 'Root'}</span>
              </td>
              <td class="v2-tag-path-column"><span class="v2-tag-path" title={tag.path}>{tag.parent ? tag.path : 'Root'}</span></td>
              <td>{tag.assets.toLocaleString()}</td>
              <td>{tag.children.toLocaleString()}</td>
              <td class="v2-table-actions">
                <V2Inline class="v2-table-actions-content" gap="sm" justify="end" wrap={false}>
                  <V2Button>Filter assets</V2Button>
                  <V2Button onclick={() => openEdit(tag)}>Edit</V2Button>
                  <V2Button variant="danger">Delete</V2Button>
                </V2Inline>
              </td>
            </tr>
          {:else}
            <tr><td colspan="6" class="v2-tag-empty">No demo tags match this search mode.</td></tr>
          {/each}
        </tbody>
      </V2Table>
    </V2Card>

    <div class="v2-tag-pager">
      <span class="v2-small v2-muted">Page 1 of 602 · 100 rows per page</span>
      <V2Inline gap="sm"><V2Button disabled={true}>Previous</V2Button><V2Button>Next</V2Button></V2Inline>
    </div>
  </V2Zone>

  {#snippet inspector()}
    <V2Zone>
      <V2Section title={editorMode === 'create' ? 'Create tag' : editorMode === 'edit' ? 'Edit tag' : 'Tag editor'}>
        {#if editorMode}
          <V2TagEditor
            mode={editorMode}
            name={editorTag?.name ?? ''}
            color={editorTag?.color ?? '#9A78FF'}
            parent={editorTag?.parent ?? ''}
            {parentOptions}
            oncancel={closeEditor}
            onsave={closeEditor}
          />
        {:else}
          <V2Card>
            <V2Stack gap="sm">
              <b>Edit or create a tag</b>
              <p class="v2-text-block v2-small v2-muted">Choose Edit on a row or Create tag above. The parent field supports root tags and nested parent relationships.</p>
              <V2Button variant="primary" onclick={openCreate}>Create tag</V2Button>
            </V2Stack>
          </V2Card>
        {/if}
      </V2Section>
    </V2Zone>
  {/snippet}
</V2PageLayout>

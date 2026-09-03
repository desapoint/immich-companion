<script lang="ts">
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Table from '../components/V2Table.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';

  let selected = $state('Family');
  const albums = [['Family',822],['Trips',416],['Screenshots',201],['Favorites Export',99],['Projects',64],['Camera Imports',1204]] as const;
</script>

<V2PageLayout title="Albums" description="Search, sort, create, edit, delete and use albums to filter the Assets workspace.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Delete selected</V2Button><V2Button variant="primary">Create album</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Search"><V2Stack gap="sm"><input placeholder="Search albums…"><V2Button variant="primary">Search</V2Button></V2Stack></V2Section><V2Section title="Sort"><V2Inline gap="sm"><V2Button active={true}>Name ↑</V2Button><V2Button>Assets</V2Button></V2Inline></V2Section><V2Section title="Selection"><V2Button>Select visible</V2Button></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar>
      <V2Badge text="42 albums" />
      {#snippet actions()}<V2Button disabled={true}>Previous</V2Button><V2Button>Next</V2Button>{/snippet}
    </V2Toolbar>
    <V2Card><V2Table><thead><tr><th></th><th>Name</th><th>Assets</th><th>Description</th><th>Actions</th></tr></thead><tbody>{#each albums as album}<tr><td><input type="checkbox"></td><td><b>{album[0]}</b></td><td>{album[1]}</td><td class="v2-muted">Album description</td><td><V2Inline gap="sm" wrap={true}><V2Button>Filter assets</V2Button><V2Button onclick={() => selected = album[0]}>Edit</V2Button><V2Button variant="danger">Delete</V2Button></V2Inline></td></tr>{/each}</tbody></V2Table></V2Card>
  </V2Zone>

  {#snippet inspector()}<V2Zone><V2Section title="Album editor"><V2Card><V2Stack gap="sm"><V2Field label="Name" value={selected}/><V2Field label="Description" value="Family photos" multiline={true}/><V2Inline gap="sm"><V2Button>Cancel</V2Button><V2Button variant="primary">Save changes</V2Button></V2Inline></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>

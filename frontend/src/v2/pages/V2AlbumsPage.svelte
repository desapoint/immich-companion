<script lang="ts">
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';

  let selected = $state('Family');
  const albums = [['Family',822],['Trips',416],['Screenshots',201],['Favorites Export',99],['Projects',64],['Camera Imports',1204]] as const;
</script>

<V2PageLayout title="Albums" description="Search, sort, create, edit, delete and use albums to filter the Assets workspace.">
  {#snippet headerActions()}<V2Inline gap="sm"><button class="v2-button">Delete selected</button><button class="v2-button v2-button-primary">Create album</button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone label="Context rail"><V2Section title="Search"><V2Stack gap="sm"><input placeholder="Search albums…"><button class="v2-button v2-button-primary">Search</button></V2Stack></V2Section><V2Section title="Sort"><V2Inline gap="sm"><button class="v2-button v2-button-primary">Name ↑</button><button class="v2-button">Assets</button></V2Inline></V2Section><V2Section title="Selection"><button class="v2-button">Select visible</button></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar label="Primary content">
      <V2Badge text="42 albums" />
      {#snippet actions()}<button class="v2-button" disabled>Previous</button><button class="v2-button">Next</button>{/snippet}
    </V2Toolbar>
    <V2Card><div class="v2-table-wrap"><table class="v2-table"><thead><tr><th class="v2-table-heading"></th><th class="v2-table-heading">Name</th><th class="v2-table-heading">Assets</th><th class="v2-table-heading">Description</th><th class="v2-table-heading">Actions</th></tr></thead><tbody>{#each albums as album}<tr><td class="v2-table-cell"><input type="checkbox"></td><td class="v2-table-cell"><b>{album[0]}</b></td><td class="v2-table-cell">{album[1]}</td><td class="v2-table-cell v2-muted">Album description</td><td class="v2-table-cell"><V2Inline gap="sm" wrap={true}><button class="v2-button">Filter assets</button><button class="v2-button" onclick={() => selected = album[0]}>Edit</button><button class="v2-button v2-button-danger">Delete</button></V2Inline></td></tr>{/each}</tbody></table></div></V2Card>
  </V2Zone>

  {#snippet inspector()}<V2Zone label="Inspector"><V2Section title="Album editor"><V2Card><V2Stack gap="sm"><V2Field label="Name" value={selected}/><label class="v2-field"><span>Description</span><textarea>Family photos</textarea></label><V2Inline gap="sm"><button class="v2-button">Cancel</button><button class="v2-button v2-button-primary">Save changes</button></V2Inline></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>

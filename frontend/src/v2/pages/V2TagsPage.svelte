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
  const tags = [['Family','People / Family',430],['Vacation','Places / Vacation',221],['Work','Projects / Work',89],['Favorite edits','Workflow / Favorite edits',64]] as const;
</script>

<V2PageLayout title="Tags" description="Manage searchable hierarchical tags, parent relationships, colors and asset filters.">
  {#snippet headerActions()}<V2Inline gap="sm"><button class="v2-button">Delete selected</button><button class="v2-button v2-button-primary">Create tag</button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone label="Context rail"><V2Section title="Tag tree"><V2Stack gap="xs"><button class="v2-tree-line active"><span class="v2-swatch"></span>People</button><button class="v2-tree-line">↳ Family</button><button class="v2-tree-line">↳ Friends</button><button class="v2-tree-line"><span class="v2-swatch alt"></span>Places</button><button class="v2-tree-line">↳ Canada</button><button class="v2-tree-line">↳ Europe</button></V2Stack></V2Section><V2Section title="Search"><V2Stack gap="sm"><input placeholder="Search tags…"><button class="v2-button v2-button-primary">Search</button></V2Stack></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar label="Primary content">
      <V2Badge text="67 tags" />
      {#snippet actions()}<button class="v2-button">Name ↑</button><button class="v2-button">Assets</button>{/snippet}
    </V2Toolbar>
    <V2Card><div class="v2-table-wrap"><table class="v2-table"><thead><tr><th class="v2-table-heading"></th><th class="v2-table-heading">Tag</th><th class="v2-table-heading">Path</th><th class="v2-table-heading">Assets</th><th class="v2-table-heading">Actions</th></tr></thead><tbody>{#each tags as tag}<tr><td class="v2-table-cell"><input type="checkbox"></td><td class="v2-table-cell"><span class="v2-swatch"></span><b>{tag[0]}</b></td><td class="v2-table-cell v2-muted">{tag[1]}</td><td class="v2-table-cell">{tag[2]}</td><td class="v2-table-cell"><V2Inline gap="sm" wrap={true}><button class="v2-button">Filter assets</button><button class="v2-button" onclick={() => selected = tag[0]}>Edit</button><button class="v2-button v2-button-danger">Delete</button></V2Inline></td></tr>{/each}</tbody></table></div></V2Card>
  </V2Zone>

  {#snippet inspector()}<V2Zone label="Inspector"><V2Section title="Tag editor"><V2Card><V2Stack gap="sm"><V2Field label="Name" value={selected}/><V2Field label="Color" value="#9A78FF"/><V2Field label="Parent" options={['People','Places','Projects','Workflow']}/><V2Inline gap="sm"><button class="v2-button">Cancel</button><button class="v2-button v2-button-primary">Save changes</button></V2Inline></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>

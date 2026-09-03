<script lang="ts">
  import SelectField from '../components/SelectField.svelte';
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
  const tags = [['Family','People / Family',430],['Vacation','Places / Vacation',221],['Work','Projects / Work',89],['Favorite edits','Workflow / Favorite edits',64]] as const;
</script>

<V2PageLayout title="Tags" description="Manage searchable hierarchical tags, parent relationships, colors and asset filters.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Delete selected</V2Button><V2Button variant="primary">Create tag</V2Button></V2Inline>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Tag tree"><V2Stack gap="xs"><button class="v2-tree-line" aria-current="true"><span class="v2-swatch"></span>People</button><button class="v2-tree-line">   ▾ Family</button><button class="v2-tree-line">   ▸ Friends</button><button class="v2-tree-line"><span class="v2-swatch" data-variant="alt"></span>Places</button><button class="v2-tree-line">   ▸ Canada</button><button class="v2-tree-line">   ▸ Europe</button></V2Stack></V2Section><V2Section title="Search"><V2Stack gap="sm"><input placeholder="Search tags…"><V2Button variant="primary">Search</V2Button></V2Stack></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar>
      <V2Badge text="67 tags" />
      {#snippet actions()}<V2Button>Name ↑</V2Button><V2Button>Assets</V2Button>{/snippet}
    </V2Toolbar>
    <V2Card><V2Table><thead><tr><th></th><th>Tag</th><th>Path</th><th>Assets</th><th>Actions</th></tr></thead><tbody>{#each tags as tag}<tr><td><input type="checkbox"></td><td><span class="v2-swatch"></span><b>{tag[0]}</b></td><td class="v2-muted">{tag[1]}</td><td>{tag[2]}</td><td><V2Inline gap="sm" wrap={true}><V2Button>Filter assets</V2Button><V2Button onclick={() => selected = tag[0]}>Edit</V2Button><V2Button variant="danger">Delete</V2Button></V2Inline></td></tr>{/each}</tbody></V2Table></V2Card>
  </V2Zone>

  {#snippet inspector()}<V2Zone><V2Section title="Tag editor"><V2Card><V2Stack gap="sm"><V2Field label="Name" value={selected}/><V2Field label="Color" value="#9A78FF"/><SelectField id="tag-parent" label="Parent" options={['People','Places','Projects','Workflow']}/><V2Inline gap="sm"><V2Button>Cancel</V2Button><V2Button variant="primary">Save changes</V2Button></V2Inline></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>

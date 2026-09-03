<script lang="ts">
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Zone from '../components/V2Zone.svelte';

  let page = $state(1);
  let viewer = $state(false);
  const total = 126;
  const pageSize = 16;
  const maxPage = Math.ceil(total / pageSize);
  const items = Array.from({ length: pageSize }, (_, i) => i);
</script>

<V2PageLayout title="Restore" description="Review current Immich trash and restore individual, selected, or all trashed assets.">
  {#snippet headerActions()}<V2Inline gap="sm"><V2Button>Restore selected</V2Button><V2Button variant="primary">Restore all</V2Button></V2Inline>{/snippet}

  {#snippet context()}
    <V2Zone label="Context rail">
      <V2Section title="Trash summary"><V2Card><V2Stack gap="sm"><b>{total} items</b><span class="v2-small v2-muted">Loaded directly from current Immich trash.</span></V2Stack></V2Card></V2Section>
      <V2Section title="Selection"><V2Stack gap="sm"><V2Button>Select all on page</V2Button><V2Button>Clear selection</V2Button></V2Stack></V2Section>
      <V2Card><span class="v2-small v2-muted">Display density is controlled globally from the header.</span></V2Card>
    </V2Zone>
  {/snippet}

  <V2Zone>
    <V2Toolbar label="Primary content">
      <V2Badge text={`Page ${page} · ${Math.min(pageSize, total - (page - 1) * pageSize)} items`} />
      {#snippet actions()}<V2Button disabled={page === 1} onclick={() => page--}>Previous</V2Button><V2Button disabled={page === maxPage} onclick={() => page++}>Next</V2Button>{/snippet}
    </V2Toolbar>
    <div class="v2-asset-grid">{#each items.slice(0, Math.min(pageSize, total - (page - 1) * pageSize)) as i}<V2AssetTile index={i} label={`Trash item ${(page - 1) * pageSize + i + 1}`} sublabel="Deleted recently" onclick={() => viewer = true} />{/each}</div>
  </V2Zone>

  {#snippet inspector()}
    <V2Zone label="Inspector"><V2Section title="Selected trash"><V2Card><V2Stack gap="sm"><b>4 selected</b><span class="v2-small v2-muted">Restore is the only mutation available in this workspace/viewer.</span><V2Button variant="primary">Restore selected</V2Button></V2Stack></V2Card></V2Section></V2Zone>
  {/snippet}
</V2PageLayout>

<V2Viewer open={viewer} title="Restore Viewer" mode="restore" onclose={() => viewer = false} />

<script lang="ts">
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2AssetTile from '../components/V2AssetTile.svelte';
  import V2Viewer from '../components/V2Viewer.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';

  let page = $state(1);
  let viewer = $state(false);
  const items = Array.from({ length: 16 }, (_, i) => i);
</script>

<V2PageLayout title="Restore" description="Review current Immich trash and restore individual, selected, or all trashed assets.">
  {#snippet headerActions()}<V2Inline gap="sm"><button class="v2-button">Restore selected</button><button class="v2-button v2-button-primary">Restore all</button></V2Inline>{/snippet}

  {#snippet context()}
    <V2Zone label="Context rail">
      <V2Section title="Trash summary"><V2Card><V2Stack gap="sm"><b>126 items</b><span class="v2-small v2-muted">Loaded directly from current Immich trash.</span></V2Stack></V2Card></V2Section>
      <V2Section title="Selection"><V2Stack gap="sm"><button class="v2-button">Select all on page</button><button class="v2-button">Clear selection</button></V2Stack></V2Section>
      <V2Card><span class="v2-small v2-muted">Display density is controlled globally from the header.</span></V2Card>
    </V2Zone>
  {/snippet}

  <V2Zone>
    <V2Toolbar label="Primary content">
      <V2Badge text={`Page ${page} · 48 items`} />
      {#snippet actions()}<button class="v2-button" disabled={page === 1} onclick={() => page--}>Previous</button><button class="v2-button" onclick={() => page++}>Next</button>{/snippet}
    </V2Toolbar>
    <div class="v2-asset-grid">{#each items as i}<V2AssetTile index={i} label={`Trash item ${(page - 1) * 16 + i + 1}`} sublabel="Deleted recently" onclick={() => viewer = true} />{/each}</div>
  </V2Zone>

  {#snippet inspector()}
    <V2Zone label="Inspector"><V2Section title="Selected trash"><V2Card><V2Stack gap="sm"><b>4 selected</b><span class="v2-small v2-muted">Restore is the only mutation available in this workspace/viewer.</span><button class="v2-button v2-button-primary">Restore selected</button></V2Stack></V2Card></V2Section></V2Zone>
  {/snippet}
</V2PageLayout>

<V2Viewer open={viewer} title="Restore Viewer" mode="restore" onclose={() => viewer = false} />

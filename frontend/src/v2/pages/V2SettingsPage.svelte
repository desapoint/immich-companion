<script lang="ts">
  import { onMount } from 'svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Menu from '../components/V2Menu.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { readV2Density, V2_DENSITY_EVENT, writeV2Density, type V2Density } from '../state/density';

  let tab = $state('General');
  let density = $state<V2Density>('standard');

  function setDensity(next: V2Density): void {
    density = next;
    writeV2Density(next);
  }

  onMount(() => {
    density = readV2Density();
    const onDensity = (event: Event) => density = (event as CustomEvent<V2Density>).detail;
    window.addEventListener(V2_DENSITY_EVENT, onDensity);
    return () => window.removeEventListener(V2_DENSITY_EVENT, onDensity);
  });
</script>

<V2PageLayout title="Settings" description="Configure background load limits, duplicate defaults and incremental/global synchronization schedules.">
  {#snippet tabs()}<V2Tabs items={['General','Duplicates','Schedules']} active={tab} onselect={(value) => tab = value}/>{/snippet}
  {#snippet context()}<V2Zone><V2Section title="Settings sections"><V2Menu items={['Background load','Duplicate handling','Sync schedules']} active="Background load" ariaLabel="Settings sections" /></V2Section><V2Card><span class="v2-small v2-muted">Each settings block saves independently. Editing a draft does not persist until its Save action is used.</span></V2Card></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar sticky={false}><b>Configuration</b></V2Toolbar>
    <div class="v2-setting-grid">
      <V2Card title="Interface density">{#snippet actions()}<V2Badge tone="ok" text="Local preference"/>{/snippet}<V2Stack gap="sm"><span class="v2-small v2-muted">Controls spacing, table row height, card padding and grid thumbnail density across collection interfaces.</span><V2Segmented items={['Standard','Condensed']} active={density === 'standard' ? 'Standard' : 'Condensed'} onselect={(value) => setDensity(value === 'Standard' ? 'standard' : 'condensed')} ariaLabel="Interface density" /></V2Stack></V2Card>
      <V2Card title="Background batch load">{#snippet actions()}<V2Badge tone="ok" text="Saved"/>{/snippet}<V2Stack gap="sm"><V2Field label="Assets per batch · 1–500" type="number" value="100"/><V2Field label="Minimum delay (seconds) · 0–60" type="number" value="1"/><V2Button variant="primary">Save load settings</V2Button></V2Stack></V2Card>
      <V2Card title="Duplicate automatic handling"><V2Stack gap="sm"><V2Field label="Exact-file action" options={['Resolve exact files','Keep all exact copies','Stack exact copies','Always review']}/><V2Field label="Primary rule" options={['Prefer Immich uploads','Prefer external files','Most recently uploaded','First Immich result']}/><V2Checkbox label="Enable automatic recommendations" checked={true}/><V2Checkbox label="Analyze candidate files automatically" checked={true}/><V2Button variant="primary">Save duplicate policy</V2Button></V2Stack></V2Card>
      <V2Card title="Incremental sync">{#snippet actions()}<V2Badge tone="ok" text="Enabled"/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled" checked={true}/><V2Field label="Cron" value="*/15 * * * *"/><V2Inline gap="sm" wrap={true}>{#each ['15 min','Hourly','Daily','Weekly'] as preset}<V2Button>{preset}</V2Button>{/each}</V2Inline><span class="v2-small v2-muted">Next run: 13:15</span><V2Button variant="primary">Save schedule</V2Button></V2Stack></V2Card>
      <V2Card title="Global sync">{#snippet actions()}<V2Badge text="Disabled"/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled"/><V2Field label="Cron" value="0 0 * * 0"/><V2Inline gap="sm" wrap={true}>{#each ['15 min','Hourly','Daily','Weekly'] as preset}<V2Button>{preset}</V2Button>{/each}</V2Inline><span class="v2-small v2-muted">Next run: disabled</span><V2Button variant="primary">Save schedule</V2Button></V2Stack></V2Card>
    </div>
  </V2Zone>

  {#snippet inspector()}<V2Zone><V2Section title="Validation"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Batch size valid"/><V2Badge tone="ok" text="Delay valid"/><span class="v2-small v2-muted">Invalid values disable the relevant save action.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>

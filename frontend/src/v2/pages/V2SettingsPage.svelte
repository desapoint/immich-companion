<script lang="ts">
  import { onMount } from 'svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
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
  {#snippet tabs()}<V2Tabs items={['General','Duplicates','Schedules']} active={tab} onselect={(v) => tab = v}/>{/snippet}
  {#snippet context()}<V2Zone label="Context rail"><V2Section title="Settings sections"><V2Stack gap="xs"><button class="v2-nav-button active">Background load</button><button class="v2-nav-button">Duplicate handling</button><button class="v2-nav-button">Sync schedules</button></V2Stack></V2Section><V2Card><span class="v2-small v2-muted">Each settings block saves independently. Editing a draft does not persist until its Save action is used.</span></V2Card></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar label="Primary content" sticky={false}><b>Configuration</b></V2Toolbar>
    <div class="v2-setting-grid">
      <V2Card><V2Stack gap="sm"><V2Inline justify="between"><h3 class="v2-section-heading">Interface density</h3><V2Badge tone="ok" text="Local preference"/></V2Inline><span class="v2-small v2-muted">Controls spacing, table row height, card padding and grid thumbnail density across collection interfaces.</span><div class="v2-segmented"><button class:active={density==='standard'} onclick={() => setDensity('standard')}>Standard</button><button class:active={density==='condensed'} onclick={() => setDensity('condensed')}>Condensed</button></div></V2Stack></V2Card>
      <V2Card><V2Stack gap="sm"><V2Inline justify="between"><h3 class="v2-section-heading">Background batch load</h3><V2Badge tone="ok" text="Saved"/></V2Inline><V2Field label="Assets per batch · 1–500" type="number" value="100"/><V2Field label="Minimum delay (seconds) · 0–60" type="number" value="1"/><button class="v2-button v2-button-primary">Save load settings</button></V2Stack></V2Card>
      <V2Card><V2Stack gap="sm"><h3 class="v2-section-heading">Duplicate automatic handling</h3><V2Field label="Exact-file action" options={['Resolve exact files','Keep all exact copies','Stack exact copies','Always review']}/><V2Field label="Primary rule" options={['Prefer Immich uploads','Prefer external files','Most recently uploaded','First Immich result']}/><label class="v2-check-row"><input type="checkbox" checked>Enable automatic recommendations</label><label class="v2-check-row"><input type="checkbox" checked>Analyze candidate files automatically</label><button class="v2-button v2-button-primary">Save duplicate policy</button></V2Stack></V2Card>
      <V2Card><V2Stack gap="sm"><V2Inline justify="between"><h3 class="v2-section-heading">Incremental sync</h3><V2Badge tone="ok" text="Enabled"/></V2Inline><label class="v2-check-row"><input type="checkbox" checked>Enabled</label><V2Field label="Cron" value="*/15 * * * *"/><V2Inline gap="sm" wrap={true}><button class="v2-button">15 min</button><button class="v2-button">Hourly</button><button class="v2-button">Daily</button><button class="v2-button">Weekly</button></V2Inline><span class="v2-small v2-muted">Next run: 13:15</span><button class="v2-button v2-button-primary">Save schedule</button></V2Stack></V2Card>
      <V2Card><V2Stack gap="sm"><V2Inline justify="between"><h3 class="v2-section-heading">Global sync</h3><V2Badge text="Disabled"/></V2Inline><label class="v2-check-row"><input type="checkbox">Enabled</label><V2Field label="Cron" value="0 0 * * 0"/><V2Inline gap="sm" wrap={true}><button class="v2-button">15 min</button><button class="v2-button">Hourly</button><button class="v2-button">Daily</button><button class="v2-button">Weekly</button></V2Inline><span class="v2-small v2-muted">Next run: disabled</span><button class="v2-button v2-button-primary">Save schedule</button></V2Stack></V2Card>
    </div>
  </V2Zone>

  {#snippet inspector()}<V2Zone label="Inspector"><V2Section title="Validation"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Batch size valid"/><V2Badge tone="ok" text="Delay valid"/><span class="v2-small v2-muted">Invalid values disable the relevant save action.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>

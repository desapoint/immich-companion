<script lang="ts">
  import { onMount } from 'svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { readV2Density, V2_DENSITY_EVENT, writeV2Density, type V2Density } from '../state/density';

  type SettingsTab = 'General' | 'Duplicates' | 'Sync';
  let tab = $state<SettingsTab>('General');
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

<V2PageLayout title="Settings" description="Configure interface behavior, duplicate defaults and synchronization schedules.">
  {#snippet tabs()}<V2Tabs items={['General','Duplicates','Sync']} active={tab} ariaLabel="Settings sections" onselect={(value) => tab = value as SettingsTab}/>{/snippet}

  <V2Zone>
    <V2Toolbar sticky={false}><b>{tab}</b></V2Toolbar>

    {#if tab === 'General'}
      <div class="v2-setting-grid">
        <V2Card title="Interface density">{#snippet actions()}<V2Badge tone="ok" text="Local preference"/>{/snippet}<V2Stack gap="sm"><span class="v2-small v2-muted">Controls spacing, table row height, card padding and grid thumbnail density across collection interfaces.</span><V2Segmented items={['Standard','Condensed']} active={density === 'standard' ? 'Standard' : 'Condensed'} onselect={(value) => setDensity(value === 'Standard' ? 'standard' : 'condensed')} ariaLabel="Interface density" /></V2Stack></V2Card>
        <V2Card title="Background batch load">{#snippet actions()}<V2Badge tone="ok" text="Saved"/>{/snippet}<V2Stack gap="sm"><V2Field label="Assets per batch · 1–500" type="number" value="100"/><V2Field label="Minimum delay (seconds) · 0–60" type="number" value="1"/><V2Button variant="primary">Save load settings</V2Button></V2Stack></V2Card>
      </div>
    {:else if tab === 'Duplicates'}
      <div class="v2-setting-grid">
        <V2Card title="Duplicate automatic handling"><V2Stack gap="sm"><SelectField id="settings-exact-action" label="Exact-file action" options={['Resolve exact files','Keep all exact copies','Stack exact copies','Always review']}/><SelectField id="settings-primary-rule" label="Primary rule" options={['Prefer Immich uploads','Prefer external files','Most recently uploaded','First Immich result']}/><V2Checkbox label="Enable automatic recommendations" checked={true}/><V2Checkbox label="Analyze candidate files automatically" checked={true}/><V2Button variant="primary">Save duplicate policy</V2Button></V2Stack></V2Card>
        <V2Card title="Review safeguards"><V2Stack gap="sm"><V2Checkbox label="Require review before deletion" checked={true}/><V2Checkbox label="Keep similarity as evidence only" checked={true}/><span class="v2-small v2-muted">Demo-only settings until duplicate policy integration is connected.</span></V2Stack></V2Card>
      </div>
    {:else}
      <div class="v2-setting-grid">
        <V2Card title="Incremental sync">{#snippet actions()}<V2Badge tone="ok" text="Enabled"/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled" checked={true}/><V2Field label="Cron" value="*/15 * * * *"/><V2Inline gap="sm" wrap={true}>{#each ['15 min','Hourly','Daily','Weekly'] as preset}<V2Button>{preset}</V2Button>{/each}</V2Inline><span class="v2-small v2-muted">Next run: 13:15</span><V2Button variant="primary">Save schedule</V2Button></V2Stack></V2Card>
        <V2Card title="Global sync">{#snippet actions()}<V2Badge text="Disabled"/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled"/><V2Field label="Cron" value="0 0 * * 0"/><V2Inline gap="sm" wrap={true}>{#each ['15 min','Hourly','Daily','Weekly'] as preset}<V2Button>{preset}</V2Button>{/each}</V2Inline><span class="v2-small v2-muted">Next run: disabled</span><V2Button variant="primary">Save schedule</V2Button></V2Stack></V2Card>
      </div>
    {/if}
  </V2Zone>

  {#snippet inspector()}
    <V2Zone>
      {#if tab === 'General'}
        <V2Section title="Validation"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Batch size valid"/><V2Badge tone="ok" text="Delay valid"/><span class="v2-small v2-muted">Invalid values disable the relevant save action.</span></V2Stack></V2Card></V2Section>
      {:else if tab === 'Duplicates'}
        <V2Section title="Policy status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Review safeguards enabled"/><span class="v2-small v2-muted">Current controls are demo state only.</span></V2Stack></V2Card></V2Section>
      {:else}
        <V2Section title="Schedule status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Incremental enabled"/><V2Badge text="Global disabled"/><span class="v2-small v2-muted">Schedules are displayed as local demo state until integration.</span></V2Stack></V2Card></V2Section>
      {/if}
    </V2Zone>
  {/snippet}
</V2PageLayout>

<script lang="ts">
  import { onMount } from 'svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2CronField from '../components/V2CronField.svelte';
  import V2Field from '../components/V2Field.svelte';
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
  let incrementalCron = $state('*/15 * * * *');
  let globalCron = $state('0 0 * * 0');
  let incrementalEnabled = $state(true);
  let globalEnabled = $state(false);
  let incrementalCronValid = $state(true);
  let globalCronValid = $state(true);

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
      </div>
    {:else if tab === 'Duplicates'}
      <div class="v2-setting-grid">
        <V2Card title="Automatic handling policy"><V2Stack gap="sm"><SelectField id="settings-exact-action" label="Exact-file action" options={['Resolve exact files','Keep all exact copies','Stack exact copies','Always review']}/><SelectField id="settings-primary-rule" label="Primary rule" options={['Prefer Immich uploads','Prefer external files','Most recently uploaded','First Immich result']}/><V2Field label="Similarity threshold (%)" type="number" value="82"/><V2Checkbox label="Enable automatic recommendations" checked={true}/><V2Checkbox label="Preselect safe groups" checked={true}/><V2Checkbox label="Analyze candidate files automatically" checked={true}/><V2Checkbox label="Verify upload streams too" checked={true}/><V2Button variant="primary">Save duplicate policy</V2Button></V2Stack></V2Card>
        <V2Card title="External libraries"><V2Stack gap="sm"><span class="v2-small v2-muted">No selected library means all external libraries. Demo options stand in for the live Immich library list.</span><V2Checkbox label="Family Archive · 1,842 assets"/><V2Checkbox label="Imported Photos · 621 assets"/><V2Checkbox label="Scanned Media · 204 assets"/></V2Stack></V2Card>
      </div>
    {:else}
      <div class="v2-setting-grid">
        <V2Card title="Background batch load">{#snippet actions()}<V2Badge tone="ok" text="Demo values"/>{/snippet}<V2Stack gap="sm"><span class="v2-small v2-muted">Global sync and large asset work rest after each batch. Tag association concurrency also influences the adaptive tag matching strategy.</span><V2Field label="Assets per batch · 1–500" type="number" value="50"/><V2Field label="Minimum delay (seconds) · 0–60" type="number" value="0.2"/><V2Field label="Tag association concurrency · 1–32" type="number" value="4"/><V2Button variant="primary">Save load settings</V2Button></V2Stack></V2Card>
        <V2Card title="Incremental sync">{#snippet actions()}<V2Badge tone={incrementalEnabled ? 'ok' : 'default'} text={incrementalEnabled ? 'Enabled' : 'Disabled'}/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled" checked={incrementalEnabled} onchange={(checked) => incrementalEnabled = checked}/><V2CronField id="settings-incremental-cron" label="Incremental schedule" enabled={incrementalEnabled} bind:value={incrementalCron} onvaliditychange={(valid) => incrementalCronValid = valid}/><V2Button variant="primary" disabled={!incrementalCronValid}>Save schedule</V2Button></V2Stack></V2Card>
        <V2Card title="Global sync">{#snippet actions()}<V2Badge tone={globalEnabled ? 'ok' : 'default'} text={globalEnabled ? 'Enabled' : 'Disabled'}/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled" checked={globalEnabled} onchange={(checked) => globalEnabled = checked}/><V2CronField id="settings-global-cron" label="Global schedule" enabled={globalEnabled} bind:value={globalCron} onvaliditychange={(valid) => globalCronValid = valid}/><V2Button variant="primary" disabled={!globalCronValid}>Save schedule</V2Button></V2Stack></V2Card>
      </div>
    {/if}
  </V2Zone>

  {#snippet inspector()}
    <V2Zone>
      {#if tab === 'General'}
        <V2Section title="Preference status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Density preference active"/><span class="v2-small v2-muted">Interface preferences are stored locally.</span></V2Stack></V2Card></V2Section>
      {:else if tab === 'Duplicates'}
        <V2Section title="Policy status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Live option coverage complete"/><span class="v2-small v2-muted">Duplicate controls are visual demo state only. No live policy is loaded or saved here yet.</span></V2Stack></V2Card></V2Section>
      {:else}
        <V2Section title="Sync status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Batch size valid"/><V2Badge tone="ok" text="Delay valid"/><V2Badge tone="ok" text="Tag concurrency valid"/><V2Badge tone={incrementalCronValid ? 'ok' : 'bad'} text={incrementalCronValid ? 'Incremental cron valid' : 'Incremental cron invalid'}/><V2Badge tone={globalCronValid ? 'ok' : 'bad'} text={globalCronValid ? 'Global cron valid' : 'Global cron invalid'}/><span class="v2-small v2-muted">Runtime and schedule controls mirror the live settings surface but remain demo-only until integration.</span></V2Stack></V2Card></V2Section>
      {/if}
    </V2Zone>
  {/snippet}
</V2PageLayout>

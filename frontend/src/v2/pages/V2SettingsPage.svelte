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
  type SyncProfile = 'Low impact' | 'Balanced' | 'Fast' | 'Custom';
  type DemoRunState = 'idle' | 'running' | 'cancelled';
  type DemoRunMode = 'Global' | 'Incremental';

  type SyncTuning = {
    assetPageSize: number;
    assetBatchSize: number;
    assetPrefetchPages: number;
    assetWriteConcurrency: number;
    assetPageDelay: number;
    catalogBatchSize: number;
    catalogWriteConcurrency: number;
    catalogBatchDelay: number;
    stackBatchSize: number;
    stackWriteConcurrency: number;
    stackBatchDelay: number;
    albumRelationshipPageSize: number;
    albumRelationshipConcurrency: number;
    albumRelationshipDelay: number;
    tagRelationshipPageSize: number;
    tagRelationshipConcurrency: number;
    tagRelationshipDelay: number;
    maxImmichApiConcurrency: number;
    retryAttempts: number;
    retryBackoffSeconds: number;
  };

  const profileValues: Record<Exclude<SyncProfile, 'Custom'>, SyncTuning> = {
    'Low impact': {
      assetPageSize: 500,
      assetBatchSize: 100,
      assetPrefetchPages: 0,
      assetWriteConcurrency: 1,
      assetPageDelay: 0.5,
      catalogBatchSize: 100,
      catalogWriteConcurrency: 1,
      catalogBatchDelay: 0.2,
      stackBatchSize: 100,
      stackWriteConcurrency: 1,
      stackBatchDelay: 0.2,
      albumRelationshipPageSize: 500,
      albumRelationshipConcurrency: 1,
      albumRelationshipDelay: 0.5,
      tagRelationshipPageSize: 500,
      tagRelationshipConcurrency: 2,
      tagRelationshipDelay: 0.5,
      maxImmichApiConcurrency: 2,
      retryAttempts: 5,
      retryBackoffSeconds: 1,
    },
    Balanced: {
      assetPageSize: 1000,
      assetBatchSize: 250,
      assetPrefetchPages: 1,
      assetWriteConcurrency: 1,
      assetPageDelay: 0.2,
      catalogBatchSize: 250,
      catalogWriteConcurrency: 1,
      catalogBatchDelay: 0,
      stackBatchSize: 250,
      stackWriteConcurrency: 1,
      stackBatchDelay: 0,
      albumRelationshipPageSize: 1000,
      albumRelationshipConcurrency: 2,
      albumRelationshipDelay: 0.2,
      tagRelationshipPageSize: 1000,
      tagRelationshipConcurrency: 4,
      tagRelationshipDelay: 0.2,
      maxImmichApiConcurrency: 4,
      retryAttempts: 5,
      retryBackoffSeconds: 1,
    },
    Fast: {
      assetPageSize: 1000,
      assetBatchSize: 500,
      assetPrefetchPages: 2,
      assetWriteConcurrency: 2,
      assetPageDelay: 0,
      catalogBatchSize: 500,
      catalogWriteConcurrency: 2,
      catalogBatchDelay: 0,
      stackBatchSize: 500,
      stackWriteConcurrency: 2,
      stackBatchDelay: 0,
      albumRelationshipPageSize: 1000,
      albumRelationshipConcurrency: 4,
      albumRelationshipDelay: 0,
      tagRelationshipPageSize: 1000,
      tagRelationshipConcurrency: 8,
      tagRelationshipDelay: 0,
      maxImmichApiConcurrency: 8,
      retryAttempts: 5,
      retryBackoffSeconds: 1,
    },
  };

  let tab = $state<SettingsTab>('General');
  let density = $state<V2Density>('standard');
  let syncProfile = $state<SyncProfile>('Balanced');
  let customTuning = $state<SyncTuning>({ ...profileValues.Balanced });
  let demoRunState = $state<DemoRunState>('running');
  let demoRunMode = $state<DemoRunMode>('Global');
  let incrementalCron = $state('*/15 * * * *');
  let globalCron = $state('0 0 * * 0');
  let incrementalEnabled = $state(true);
  let globalEnabled = $state(false);
  let incrementalCronValid = $state(true);
  let globalCronValid = $state(true);

  const activeTuning = $derived(syncProfile === 'Custom' ? customTuning : profileValues[syncProfile]);

  const demoPhases = [
    { name: 'Catalogs', detail: '841 albums · 2,194 tags', state: 'complete' },
    { name: 'Assets', detail: '128,422 / 240,031 assets', state: 'complete' },
    { name: 'Stacks', detail: '3,821 stacks · 9,412 members', state: 'complete' },
    { name: 'Album relationships', detail: '317 / 841 albums', state: 'running' },
    { name: 'Tag relationships', detail: 'Waiting for album relationships', state: 'waiting' },
    { name: 'Finalization', detail: 'Generation validation and cleanup', state: 'waiting' },
  ] as const;

  function setDensity(next: V2Density): void {
    density = next;
    writeV2Density(next);
  }

  function setProfile(next: SyncProfile): void {
    if (next === 'Custom' && syncProfile !== 'Custom') {
      customTuning = { ...activeTuning };
    }
    syncProfile = next;
  }

  function updateCustom<K extends keyof SyncTuning>(key: K, value: string): void {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return;
    customTuning = { ...customTuning, [key]: parsed };
  }

  function startDemoRun(mode: DemoRunMode): void {
    demoRunMode = mode;
    demoRunState = 'running';
  }

  function cancelDemoRun(): void {
    demoRunState = 'cancelled';
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
      <div class="sync-demo-banner">
        <div><strong>Sync Control Center</strong><span class="v2-small v2-muted">Interactive V2 mockup. Values and actions below are demo state only and do not call the live sync backend.</span></div>
        <V2Badge tone="default" text="Demo only"/>
      </div>

      <div class="sync-control-grid sync-control-grid--hero">
        <V2Card title="Current synchronization">
          {#snippet actions()}<V2Badge tone={demoRunState === 'running' ? 'ok' : 'default'} text={demoRunState === 'running' ? `${demoRunMode} sync running` : demoRunState === 'cancelled' ? 'Demo cancelled' : 'Idle'}/>{/snippet}
          <V2Stack gap="sm">
            <div class="sync-run-summary"><div><span class="v2-small v2-muted">Generation</span><strong>#184</strong></div><div><span class="v2-small v2-muted">Elapsed</span><strong>18m 42s</strong></div><div><span class="v2-small v2-muted">Assets</span><strong>128,422 / 240,031</strong></div><div><span class="v2-small v2-muted">Progress</span><strong>53.5%</strong></div></div>
            <div class="sync-progress" aria-label="Demo sync progress"><span style="width: 53.5%"></span></div>
            <div class="sync-run-actions"><V2Button variant="primary" onclick={() => startDemoRun('Global')}>Start global</V2Button><V2Button onclick={() => startDemoRun('Incremental')}>Start incremental</V2Button><V2Button disabled={demoRunState !== 'running'} onclick={cancelDemoRun}>Cancel demo</V2Button></div>
          </V2Stack>
        </V2Card>

        <V2Card title="Run counters"><div class="sync-counter-grid"><div><strong>322</strong><span>Created</span></div><div><strong>4,218</strong><span>Updated</span></div><div><strong>123,882</strong><span>Unchanged</span></div><div><strong>3,821</strong><span>Stacks</span></div><div><strong>841</strong><span>Albums</span></div><div><strong>2,194</strong><span>Tags</span></div></div></V2Card>
      </div>

      <V2Card title="Synchronization phases">
        {#snippet actions()}<V2Badge tone="ok" text="Checkpointed demo"/>{/snippet}
        <div class="sync-phase-list">{#each demoPhases as phase, index}<div class:sync-phase--active={phase.state === 'running'} class="sync-phase-row"><div class="sync-phase-index">{index + 1}</div><div class="sync-phase-copy"><strong>{phase.name}</strong><span class="v2-small v2-muted">{phase.detail}</span></div><V2Badge tone={phase.state === 'complete' ? 'ok' : 'default'} text={phase.state === 'complete' ? 'Complete' : phase.state === 'running' ? 'Running' : 'Waiting'}/></div>{/each}</div>
      </V2Card>

      <V2Section title="Performance profile">
        <V2Card title="Sync intensity preset">
          {#snippet actions()}<V2Badge tone="default" text="Mock profile"/>{/snippet}
          <V2Stack gap="sm">
            <span class="v2-small v2-muted">Choose a preset to apply a complete set of demo values. Detailed controls are hidden for presets; select Custom to edit every value directly. Switching from a preset to Custom copies that preset's current values into the editable fields.</span>
            <V2Segmented items={['Low impact','Balanced','Fast','Custom']} active={syncProfile} onselect={(value) => setProfile(value as SyncProfile)} ariaLabel="Sync performance profile" />
            <div class="sync-profile-summary"><div><span>Immich server pressure</span><strong>{syncProfile === 'Low impact' ? 'Low' : syncProfile === 'Fast' ? 'High' : syncProfile === 'Custom' ? 'Custom values' : 'Medium'}</strong></div><div><span>Companion / PostgreSQL pressure</span><strong>{syncProfile === 'Fast' ? 'High' : syncProfile === 'Low impact' ? 'Low' : syncProfile === 'Custom' ? 'Custom values' : 'Medium'}</strong></div><div><span>Expected full-sync duration</span><strong>{syncProfile === 'Fast' ? 'Shortest' : syncProfile === 'Low impact' ? 'Longest' : syncProfile === 'Custom' ? 'Depends on values' : 'Balanced'}</strong></div></div>
          </V2Stack>
        </V2Card>

        <V2Card title={`${syncProfile} preset values`}>
          <V2Stack gap="sm">
            <span class="v2-small v2-muted">These are the values the selected profile would apply. A global or incremental sync job still remains serialized to one active sync task; concurrency below refers only to bounded work inside that single sync.</span>
            <div class="sync-value-grid">
              <div><span>Asset API page size</span><strong>{activeTuning.assetPageSize}</strong><small>Assets requested from Immich per asset-list page.</small></div>
              <div><span>Asset DB batch size</span><strong>{activeTuning.assetBatchSize}</strong><small>Assets written to Companion/PostgreSQL per persistence batch.</small></div>
              <div><span>Asset prefetch pages</span><strong>{activeTuning.assetPrefetchPages}</strong><small>Future Immich asset pages buffered ahead while current data is persisted.</small></div>
              <div><span>Album scan concurrency</span><strong>{activeTuning.albumRelationshipConcurrency}</strong><small>Album-membership scans allowed in parallel inside the one sync job.</small></div>
              <div><span>Tag scan concurrency</span><strong>{activeTuning.tagRelationshipConcurrency}</strong><small>Tag-association scans allowed in parallel inside the one sync job.</small></div>
              <div><span>Max concurrent Immich API requests</span><strong>{activeTuning.maxImmichApiConcurrency}</strong><small>Shared ceiling for simultaneous requests from all phases of the active sync.</small></div>
            </div>
          </V2Stack>
        </V2Card>
      </V2Section>

      {#if syncProfile === 'Custom'}
        <V2Section title="Custom per-phase tuning">
          <div class="sync-custom-note"><strong>Custom mode</strong><span class="v2-small v2-muted">Every field below controls a different part of the single active sync job. API page sizes and scan concurrency mainly affect Immich. Database batch sizes and write concurrency mainly affect Companion/PostgreSQL.</span></div>
          <div class="sync-control-grid">
            <V2Card title="Asset listing and persistence">
              {#snippet actions()}<V2Badge tone="default" text="Immich + Companion DB"/>{/snippet}
              <V2Stack gap="sm">
                <span class="v2-small v2-muted">Controls the main asset traversal. Immich page size determines each API response; DB batch size determines how that page is split for local writes.</span>
                <V2Field label="Immich asset API page size · assets returned per request · 25–1000" type="number" min="25" max="1000" value={customTuning.assetPageSize} onchange={(v) => updateCustom('assetPageSize', v)}/>
                <V2Field label="Companion asset DB batch size · assets persisted per transaction batch · 1–500" type="number" min="1" max="500" value={customTuning.assetBatchSize} onchange={(v) => updateCustom('assetBatchSize', v)}/>
                <V2Field label="Asset prefetch depth · future Immich pages buffered ahead · 0–4" type="number" min="0" max="4" value={customTuning.assetPrefetchPages} onchange={(v) => updateCustom('assetPrefetchPages', v)}/>
                <V2Field label="Asset DB write concurrency · persistence batches written in parallel · 1–8" type="number" min="1" max="8" value={customTuning.assetWriteConcurrency} onchange={(v) => updateCustom('assetWriteConcurrency', v)}/>
                <V2Field label="Asset API inter-page delay · seconds before requesting the next Immich asset page" type="number" min="0" step="0.1" value={customTuning.assetPageDelay} onchange={(v) => updateCustom('assetPageDelay', v)}/>
              </V2Stack>
            </V2Card>

            <V2Card title="Album and tag catalogs">
              {#snippet actions()}<V2Badge tone="default" text="Mostly Companion DB"/>{/snippet}
              <V2Stack gap="sm">
                <span class="v2-small v2-muted">Controls persistence of the album and tag catalog lists after they are fetched from Immich.</span>
                <V2Field label="Catalog DB batch size · albums/tags persisted per local batch · 1–500" type="number" min="1" max="500" value={customTuning.catalogBatchSize} onchange={(v) => updateCustom('catalogBatchSize', v)}/>
                <V2Field label="Catalog DB write concurrency · catalog persistence batches in parallel · 1–4" type="number" min="1" max="4" value={customTuning.catalogWriteConcurrency} onchange={(v) => updateCustom('catalogWriteConcurrency', v)}/>
                <V2Field label="Catalog DB inter-batch delay · seconds between local catalog batches" type="number" min="0" step="0.1" value={customTuning.catalogBatchDelay} onchange={(v) => updateCustom('catalogBatchDelay', v)}/>
              </V2Stack>
            </V2Card>

            <V2Card title="Stack relationships">
              {#snippet actions()}<V2Badge tone="default" text="Immich + Companion DB"/>{/snippet}
              <V2Stack gap="sm">
                <span class="v2-small v2-muted">Controls how stack records and stack-member relationships are grouped and written locally.</span>
                <V2Field label="Stack DB batch size · stacks applied per local batch · 1–500" type="number" min="1" max="500" value={customTuning.stackBatchSize} onchange={(v) => updateCustom('stackBatchSize', v)}/>
                <V2Field label="Stack DB write concurrency · stack batches persisted in parallel · 1–4" type="number" min="1" max="4" value={customTuning.stackWriteConcurrency} onchange={(v) => updateCustom('stackWriteConcurrency', v)}/>
                <V2Field label="Stack inter-batch delay · seconds between stack batches" type="number" min="0" step="0.1" value={customTuning.stackBatchDelay} onchange={(v) => updateCustom('stackBatchDelay', v)}/>
              </V2Stack>
            </V2Card>

            <V2Card title="Album membership relationships">
              {#snippet actions()}<V2Badge tone="default" text="Immich API heavy"/>{/snippet}
              <V2Stack gap="sm">
                <span class="v2-small v2-muted">Controls requests that discover which assets belong to each album. This is separate from the album catalog itself.</span>
                <V2Field label="Album-membership API page size · asset IDs returned per Immich album request · 25–1000" type="number" min="25" max="1000" value={customTuning.albumRelationshipPageSize} onchange={(v) => updateCustom('albumRelationshipPageSize', v)}/>
                <V2Field label="Album scan concurrency · albums scanned in parallel inside one sync job · 1–8" type="number" min="1" max="8" value={customTuning.albumRelationshipConcurrency} onchange={(v) => updateCustom('albumRelationshipConcurrency', v)}/>
                <V2Field label="Album API inter-page delay · seconds between membership pages for an album" type="number" min="0" step="0.1" value={customTuning.albumRelationshipDelay} onchange={(v) => updateCustom('albumRelationshipDelay', v)}/>
              </V2Stack>
            </V2Card>

            <V2Card title="Tag membership relationships">
              {#snippet actions()}<V2Badge tone="default" text="Immich API heavy"/>{/snippet}
              <V2Stack gap="sm">
                <span class="v2-small v2-muted">Controls requests that reconcile which assets have each tag. This is separate from the tag catalog list.</span>
                <V2Field label="Tag-membership API page size · asset IDs returned per Immich tag request · 25–1000" type="number" min="25" max="1000" value={customTuning.tagRelationshipPageSize} onchange={(v) => updateCustom('tagRelationshipPageSize', v)}/>
                <V2Field label="Tag scan concurrency · tags reconciled in parallel inside one sync job · 1–32" type="number" min="1" max="32" value={customTuning.tagRelationshipConcurrency} onchange={(v) => updateCustom('tagRelationshipConcurrency', v)}/>
                <V2Field label="Tag API inter-page delay · seconds between membership pages for a tag" type="number" min="0" step="0.1" value={customTuning.tagRelationshipDelay} onchange={(v) => updateCustom('tagRelationshipDelay', v)}/>
              </V2Stack>
            </V2Card>

            <V2Card title="Global sync safety limits">
              {#snippet actions()}<V2Badge tone="ok" text="Single sync job preserved"/>{/snippet}
              <V2Stack gap="sm">
                <span class="v2-small v2-muted">The global/incremental sync task concurrency stays locked to one. The editable API ceiling below only limits simultaneous Immich requests made by phases inside that one active sync.</span>
                <div class="sync-locked-row"><span><strong>Maximum concurrent sync jobs</strong><small>Prevents full and incremental global sync jobs from overlapping.</small></span><strong>1 🔒</strong></div>
                <V2Field label="Maximum concurrent Immich API requests inside the active sync · shared phase ceiling · 1–32" type="number" min="1" max="32" value={customTuning.maxImmichApiConcurrency} onchange={(v) => updateCustom('maxImmichApiConcurrency', v)}/>
                <V2Field label="Sync task retry attempts · maximum attempts before the demo run is considered failed · 1–10" type="number" min="1" max="10" value={customTuning.retryAttempts} onchange={(v) => updateCustom('retryAttempts', v)}/>
                <V2Field label="Retry backoff base · initial delay in seconds used when retrying failed sync work" type="number" min="0" step="0.1" value={customTuning.retryBackoffSeconds} onchange={(v) => updateCustom('retryBackoffSeconds', v)}/>
              </V2Stack>
            </V2Card>
          </div>

          <div class="sync-save-row"><span class="v2-small v2-muted">Demo values only. Saving does not persist or modify the current backend runtime configuration.</span><V2Button variant="primary">Save custom demo settings</V2Button></div>
        </V2Section>
      {/if}

      <V2Section title="Schedules">
        <div class="sync-control-grid">
          <V2Card title="Incremental sync schedule">{#snippet actions()}<V2Badge tone={incrementalEnabled ? 'ok' : 'default'} text={incrementalEnabled ? 'Enabled' : 'Disabled'}/>{/snippet}<V2Stack gap="sm"><span class="v2-small v2-muted">Controls when the lightweight delta sync would run. It does not allow an incremental sync to overlap an already-running global sync.</span><V2Checkbox label="Enable incremental sync schedule" checked={incrementalEnabled} onchange={(checked) => incrementalEnabled = checked}/><V2CronField id="settings-incremental-cron" label="Incremental sync cron expression" enabled={incrementalEnabled} bind:value={incrementalCron} onvaliditychange={(valid) => incrementalCronValid = valid}/><V2Button variant="primary" disabled={!incrementalCronValid}>Save demo schedule</V2Button></V2Stack></V2Card>
          <V2Card title="Global full-sync schedule">{#snippet actions()}<V2Badge tone={globalEnabled ? 'ok' : 'default'} text={globalEnabled ? 'Enabled' : 'Disabled'}/>{/snippet}<V2Stack gap="sm"><span class="v2-small v2-muted">Controls when the authoritative full-library synchronization would run. Only one global/incremental sync job is intended to execute at a time.</span><V2Checkbox label="Enable global full-sync schedule" checked={globalEnabled} onchange={(checked) => globalEnabled = checked}/><V2CronField id="settings-global-cron" label="Global full-sync cron expression" enabled={globalEnabled} bind:value={globalCron} onvaliditychange={(valid) => globalCronValid = valid}/><V2Button variant="primary" disabled={!globalCronValid}>Save demo schedule</V2Button></V2Stack></V2Card>
        </div>
      </V2Section>
    {/if}
  </V2Zone>

  {#snippet inspector()}
    <V2Zone>
      {#if tab === 'General'}
        <V2Section title="Preference status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Density preference active"/><span class="v2-small v2-muted">Interface preferences are stored locally.</span></V2Stack></V2Card></V2Section>
      {:else if tab === 'Duplicates'}
        <V2Section title="Policy status"><V2Card><V2Stack gap="sm"><V2Badge tone="ok" text="Live option coverage complete"/><span class="v2-small v2-muted">Duplicate controls are visual demo state only. No live policy is loaded or saved here yet.</span></V2Stack></V2Card></V2Section>
      {:else}
        <V2Section title="Sync status"><V2Card><V2Stack gap="sm"><V2Badge tone="default" text="Interface-only demo"/><V2Badge tone="ok" text={`${syncProfile} profile selected`}/><V2Badge tone="ok" text="Concurrent sync jobs locked to 1"/><V2Badge tone={incrementalCronValid ? 'ok' : 'bad'} text={incrementalCronValid ? 'Incremental cron valid' : 'Incremental cron invalid'}/><V2Badge tone={globalCronValid ? 'ok' : 'bad'} text={globalCronValid ? 'Global cron valid' : 'Global cron invalid'}/><span class="v2-small v2-muted">The control center intentionally does not load, start, cancel, or save real synchronization yet. It demonstrates the intended V2 surface and state hierarchy only.</span></V2Stack></V2Card></V2Section>
      {/if}
    </V2Zone>
  {/snippet}
</V2PageLayout>

<style>
  .sync-demo-banner,.sync-save-row,.sync-run-actions,.sync-phase-row,.sync-profile-summary > div,.sync-locked-row{display:flex;align-items:center}
  .sync-demo-banner{justify-content:space-between;gap:1rem;padding:.9rem 1rem;margin-bottom:1rem;border:1px solid var(--v2-border,rgba(127,127,127,.25));border-radius:.8rem;background:var(--v2-surface-subtle,rgba(127,127,127,.06))}
  .sync-demo-banner>div{display:grid;gap:.2rem}.sync-control-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.sync-control-grid--hero{margin-bottom:1rem}
  .sync-run-summary,.sync-counter-grid,.sync-profile-summary,.sync-value-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}
  .sync-run-summary>div,.sync-counter-grid>div,.sync-profile-summary>div,.sync-value-grid>div{display:grid;gap:.15rem;padding:.7rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}
  .sync-counter-grid>div strong{font-size:1.15rem}.sync-counter-grid>div span,.sync-profile-summary span,.sync-value-grid span{font-size:.78rem;opacity:.7}.sync-value-grid small{font-size:.72rem;opacity:.65;line-height:1.35}
  .sync-progress{height:.55rem;overflow:hidden;border-radius:999px;background:var(--v2-surface-subtle,rgba(127,127,127,.12))}.sync-progress>span{display:block;height:100%;border-radius:inherit;background:currentColor;opacity:.65}
  .sync-run-actions{flex-wrap:wrap;gap:.5rem}.sync-phase-list{display:grid;gap:.5rem}.sync-phase-row{gap:.75rem;padding:.65rem .75rem;border:1px solid var(--v2-border,rgba(127,127,127,.2));border-radius:.65rem}.sync-phase--active{background:var(--v2-surface-subtle,rgba(127,127,127,.06))}
  .sync-phase-index{display:grid;place-items:center;width:1.8rem;height:1.8rem;flex:0 0 auto;border:1px solid var(--v2-border,rgba(127,127,127,.28));border-radius:999px;font-size:.78rem;font-weight:700}.sync-phase-copy{display:grid;gap:.12rem;min-width:0;flex:1}
  .sync-profile-summary{grid-template-columns:repeat(3,minmax(0,1fr))}.sync-profile-summary>div{align-items:flex-start}.sync-custom-note{display:grid;gap:.2rem;margin-bottom:1rem;padding:.8rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem;background:var(--v2-surface-subtle,rgba(127,127,127,.05))}
  .sync-locked-row{justify-content:space-between;gap:1rem;padding:.75rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}.sync-locked-row>span{display:grid;gap:.15rem}.sync-locked-row small{font-size:.72rem;opacity:.65}
  .sync-save-row{justify-content:space-between;gap:1rem;margin-top:1rem}
  @media(max-width:900px){.sync-control-grid,.sync-profile-summary,.sync-value-grid{grid-template-columns:1fr}}
  @media(max-width:620px){.sync-demo-banner,.sync-save-row,.sync-phase-row,.sync-locked-row{align-items:flex-start}.sync-demo-banner,.sync-save-row{flex-direction:column}.sync-run-summary,.sync-counter-grid{grid-template-columns:1fr}}
</style>
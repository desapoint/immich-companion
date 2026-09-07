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

  let tab = $state<SettingsTab>('General');
  let density = $state<V2Density>('standard');
  let syncProfile = $state<SyncProfile>('Balanced');
  let demoRunState = $state<DemoRunState>('running');
  let demoRunMode = $state<DemoRunMode>('Global');
  let incrementalCron = $state('*/15 * * * *');
  let globalCron = $state('0 0 * * 0');
  let incrementalEnabled = $state(true);
  let globalEnabled = $state(false);
  let incrementalCronValid = $state(true);
  let globalCronValid = $state(true);

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
        <div>
          <strong>Sync Control Center</strong>
          <span class="v2-small v2-muted">Interactive V2 mockup. Values and actions below are demo state only and do not call the live sync backend.</span>
        </div>
        <V2Badge tone="default" text="Demo only"/>
      </div>

      <div class="sync-control-grid sync-control-grid--hero">
        <V2Card title="Current synchronization">
          {#snippet actions()}<V2Badge tone={demoRunState === 'running' ? 'ok' : 'default'} text={demoRunState === 'running' ? `${demoRunMode} sync running` : demoRunState === 'cancelled' ? 'Demo cancelled' : 'Idle'}/>{/snippet}
          <V2Stack gap="sm">
            <div class="sync-run-summary">
              <div>
                <span class="v2-small v2-muted">Generation</span>
                <strong>#184</strong>
              </div>
              <div>
                <span class="v2-small v2-muted">Elapsed</span>
                <strong>18m 42s</strong>
              </div>
              <div>
                <span class="v2-small v2-muted">Assets</span>
                <strong>128,422 / 240,031</strong>
              </div>
              <div>
                <span class="v2-small v2-muted">Progress</span>
                <strong>53.5%</strong>
              </div>
            </div>

            <div class="sync-progress" aria-label="Demo sync progress">
              <span style="width: 53.5%"></span>
            </div>

            <div class="sync-run-actions">
              <V2Button variant="primary" onclick={() => startDemoRun('Global')}>Start global</V2Button>
              <V2Button onclick={() => startDemoRun('Incremental')}>Start incremental</V2Button>
              <V2Button disabled={demoRunState !== 'running'} onclick={cancelDemoRun}>Cancel demo</V2Button>
            </div>
          </V2Stack>
        </V2Card>

        <V2Card title="Run counters">
          <div class="sync-counter-grid">
            <div><strong>322</strong><span>Created</span></div>
            <div><strong>4,218</strong><span>Updated</span></div>
            <div><strong>123,882</strong><span>Unchanged</span></div>
            <div><strong>3,821</strong><span>Stacks</span></div>
            <div><strong>841</strong><span>Albums</span></div>
            <div><strong>2,194</strong><span>Tags</span></div>
          </div>
        </V2Card>
      </div>

      <V2Card title="Synchronization phases">
        {#snippet actions()}<V2Badge tone="ok" text="Checkpointed demo"/>{/snippet}
        <div class="sync-phase-list">
          {#each demoPhases as phase, index}
            <div class:sync-phase--active={phase.state === 'running'} class="sync-phase-row">
              <div class="sync-phase-index">{index + 1}</div>
              <div class="sync-phase-copy">
                <strong>{phase.name}</strong>
                <span class="v2-small v2-muted">{phase.detail}</span>
              </div>
              <V2Badge
                tone={phase.state === 'complete' ? 'ok' : 'default'}
                text={phase.state === 'complete' ? 'Complete' : phase.state === 'running' ? 'Running' : 'Waiting'}
              />
            </div>
          {/each}
        </div>
      </V2Card>

      <V2Section title="Performance profile">
        <V2Card title="Sync intensity">
          {#snippet actions()}<V2Badge tone="default" text="Mock profile"/>{/snippet}
          <V2Stack gap="sm">
            <span class="v2-small v2-muted">Profiles group the detailed controls below. Custom exposes the intended per-phase tuning surface without changing live runtime settings.</span>
            <V2Segmented items={['Low impact','Balanced','Fast','Custom']} active={syncProfile} onselect={(value) => syncProfile = value as SyncProfile} ariaLabel="Sync performance profile" />
            <div class="sync-profile-summary">
              <div><span>Immich pressure</span><strong>{syncProfile === 'Low impact' ? 'Low' : syncProfile === 'Fast' ? 'High' : syncProfile === 'Custom' ? 'Custom' : 'Medium'}</strong></div>
              <div><span>Companion DB pressure</span><strong>{syncProfile === 'Fast' ? 'High' : syncProfile === 'Low impact' ? 'Low' : 'Medium'}</strong></div>
              <div><span>Expected duration</span><strong>{syncProfile === 'Fast' ? 'Shortest' : syncProfile === 'Low impact' ? 'Longest' : syncProfile === 'Custom' ? 'Depends on values' : 'Balanced'}</strong></div>
            </div>
          </V2Stack>
        </V2Card>
      </V2Section>

      <V2Section title="Per-phase tuning">
        <div class="sync-control-grid">
          <V2Card title="Assets">
            {#snippet actions()}<V2Badge tone="default" text="Immich + DB"/>{/snippet}
            <V2Stack gap="sm">
              <V2Field label="Immich page size · 25–1000" type="number" value="1000"/>
              <V2Field label="Database batch size · 1–500" type="number" value="250"/>
              <V2Field label="Prefetch pages · 0–4" type="number" value="2"/>
              <V2Field label="Write concurrency · 1–8" type="number" value="1"/>
              <V2Field label="Delay between pages (seconds)" type="number" value="0.2"/>
              <span class="v2-small v2-muted">Prefetch is intended to overlap Immich reads with Companion persistence while keeping the queue bounded.</span>
            </V2Stack>
          </V2Card>

          <V2Card title="Catalogs">
            {#snippet actions()}<V2Badge tone="default" text="Mostly DB"/>{/snippet}
            <V2Stack gap="sm">
              <V2Field label="Catalog batch size · 1–500" type="number" value="250"/>
              <V2Field label="Write concurrency · 1–4" type="number" value="1"/>
              <V2Field label="Delay between batches (seconds)" type="number" value="0"/>
              <span class="v2-small v2-muted">Album and tag catalogs remain separate work, with bounded persistence concurrency.</span>
            </V2Stack>
          </V2Card>

          <V2Card title="Stacks">
            {#snippet actions()}<V2Badge tone="default" text="Immich + DB"/>{/snippet}
            <V2Stack gap="sm">
              <V2Field label="Stack batch size · 1–500" type="number" value="250"/>
              <V2Field label="Write concurrency · 1–4" type="number" value="1"/>
              <V2Field label="Delay between batches (seconds)" type="number" value="0"/>
              <span class="v2-small v2-muted">Stack batches stay bounded so relationship writes cannot fan out without an explicit limit.</span>
            </V2Stack>
          </V2Card>

          <V2Card title="Album relationships">
            {#snippet actions()}<V2Badge tone="default" text="Immich heavy"/>{/snippet}
            <V2Stack gap="sm">
              <V2Field label="Relationship page size · 25–1000" type="number" value="1000"/>
              <V2Field label="Album concurrency · 1–8" type="number" value="2"/>
              <V2Field label="Delay between pages (seconds)" type="number" value="0.2"/>
              <span class="v2-small v2-muted">Concurrency represents how many album membership scans may be in flight at once.</span>
            </V2Stack>
          </V2Card>

          <V2Card title="Tag relationships">
            {#snippet actions()}<V2Badge tone="default" text="Immich heavy"/>{/snippet}
            <V2Stack gap="sm">
              <V2Field label="Relationship page size · 25–1000" type="number" value="1000"/>
              <V2Field label="Tag concurrency · 1–32" type="number" value="4"/>
              <V2Field label="Delay between pages (seconds)" type="number" value="0.2"/>
              <span class="v2-small v2-muted">Mirrors the existing tag association concept and keeps the speed-versus-host-load tradeoff visible.</span>
            </V2Stack>
          </V2Card>

          <V2Card title="Global safeguards">
            {#snippet actions()}<V2Badge tone="ok" text="Recommended"/>{/snippet}
            <V2Stack gap="sm">
              <V2Field label="Maximum Immich sync requests · 1–32" type="number" value="6"/>
              <V2Field label="Retry attempts · 1–10" type="number" value="5"/>
              <V2Field label="Retry backoff base (seconds)" type="number" value="1"/>
              <V2Checkbox label="Apply shared request ceiling across sync phases" checked={true}/>
              <span class="v2-small v2-muted">The shared ceiling is a proposed UI safeguard so per-phase concurrency cannot accidentally create unbounded aggregate Immich pressure.</span>
            </V2Stack>
          </V2Card>
        </div>

        <div class="sync-save-row">
          <span class="v2-small v2-muted">Demo values only. Saving does not persist or modify the current backend runtime configuration.</span>
          <V2Button variant="primary">Save demo performance settings</V2Button>
        </div>
      </V2Section>

      <V2Section title="Schedules">
        <div class="sync-control-grid">
          <V2Card title="Incremental sync">{#snippet actions()}<V2Badge tone={incrementalEnabled ? 'ok' : 'default'} text={incrementalEnabled ? 'Enabled' : 'Disabled'}/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled" checked={incrementalEnabled} onchange={(checked) => incrementalEnabled = checked}/><V2CronField id="settings-incremental-cron" label="Incremental schedule" enabled={incrementalEnabled} bind:value={incrementalCron} onvaliditychange={(valid) => incrementalCronValid = valid}/><V2Button variant="primary" disabled={!incrementalCronValid}>Save demo schedule</V2Button></V2Stack></V2Card>
          <V2Card title="Global sync">{#snippet actions()}<V2Badge tone={globalEnabled ? 'ok' : 'default'} text={globalEnabled ? 'Enabled' : 'Disabled'}/>{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enabled" checked={globalEnabled} onchange={(checked) => globalEnabled = checked}/><V2CronField id="settings-global-cron" label="Global schedule" enabled={globalEnabled} bind:value={globalCron} onvaliditychange={(valid) => globalCronValid = valid}/><V2Button variant="primary" disabled={!globalCronValid}>Save demo schedule</V2Button></V2Stack></V2Card>
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
        <V2Section title="Sync status">
          <V2Card>
            <V2Stack gap="sm">
              <V2Badge tone="default" text="Interface-only demo"/>
              <V2Badge tone="ok" text={`${syncProfile} profile selected`}/>
              <V2Badge tone={incrementalCronValid ? 'ok' : 'bad'} text={incrementalCronValid ? 'Incremental cron valid' : 'Incremental cron invalid'}/>
              <V2Badge tone={globalCronValid ? 'ok' : 'bad'} text={globalCronValid ? 'Global cron valid' : 'Global cron invalid'}/>
              <span class="v2-small v2-muted">The control center intentionally does not load, start, cancel, or save real synchronization yet. It demonstrates the intended V2 surface and state hierarchy only.</span>
            </V2Stack>
          </V2Card>
        </V2Section>
      {/if}
    </V2Zone>
  {/snippet}
</V2PageLayout>

<style>
  .sync-demo-banner,
  .sync-save-row,
  .sync-run-actions,
  .sync-phase-row,
  .sync-profile-summary > div {
    display: flex;
    align-items: center;
  }

  .sync-demo-banner {
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1rem;
    margin-bottom: 1rem;
    border: 1px solid var(--v2-border, rgba(127, 127, 127, 0.25));
    border-radius: 0.8rem;
    background: var(--v2-surface-subtle, rgba(127, 127, 127, 0.06));
  }

  .sync-demo-banner > div {
    display: grid;
    gap: 0.2rem;
  }

  .sync-control-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .sync-control-grid--hero {
    margin-bottom: 1rem;
  }

  .sync-run-summary,
  .sync-counter-grid,
  .sync-profile-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.65rem;
  }

  .sync-run-summary > div,
  .sync-counter-grid > div,
  .sync-profile-summary > div {
    display: grid;
    gap: 0.15rem;
    padding: 0.7rem;
    border: 1px solid var(--v2-border, rgba(127, 127, 127, 0.22));
    border-radius: 0.65rem;
  }

  .sync-counter-grid > div strong {
    font-size: 1.15rem;
  }

  .sync-counter-grid > div span,
  .sync-profile-summary span {
    font-size: 0.78rem;
    opacity: 0.7;
  }

  .sync-progress {
    height: 0.55rem;
    overflow: hidden;
    border-radius: 999px;
    background: var(--v2-surface-subtle, rgba(127, 127, 127, 0.12));
  }

  .sync-progress > span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: currentColor;
    opacity: 0.65;
  }

  .sync-run-actions {
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .sync-phase-list {
    display: grid;
    gap: 0.5rem;
  }

  .sync-phase-row {
    gap: 0.75rem;
    padding: 0.65rem 0.75rem;
    border: 1px solid var(--v2-border, rgba(127, 127, 127, 0.2));
    border-radius: 0.65rem;
  }

  .sync-phase--active {
    background: var(--v2-surface-subtle, rgba(127, 127, 127, 0.06));
  }

  .sync-phase-index {
    display: grid;
    place-items: center;
    width: 1.8rem;
    height: 1.8rem;
    flex: 0 0 auto;
    border: 1px solid var(--v2-border, rgba(127, 127, 127, 0.28));
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
  }

  .sync-phase-copy {
    display: grid;
    gap: 0.12rem;
    min-width: 0;
    flex: 1;
  }

  .sync-profile-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .sync-profile-summary > div {
    align-items: flex-start;
  }

  .sync-save-row {
    justify-content: space-between;
    gap: 1rem;
    margin-top: 1rem;
  }

  @media (max-width: 900px) {
    .sync-control-grid,
    .sync-profile-summary {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 620px) {
    .sync-demo-banner,
    .sync-save-row,
    .sync-phase-row {
      align-items: flex-start;
    }

    .sync-demo-banner,
    .sync-save-row {
      flex-direction: column;
    }

    .sync-run-summary,
    .sync-counter-grid {
      grid-template-columns: 1fr;
    }
  }
</style>

<script lang="ts">
  import { onMount } from 'svelte';
  import type { AssetSyncCoordinatorStatus, AssetSyncMode, AssetSyncRunStatus, AssetTaskStatus } from '../../features/assets/types/assets';
  import type { SyncRuntimeSettings, SyncSchedule } from '../../features/settings/types/settings';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2CronField from '../components/V2CronField.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Notice from '../components/V2Notice.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Progress from '../components/V2Progress.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import { readV2Density, V2_DENSITY_EVENT, writeV2Density, type V2Density } from '../state/density';

  type SettingsTab = 'General' | 'Duplicates' | 'Sync';

  let tab = $state<SettingsTab>('General');
  let density = $state<V2Density>('standard');
  let statusState = $state<AssetSyncCoordinatorStatus | null>(null);
  let runtime = $state<SyncRuntimeSettings | null>(null);
  let schedules = $state<SyncSchedule[]>([]);
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let active = true;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let taskSocket: WebSocket | null = null;

  const currentRun = $derived(statusState?.active ?? statusState?.pending ?? null);
  const fullSchedule = $derived(schedules.find((item) => item.name === 'asset-sync-full') ?? null);
  const incrementalSchedule = $derived(schedules.find((item) => item.name === 'asset-sync-incremental') ?? null);
  const progressKnown = $derived(
    currentRun?.progress.total != null && currentRun.progress.percent != null,
  );

  function message(value: unknown, fallback: string): string {
    return value instanceof Error ? value.message : fallback;
  }

  function setDensity(next: V2Density): void {
    density = next;
    writeV2Density(next);
  }

  async function refreshStatus(): Promise<void> {
    try {
      const next = await libraryData.sync.status();
      if (active) statusState = next;
    } catch (value) {
      if (active && !statusState) error = message(value, 'Could not load synchronization status.');
    }
  }

  function handleTaskUpdate(task: AssetTaskStatus): void {
    if (task.task_type === 'asset_sync') void refreshStatus();
  }

  function connectTaskUpdates(): void {
    if (!active || taskSocket) return;
    taskSocket = libraryData.sync.openUpdates(
      handleTaskUpdate,
      () => undefined,
      () => {
        taskSocket = null;
        if (!active) return;
        reconnectTimer = setTimeout(connectTaskUpdates, 2000);
      },
    );
  }

  async function loadLiveConfiguration(): Promise<void> {
    loading = true;
    error = null;
    try {
      const [nextStatus, nextRuntime, nextSchedules] = await Promise.all([
        libraryData.sync.status(),
        libraryData.sync.runtimeSettings(),
        libraryData.sync.schedules(),
      ]);
      if (!active) return;
      statusState = nextStatus;
      runtime = nextRuntime;
      schedules = nextSchedules;
    } catch (value) {
      if (active) error = message(value, 'Could not load live synchronization configuration.');
    } finally {
      if (active) loading = false;
    }
  }

  async function start(mode: AssetSyncMode): Promise<void> {
    busy = true;
    error = null;
    success = null;
    try {
      await libraryData.sync.start(mode);
      await refreshStatus();
      if (active) success = `${mode === 'full' ? 'Global' : 'Incremental'} synchronization submitted.`;
    } catch (value) {
      if (active) error = message(value, 'Could not start synchronization.');
    } finally {
      if (active) busy = false;
    }
  }

  async function cancelCurrent(): Promise<void> {
    const run = currentRun;
    if (!run) return;
    busy = true;
    error = null;
    success = null;
    try {
      await libraryData.sync.cancel(run.task_id ?? run.id);
      await refreshStatus();
      if (active) success = 'Cancellation requested.';
    } catch (value) {
      if (active) error = message(value, 'Could not cancel synchronization.');
    } finally {
      if (active) busy = false;
    }
  }

  async function saveRuntime(): Promise<void> {
    if (!runtime) return;
    busy = true;
    error = null;
    success = null;
    try {
      runtime = await libraryData.sync.saveRuntimeSettings(runtime);
      success = 'Synchronization runtime settings saved.';
    } catch (value) {
      error = message(value, 'Could not save synchronization runtime settings.');
    } finally {
      busy = false;
    }
  }

  function setRuntime<K extends keyof SyncRuntimeSettings>(key: K, raw: string): void {
    if (!runtime) return;
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    runtime = { ...runtime, [key]: value };
  }

  function updateSchedule(name: string, patch: Partial<Pick<SyncSchedule, 'enabled' | 'cron_expression'>>): void {
    schedules = schedules.map((item) => item.name === name ? { ...item, ...patch } : item);
  }

  async function persistSchedule(schedule: SyncSchedule | null): Promise<void> {
    if (!schedule || !schedule.cron_expression) return;
    busy = true;
    error = null;
    success = null;
    try {
      const saved = await libraryData.sync.saveSchedule(schedule.name, {
        enabled: schedule.enabled,
        cron_expression: schedule.cron_expression,
      });
      schedules = schedules.map((item) => item.name === saved.name ? saved : item);
      success = `${schedule.name === 'asset-sync-full' ? 'Global' : 'Incremental'} schedule saved.`;
    } catch (value) {
      error = message(value, 'Could not save synchronization schedule.');
    } finally {
      busy = false;
    }
  }

  function runLabel(run: AssetSyncRunStatus | null): string {
    if (!run) return 'Idle';
    if (run.status === 'queued') return 'Queued';
    if (run.status === 'retrying') return 'Retrying';
    if (run.status === 'recovering') return 'Recovering';
    return 'Running';
  }

  function formatNumber(value: number | null | undefined): string {
    return typeof value === 'number' ? value.toLocaleString() : '—';
  }

  onMount(() => {
    active = true;
    density = readV2Density();
    const onDensity = (event: Event) => density = (event as CustomEvent<V2Density>).detail;
    window.addEventListener(V2_DENSITY_EVENT, onDensity);
    void loadLiveConfiguration();
    connectTaskUpdates();
    pollTimer = setInterval(() => void refreshStatus(), 10000);
    return () => {
      active = false;
      window.removeEventListener(V2_DENSITY_EVENT, onDensity);
      if (pollTimer) clearInterval(pollTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      taskSocket?.close();
      taskSocket = null;
    };
  });
</script>

<V2PageLayout title="Settings" description="Configure interface behavior and live synchronization controls.">
  {#snippet tabs()}
    <V2Tabs items={['General', 'Duplicates', 'Sync']} active={tab} ariaLabel="Settings sections" onselect={(value) => tab = value as SettingsTab} />
  {/snippet}

  <V2Zone>
    <V2Toolbar sticky={false}><b>{tab}</b></V2Toolbar>

    {#if tab === 'General'}
      <div class="v2-setting-grid">
        <V2Card title="Interface density">
          {#snippet actions()}<V2Badge tone="ok" text="Saved locally" />{/snippet}
          <V2Stack gap="sm">
            <span class="v2-small v2-muted">Controls spacing, table row height, card padding and grid thumbnail density throughout V2.</span>
            <V2Segmented items={['Standard', 'Condensed']} active={density === 'standard' ? 'Standard' : 'Condensed'} onselect={(value) => setDensity(value === 'Standard' ? 'standard' : 'condensed')} ariaLabel="Interface density" />
            <span class="v2-small v2-muted">The preference is applied immediately and retained across pages and browser reloads.</span>
          </V2Stack>
        </V2Card>
      </div>
    {:else if tab === 'Duplicates'}
      <V2Card title="Implementation not done yet">
        {#snippet actions()}<V2Badge tone="warn" text="Live actions disabled" />{/snippet}
        <V2Notice tone="warning" title="This settings area is not live yet">
          Duplicate settings are intentionally disabled in V2 until their live integration is complete.
        </V2Notice>
      </V2Card>
    {:else if loading}
      <V2Notice>Loading live synchronization status and configuration…</V2Notice>
    {:else}
      <V2Stack gap="md">
        {#if error}<V2Notice tone="error" title="Synchronization request failed">{error}</V2Notice>{/if}
        {#if success}<V2Notice tone="success">{success}</V2Notice>{/if}

        <V2Card title="Current synchronization">
          {#snippet actions()}<V2Badge tone={currentRun ? 'ok' : 'default'} text={runLabel(currentRun)} />{/snippet}
          <V2Stack gap="sm">
            {#if currentRun}
              <div class="sync-run-summary">
                <div><span>Mode</span><strong>{currentRun.mode === 'full' ? 'Global' : 'Incremental'}</strong></div>
                <div><span>Generation</span><strong>#{currentRun.generation}</strong></div>
                <div><span>Phase</span><strong>{currentRun.progress.phase || currentRun.phase}</strong></div>
                <div><span>Processed</span><strong>{formatNumber(currentRun.progress.completed)} / {formatNumber(currentRun.progress.total)}</strong></div>
              </div>
              <V2Progress
                value={progressKnown ? currentRun.progress.percent ?? undefined : undefined}
                indeterminate={!progressKnown}
                label={`Synchronization ${currentRun.progress.phase || currentRun.phase} progress`}
              />
              <div class="v2-small v2-muted">
                {currentRun.progress.detail ?? (progressKnown ? `${formatNumber(currentRun.progress.completed)} of ${formatNumber(currentRun.progress.total)} processed` : 'Synchronization is running; total work is not known yet.')}
              </div>
            {:else}
              <V2Notice tone="info">No synchronization is currently active or queued.</V2Notice>
            {/if}
            <div class="sync-run-actions">
              <V2Button variant="primary" disabled={busy || Boolean(currentRun)} onclick={() => void start('full')}>Start global sync</V2Button>
              <V2Button disabled={busy || Boolean(currentRun)} onclick={() => void start('incremental')}>Start incremental sync</V2Button>
              <V2Button variant="danger" disabled={busy || !currentRun} onclick={() => void cancelCurrent()}>Cancel sync</V2Button>
              <V2Button disabled={busy} onclick={() => void refreshStatus()}>Refresh</V2Button>
            </div>
          </V2Stack>
        </V2Card>

        <V2Card title="Run counters">
          {#if currentRun}
            <div class="sync-counter-grid">
              {#each Object.entries(currentRun.counters) as [name, value] (name)}
                <div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>
              {/each}
            </div>
          {:else if statusState?.last_success}
            <div class="sync-counter-grid">
              {#each Object.entries(statusState.last_success.counters) as [name, value] (name)}
                <div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>
              {/each}
            </div>
          {:else}
            <span class="v2-small v2-muted">No completed synchronization counters are available yet.</span>
          {/if}
        </V2Card>

        <V2Section title="Live runtime configuration">
          <V2Card title="Synchronization load controls">
            {#snippet actions()}<V2Badge tone="ok" text="Live backend settings" />{/snippet}
            {#if runtime}
              <V2Stack gap="sm">
                <V2Field label="Full-sync persistence batch size" type="number" min="1" value={runtime.full_batch_size} onchange={(value) => setRuntime('full_batch_size', value)} />
                <V2Field label="Minimum full-sync batch delay (seconds)" type="number" min="0" step="0.1" value={runtime.full_min_batch_delay_seconds} onchange={(value) => setRuntime('full_min_batch_delay_seconds', value)} />
                <V2Field label="Tag association concurrency" type="number" min="1" max="32" value={runtime.tag_association_concurrency} onchange={(value) => setRuntime('tag_association_concurrency', value)} />
                <V2Notice tone="info" title="Only persisted controls are shown">
                  Page concurrency and the additional per-step controls from the earlier V2 mockup are hidden until their backend implementation is live. This screen does not pretend to save unsupported values.
                </V2Notice>
                <div><V2Button variant="primary" disabled={busy} onclick={() => void saveRuntime()}>Save runtime settings</V2Button></div>
              </V2Stack>
            {:else}
              <V2Notice tone="error">Runtime settings were not available.</V2Notice>
            {/if}
          </V2Card>
        </V2Section>

        <V2Section title="Schedules">
          <div class="sync-control-grid">
            {#if incrementalSchedule}
              <V2Card title="Incremental sync schedule">
                {#snippet actions()}<V2Badge tone={incrementalSchedule.enabled ? 'ok' : 'default'} text={incrementalSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}
                <V2Stack gap="sm">
                  <V2Checkbox label="Enable incremental sync schedule" checked={incrementalSchedule.enabled} onchange={(checked) => updateSchedule(incrementalSchedule.name, { enabled: checked })} />
                  <V2CronField id="settings-incremental-cron" label="Incremental synchronization" enabled={incrementalSchedule.enabled} value={incrementalSchedule.cron_expression ?? ''} onchange={(value) => updateSchedule(incrementalSchedule.name, { cron_expression: value })} />
                  <div><V2Button variant="primary" disabled={busy || !incrementalSchedule.cron_expression} onclick={() => void persistSchedule(incrementalSchedule)}>Save incremental schedule</V2Button></div>
                </V2Stack>
              </V2Card>
            {/if}

            {#if fullSchedule}
              <V2Card title="Global full-sync schedule">
                {#snippet actions()}<V2Badge tone={fullSchedule.enabled ? 'ok' : 'default'} text={fullSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}
                <V2Stack gap="sm">
                  <V2Checkbox label="Enable global full-sync schedule" checked={fullSchedule.enabled} onchange={(checked) => updateSchedule(fullSchedule.name, { enabled: checked })} />
                  <V2CronField id="settings-global-cron" label="Global full synchronization" enabled={fullSchedule.enabled} value={fullSchedule.cron_expression ?? ''} onchange={(value) => updateSchedule(fullSchedule.name, { cron_expression: value })} />
                  <div><V2Button variant="primary" disabled={busy || !fullSchedule.cron_expression} onclick={() => void persistSchedule(fullSchedule)}>Save global schedule</V2Button></div>
                </V2Stack>
              </V2Card>
            {/if}
          </div>
        </V2Section>
      </V2Stack>
    {/if}
  </V2Zone>
</V2PageLayout>

<style>
  .sync-run-actions{display:flex;flex-wrap:wrap;gap:.5rem}
  .sync-run-summary,.sync-counter-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}
  .sync-run-summary>div,.sync-counter-grid>div{display:grid;gap:.15rem;padding:.7rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}
  .sync-run-summary span,.sync-counter-grid span{font-size:.78rem;opacity:.7;text-transform:capitalize}
  .sync-control-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}
  @media(max-width:900px){.sync-control-grid,.sync-run-summary,.sync-counter-grid{grid-template-columns:1fr}}
</style>

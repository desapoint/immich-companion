<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '../../lib/components/ui/LoadingSpinner.svelte';
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
  import type { SyncCoordinatorStatus, SyncMode, SyncRun, SyncRuntimeSettings, SyncSchedule, TaskConnectionState, TaskSubscription } from '../data/syncContracts';
  import { readV2Density, V2_DENSITY_EVENT, writeV2Density, type V2Density } from '../state/density';

  type SettingsTab = 'General' | 'Duplicates' | 'Sync';
  type PendingOperation = 'starting' | 'cancelling' | 'runtime' | 'schedules' | null;

  let tab = $state<SettingsTab>('General');
  let density = $state<V2Density>('standard');
  let statusState = $state<SyncCoordinatorStatus | null>(null);
  let runtime = $state<SyncRuntimeSettings | null>(null);
  let savedRuntime = $state<SyncRuntimeSettings | null>(null);
  let schedules = $state<SyncSchedule[]>([]);
  let savedSchedules = $state<SyncSchedule[]>([]);
  let loading = $state(true);
  let pendingOperation = $state<PendingOperation>(null);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let connectionState = $state<TaskConnectionState>('connecting');
  let active = true;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let taskSubscription: TaskSubscription | null = null;

  const currentRun = $derived(statusState?.active ?? statusState?.pending ?? null);
  const fullSchedule = $derived(schedules.find((item) => item.name === 'asset-sync-full') ?? null);
  const incrementalSchedule = $derived(schedules.find((item) => item.name === 'asset-sync-incremental') ?? null);
  const progressKnown = $derived(currentRun?.progress.total != null && currentRun.progress.percent != null);
  const runtimeDirty = $derived(Boolean(runtime && savedRuntime && JSON.stringify(runtime) !== JSON.stringify(savedRuntime)));
  const schedulesDirty = $derived(JSON.stringify(scheduleSnapshot(schedules)) !== JSON.stringify(scheduleSnapshot(savedSchedules)));
  const schedulesValid = $derived(schedules.every((item) => !item.enabled || Boolean(item.cronExpression)));
  const busy = $derived(pendingOperation !== null);

  function scheduleSnapshot(values: SyncSchedule[]): Array<{ name: string; enabled: boolean; cronExpression: string | null }> {
    return values.map(({ name, enabled, cronExpression }) => ({ name, enabled, cronExpression })).sort((a, b) => a.name.localeCompare(b.name));
  }

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
      runtime = { ...nextRuntime };
      savedRuntime = { ...nextRuntime };
      schedules = nextSchedules.map((item) => ({ ...item }));
      savedSchedules = nextSchedules.map((item) => ({ ...item }));
    } catch (value) {
      if (active) error = message(value, 'Could not load live synchronization configuration.');
    } finally {
      if (active) loading = false;
    }
  }

  async function start(mode: SyncMode): Promise<void> {
    if (busy) return;
    pendingOperation = 'starting';
    error = null;
    success = null;
    try {
      await libraryData.sync.start(mode);
      await refreshStatus();
      if (active) success = `${mode === 'full' ? 'Global' : 'Incremental'} synchronization started.`;
    } catch (value) {
      if (active) error = message(value, 'Could not start synchronization.');
    } finally {
      if (active) pendingOperation = null;
    }
  }

  async function cancelCurrent(): Promise<void> {
    const run = currentRun;
    if (!run || busy) return;
    pendingOperation = 'cancelling';
    error = null;
    success = null;
    try {
      await libraryData.tasks.cancel(run.taskId ?? run.id);
      await refreshStatus();
      if (active) success = 'Cancellation requested.';
    } catch (value) {
      if (active) error = message(value, 'Could not cancel synchronization.');
    } finally {
      if (active) pendingOperation = null;
    }
  }

  async function saveRuntime(): Promise<void> {
    if (!runtime || !runtimeDirty || busy) return;
    pendingOperation = 'runtime';
    error = null;
    success = null;
    const draft = { ...runtime };
    try {
      const saved = await libraryData.sync.saveRuntimeSettings(draft);
      if (!active) return;
      runtime = { ...saved };
      savedRuntime = { ...saved };
      success = 'Synchronization runtime settings saved.';
    } catch (value) {
      if (active) error = message(value, 'Could not save synchronization runtime settings. Your unsaved values are still shown.');
    } finally {
      if (active) pendingOperation = null;
    }
  }

  function setRuntime<K extends keyof SyncRuntimeSettings>(key: K, raw: string): void {
    if (!runtime) return;
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    runtime = { ...runtime, [key]: value };
  }

  function updateSchedule(name: string, patch: Partial<Pick<SyncSchedule, 'enabled' | 'cronExpression'>>): void {
    schedules = schedules.map((item) => item.name === name ? { ...item, ...patch } : item);
  }

  async function saveScheduleSection(): Promise<void> {
    if (!schedulesDirty || !schedulesValid || busy) return;
    pendingOperation = 'schedules';
    error = null;
    success = null;
    const draft = schedules.map((item) => ({ ...item }));
    try {
      const saved = await libraryData.sync.saveSchedules(scheduleSnapshot(draft));
      if (!active) return;
      const byName = new Map(saved.map((item) => [item.name, item]));
      schedules = draft.map((item) => byName.get(item.name) ?? item);
      savedSchedules = schedules.map((item) => ({ ...item }));
      success = 'Synchronization schedules saved.';
    } catch (value) {
      if (!active) return;
      error = message(value, 'Could not save all synchronization schedules. Unsaved values are still shown.');
      try {
        savedSchedules = (await libraryData.sync.schedules()).map((item) => ({ ...item }));
      } catch {
        // Keep the last confirmed snapshot when reconciliation is unavailable.
      }
    } finally {
      if (active) pendingOperation = null;
    }
  }

  function runLabel(run: SyncRun | null): string {
    if (!run) return 'Idle';
    if (run.status === 'queued') return 'Queued';
    if (run.status === 'retrying') return 'Retrying';
    if (run.status === 'recovering') return 'Recovering';
    return 'Running';
  }

  function connectionLabel(): string {
    if (connectionState === 'connected') return 'Live';
    if (connectionState === 'reconnecting') return 'Reconnecting';
    if (connectionState === 'connecting') return 'Connecting';
    return 'Disconnected';
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
    taskSubscription = libraryData.tasks.subscribe({
      onTask: (task) => { if (task.taskType === 'asset_sync') void refreshStatus(); },
      onConnectionState: (state) => {
        const wasDisconnected = connectionState === 'reconnecting' || connectionState === 'disconnected';
        connectionState = state;
        if (state === 'connected' && wasDisconnected) void refreshStatus();
      },
      onError: () => undefined,
    });
    pollTimer = setInterval(() => void refreshStatus(), 10000);
    return () => {
      active = false;
      window.removeEventListener(V2_DENSITY_EVENT, onDensity);
      if (pollTimer) clearInterval(pollTimer);
      taskSubscription?.close();
      taskSubscription = null;
    };
  });
</script>

<V2PageLayout title="Settings" description="Configure interface behavior and live synchronization controls.">
  {#snippet tabs()}<V2Tabs items={['General', 'Duplicates', 'Sync']} active={tab} ariaLabel="Settings sections" onselect={(value) => tab = value as SettingsTab} />{/snippet}

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
        <V2Notice tone="warning" title="This settings area is not live yet">Duplicate settings are intentionally disabled in V2 until their live integration is complete.</V2Notice>
      </V2Card>
    {:else if loading}
      <V2Notice>Loading live synchronization status and configuration…</V2Notice>
    {:else}
      <V2Stack gap="md">
        {#if error}<V2Notice tone="error" title="Synchronization request failed">{error}</V2Notice>{/if}
        {#if success}<V2Notice tone="success">{success}</V2Notice>{/if}
        {#if connectionState === 'reconnecting' || connectionState === 'disconnected'}
          <V2Notice tone="warning" title="Live updates interrupted">The last known synchronization state is still shown. Live task updates are {connectionState === 'reconnecting' ? 'reconnecting automatically' : 'disconnected'}; status polling continues in the meantime.</V2Notice>
        {/if}

        <V2Card title="Current synchronization">
          {#snippet actions()}<span class="sync-status-badges"><V2Badge tone={currentRun ? 'ok' : 'default'} text={runLabel(currentRun)} /><V2Badge tone={connectionState === 'connected' ? 'ok' : connectionState === 'disconnected' ? 'warn' : 'default'} text={connectionLabel()} /></span>{/snippet}
          <V2Stack gap="sm">
            {#if currentRun}
              <div class="sync-run-summary">
                <div><span>Mode</span><strong>{currentRun.mode === 'full' ? 'Global' : 'Incremental'}</strong></div>
                <div><span>Generation</span><strong>#{currentRun.generation}</strong></div>
                <div><span>Phase</span><strong>{currentRun.progress.phase || currentRun.phase}</strong></div>
                <div><span>Processed</span><strong>{formatNumber(currentRun.progress.completed)} / {formatNumber(currentRun.progress.total)}</strong></div>
              </div>
              <V2Progress value={progressKnown ? currentRun.progress.percent ?? undefined : undefined} indeterminate={!progressKnown} label={`Synchronization ${currentRun.progress.phase || currentRun.phase} progress`} />
              <div class="v2-small v2-muted">{currentRun.progress.detail ?? (progressKnown ? `${formatNumber(currentRun.progress.completed)} of ${formatNumber(currentRun.progress.total)} processed` : 'Synchronization is running; total work is not known yet.')}</div>
            {:else}
              <V2Notice tone="info">No synchronization is currently active or queued.</V2Notice>
            {/if}
            <div class="sync-run-actions">
              <V2Button variant="primary" disabled={busy || Boolean(currentRun)} onclick={() => void start('full')}>{#if pendingOperation === 'starting'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Starting…</span>{:else}Start global sync{/if}</V2Button>
              <V2Button disabled={busy || Boolean(currentRun)} onclick={() => void start('incremental')}>Start incremental sync</V2Button>
              <V2Button variant="danger" disabled={busy || !currentRun} onclick={() => void cancelCurrent()}>{pendingOperation === 'cancelling' ? 'Cancelling…' : 'Cancel sync'}</V2Button>
              <V2Button disabled={busy} onclick={() => void refreshStatus()}>Refresh</V2Button>
            </div>
          </V2Stack>
        </V2Card>

        <V2Card title="Run counters">
          {#if currentRun}
            <div class="sync-counter-grid">{#each Object.entries(currentRun.counters) as [name, value] (name)}<div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>{/each}</div>
          {:else if statusState?.lastSuccess}
            <div class="sync-counter-grid">{#each Object.entries(statusState.lastSuccess.counters) as [name, value] (name)}<div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>{/each}</div>
          {:else}<span class="v2-small v2-muted">No completed synchronization counters are available yet.</span>{/if}
        </V2Card>

        <V2Section title="Live runtime configuration">
          <V2Card title="Synchronization load controls">
            {#snippet actions()}<V2Badge tone={runtimeDirty ? 'warn' : 'ok'} text={runtimeDirty ? 'Unsaved changes' : 'Saved'} />{/snippet}
            {#if runtime}
              <V2Stack gap="sm">
                <V2Field label="Full-sync persistence batch size" type="number" min="1" value={runtime.fullBatchSize} onchange={(value) => setRuntime('fullBatchSize', value)} />
                <V2Field label="Minimum full-sync batch delay (seconds)" type="number" min="0" step="0.1" value={runtime.fullMinBatchDelaySeconds} onchange={(value) => setRuntime('fullMinBatchDelaySeconds', value)} />
                <V2Field label="Tag association concurrency" type="number" min="1" max="32" value={runtime.tagAssociationConcurrency} onchange={(value) => setRuntime('tagAssociationConcurrency', value)} />
                <V2Notice tone="info" title="Only persisted controls are shown">Page concurrency and additional per-step controls remain hidden until their backend implementation is live.</V2Notice>
                <div><V2Button variant="primary" disabled={busy || !runtimeDirty} onclick={() => void saveRuntime()}>{#if pendingOperation === 'runtime'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Saving…</span>{:else}Save runtime settings{/if}</V2Button></div>
              </V2Stack>
            {:else}<V2Notice tone="error">Runtime settings were not available.</V2Notice>{/if}
          </V2Card>
        </V2Section>

        <V2Section title="Schedules">
          <V2Stack gap="sm">
            <div class="sync-control-grid">
              {#if incrementalSchedule}
                <V2Card title="Incremental sync schedule">
                  {#snippet actions()}<V2Badge tone={incrementalSchedule.enabled ? 'ok' : 'default'} text={incrementalSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}
                  <V2Stack gap="sm">
                    <V2Checkbox label="Enable incremental sync schedule" checked={incrementalSchedule.enabled} onchange={(checked) => updateSchedule(incrementalSchedule.name, { enabled: checked })} />
                    <V2CronField id="settings-incremental-cron" label="Incremental synchronization" enabled={incrementalSchedule.enabled} value={incrementalSchedule.cronExpression ?? ''} onchange={(value) => updateSchedule(incrementalSchedule.name, { cronExpression: value })} />
                  </V2Stack>
                </V2Card>
              {/if}
              {#if fullSchedule}
                <V2Card title="Global full-sync schedule">
                  {#snippet actions()}<V2Badge tone={fullSchedule.enabled ? 'ok' : 'default'} text={fullSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}
                  <V2Stack gap="sm">
                    <V2Checkbox label="Enable global full-sync schedule" checked={fullSchedule.enabled} onchange={(checked) => updateSchedule(fullSchedule.name, { enabled: checked })} />
                    <V2CronField id="settings-global-cron" label="Global full synchronization" enabled={fullSchedule.enabled} value={fullSchedule.cronExpression ?? ''} onchange={(value) => updateSchedule(fullSchedule.name, { cronExpression: value })} />
                  </V2Stack>
                </V2Card>
              {/if}
            </div>
            <div class="sync-section-save"><V2Badge tone={schedulesDirty ? 'warn' : 'ok'} text={schedulesDirty ? 'Unsaved changes' : 'Saved'} /><V2Button variant="primary" disabled={busy || !schedulesDirty || !schedulesValid} onclick={() => void saveScheduleSection()}>{#if pendingOperation === 'schedules'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Saving schedules…</span>{:else}Save schedule changes{/if}</V2Button></div>
          </V2Stack>
        </V2Section>
      </V2Stack>
    {/if}
  </V2Zone>
</V2PageLayout>

<style>
  .sync-run-actions,.sync-status-badges,.sync-section-save,.pending-label{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem}
  .sync-section-save{justify-content:flex-end}
  .sync-run-summary,.sync-counter-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}
  .sync-run-summary>div,.sync-counter-grid>div{display:grid;gap:.15rem;padding:.7rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}
  .sync-run-summary span,.sync-counter-grid span{font-size:.78rem;opacity:.7;text-transform:capitalize}
  .sync-control-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}
  @media(max-width:900px){.sync-control-grid,.sync-run-summary,.sync-counter-grid{grid-template-columns:1fr}}
</style>

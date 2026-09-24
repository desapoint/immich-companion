<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '../../../lib/components/ui/LoadingSpinner.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import V2CronField from '../../../lib/components/ui/CronField.svelte';
  import V2Field from '../../../lib/components/ui/TextField.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import V2Progress from '../../../lib/components/ui/Progress.svelte';
  import V2SelectField from '../../../lib/components/ui/SimpleSelectField.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import type { SyncMode, SyncRun, SyncRuntimeSettings, SyncSchedule } from '../../status/types/syncContracts';
  import { syncStatus } from '../../status/state/syncStatus.svelte';
  import { connectionLabel, connectionTone } from '../../status/utils/connectionPresentation';

  type PendingOperation = 'starting' | 'cancelling' | 'runtime' | 'schedules' | null;
  let runtime = $state<SyncRuntimeSettings | null>(null);
  let savedRuntime = $state<SyncRuntimeSettings | null>(null);
  let schedules = $state<SyncSchedule[]>([]);
  let savedSchedules = $state<SyncSchedule[]>([]);
  let loading = $state(true);
  let pendingOperation = $state<PendingOperation>(null);
  let error = $state<string | null>(null);
  let success = $state<string | null>(null);
  let active = true;
  const currentRun = $derived(syncStatus.status?.active ?? syncStatus.status?.pending ?? null);
  const fullSchedule = $derived(schedules.find((item) => item.name === 'asset-sync-full') ?? null);
  const incrementalSchedule = $derived(schedules.find((item) => item.name === 'asset-sync-incremental') ?? null);
  const progressKnown = $derived(currentRun?.progress.total != null && currentRun.progress.percent != null);
  const runtimeDirty = $derived(Boolean(runtime && savedRuntime && JSON.stringify(runtime) !== JSON.stringify(savedRuntime)));
  const runtimeValid = $derived(Boolean(runtime
    && Number.isInteger(runtime.fullBatchSize) && runtime.fullBatchSize >= 1 && runtime.fullBatchSize <= 500
    && runtime.fullMinBatchDelaySeconds >= 0 && runtime.fullMinBatchDelaySeconds <= 60
    && Number.isInteger(runtime.tagAssociationConcurrency) && runtime.tagAssociationConcurrency >= 1 && runtime.tagAssociationConcurrency <= 32
    && Number.isInteger(runtime.metadataRequestConcurrency) && runtime.metadataRequestConcurrency >= 1 && runtime.metadataRequestConcurrency <= 16
    && Number.isInteger(runtime.pagePrefetch) && runtime.pagePrefetch >= 0 && runtime.pagePrefetch <= 4
    && Number.isInteger(runtime.apiPageSize) && runtime.apiPageSize >= 25 && runtime.apiPageSize <= 1000
    && Number.isInteger(runtime.incrementalOverlapSeconds) && runtime.incrementalOverlapSeconds >= 0 && runtime.incrementalOverlapSeconds <= 86400));
  const schedulesDirty = $derived(JSON.stringify(scheduleSnapshot(schedules)) !== JSON.stringify(scheduleSnapshot(savedSchedules)));
  const schedulesValid = $derived(schedules.every((item) => !item.enabled || Boolean(item.cronExpression)));
  const busy = $derived(pendingOperation !== null);

  function scheduleSnapshot(values: SyncSchedule[]) { return values.map(({ name, enabled, cronExpression }) => ({ name, enabled, cronExpression })).sort((a, b) => a.name.localeCompare(b.name)); }
  function message(value: unknown, fallback: string) { return value instanceof Error ? value.message : fallback; }
  function formatNumber(value: number | null | undefined) { return typeof value === 'number' ? value.toLocaleString() : '—'; }
  function runLabel(run: SyncRun | null) { if (!run) return 'Idle'; if (run.status === 'queued') return 'Queued'; if (run.status === 'retrying') return 'Retrying'; if (run.status === 'recovering') return 'Recovering'; if (run.status === 'completed') return 'Completed'; if (run.status === 'failed') return 'Failed'; if (run.status === 'cancelled') return 'Cancelled'; return 'Running'; }
  function runTone(run: SyncRun | null): 'default' | 'ok' | 'warn' | 'bad' { if (!run) return 'default'; if (run.status === 'failed') return 'bad'; if (run.status === 'cancelled') return 'warn'; return 'ok'; }
  async function refreshScheduleRunTimes() { try { const latest = await libraryData.sync.schedules(); if (!active) return; const byName = new Map(latest.map((item) => [item.name, item])); const merge = (item: SyncSchedule) => { const live = byName.get(item.name); return live ? { ...item, lastRunAt: live.lastRunAt, nextRunAt: live.nextRunAt } : item; }; schedules = schedules.map(merge); savedSchedules = savedSchedules.map(merge); } catch { /* status remains useful without schedule metadata */ } }
  async function refreshStatus() { await Promise.all([syncStatus.refresh(), refreshScheduleRunTimes()]); }
  async function loadConfiguration() { loading = true; error = null; try { const [nextRuntime, nextSchedules] = await Promise.all([libraryData.sync.runtimeSettings(), libraryData.sync.schedules()]); if (!active) return; runtime = { ...nextRuntime }; savedRuntime = { ...nextRuntime }; schedules = nextSchedules.map((item) => ({ ...item })); savedSchedules = nextSchedules.map((item) => ({ ...item })); } catch (value) { if (active) error = message(value, 'Could not load live synchronization configuration.'); } finally { if (active) loading = false; } }
  async function start(mode: SyncMode) { if (busy) return; pendingOperation = 'starting'; error = null; success = null; try { await libraryData.sync.start(mode); await refreshStatus(); if (active) success = `${mode === 'full' ? 'Global' : 'Incremental'} synchronization started.`; } catch (value) { if (active) error = message(value, 'Could not start synchronization.'); } finally { if (active) pendingOperation = null; } }
  async function cancelCurrent() { const run = currentRun; if (!run || busy) return; pendingOperation = 'cancelling'; error = null; success = null; try { await libraryData.tasks.cancel(run.taskId ?? run.id); await syncStatus.refresh(); if (active) success = 'Cancellation requested.'; } catch (value) { if (active) error = message(value, 'Could not cancel synchronization.'); } finally { if (active) pendingOperation = null; } }
  function setRuntime<K extends keyof SyncRuntimeSettings>(key: K, raw: string) { if (!runtime) return; const value = Number(raw); if (Number.isFinite(value)) runtime = { ...runtime, [key]: value }; }
  function setRuntimeValue<K extends keyof SyncRuntimeSettings>(key: K, value: SyncRuntimeSettings[K]) { if (runtime) runtime = { ...runtime, [key]: value }; }
  async function saveRuntime() { if (!runtime || !runtimeDirty || busy) return; pendingOperation = 'runtime'; error = null; success = null; try { const saved = await libraryData.sync.saveRuntimeSettings({ ...runtime }); if (!active) return; runtime = { ...saved }; savedRuntime = { ...saved }; success = 'Synchronization runtime settings saved.'; } catch (value) { if (active) error = message(value, 'Could not save synchronization runtime settings. Your unsaved values are still shown.'); } finally { if (active) pendingOperation = null; } }
  function updateSchedule(name: string, patch: Partial<Pick<SyncSchedule, 'enabled' | 'cronExpression'>>) { schedules = schedules.map((item) => item.name === name ? { ...item, ...patch } : item); }
  async function saveSchedules() { if (!schedulesDirty || !schedulesValid || busy) return; pendingOperation = 'schedules'; error = null; success = null; const draft = schedules.map((item) => ({ ...item })); try { const saved = await libraryData.sync.saveSchedules(scheduleSnapshot(draft)); if (!active) return; const byName = new Map(saved.map((item) => [item.name, item])); schedules = draft.map((item) => byName.get(item.name) ?? item); savedSchedules = schedules.map((item) => ({ ...item })); success = 'Synchronization schedules saved.'; } catch (value) { if (!active) return; error = message(value, 'Could not save all synchronization schedules. Unsaved values are still shown.'); try { savedSchedules = (await libraryData.sync.schedules()).map((item) => ({ ...item })); } catch { /* retain last confirmed snapshot */ } } finally { if (active) pendingOperation = null; } }
  onMount(() => {
    void loadConfiguration();
    const release = syncStatus.acquire();
    const scheduleRefresh = setInterval(() => void refreshScheduleRunTimes(), 30_000);
    return () => {
      active = false;
      clearInterval(scheduleRefresh);
      release();
    };
  });
</script>

{#if loading}<V2Notice>Loading live synchronization status and configuration…</V2Notice>
{:else}<V2Stack gap="md">
  {#if error}<V2Notice tone="error" title="Synchronization request failed">{error}</V2Notice>{/if}
  {#if syncStatus.error && !syncStatus.status}<V2Notice tone="error" title="Synchronization status unavailable">{syncStatus.error}</V2Notice>{/if}
  {#if success}<V2Notice tone="success">{success}</V2Notice>{/if}
  {#if syncStatus.connectionState === 'reconnecting' || syncStatus.connectionState === 'disconnected'}<V2Notice tone="warning" title="Live updates interrupted">The last known synchronization state is still shown. Live task updates are {syncStatus.connectionState === 'reconnecting' ? 'reconnecting automatically' : 'disconnected'}; shared status polling continues in the meantime.</V2Notice>{/if}
  <V2Card title="Current synchronization">
    {#snippet actions()}<span class="sync-status-badges"><V2Badge tone={runTone(currentRun)} text={runLabel(currentRun)} /><V2Badge tone={connectionTone(syncStatus.connectionState)} text={connectionLabel(syncStatus.connectionState)} /></span>{/snippet}
    <V2Stack gap="sm">{#if currentRun}<div class="sync-run-summary"><div><span>Mode</span><strong>{currentRun.mode === 'full' ? 'Global' : 'Incremental'}</strong></div><div><span>Generation</span><strong>#{currentRun.generation}</strong></div><div><span>Phase</span><strong>{currentRun.progress.phase || currentRun.phase}</strong></div><div><span>Processed</span><strong>{formatNumber(currentRun.progress.completed)} / {formatNumber(currentRun.progress.total)}</strong></div></div><V2Progress value={progressKnown ? currentRun.progress.percent ?? undefined : undefined} indeterminate={!progressKnown} label={`Synchronization ${currentRun.progress.phase || currentRun.phase} progress`} /><div class="v2-small v2-muted">{currentRun.progress.detail ?? (progressKnown ? `${formatNumber(currentRun.progress.completed)} of ${formatNumber(currentRun.progress.total)} processed` : 'Synchronization is running; total work is not known yet.')}</div>{:else}<V2Notice tone="info">No synchronization is currently active or queued.</V2Notice>{/if}<div class="sync-run-actions"><V2Button variant="primary" disabled={busy || Boolean(currentRun)} onclick={() => void start('full')}>{#if pendingOperation === 'starting'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Starting…</span>{:else}Start global sync{/if}</V2Button><V2Button disabled={busy || Boolean(currentRun)} onclick={() => void start('incremental')}>Start incremental sync</V2Button><V2Button variant="danger" disabled={busy || !currentRun || ['completed', 'failed', 'cancelled'].includes(currentRun.status)} onclick={() => void cancelCurrent()}>{pendingOperation === 'cancelling' ? 'Cancelling…' : 'Cancel sync'}</V2Button><V2Button disabled={busy || syncStatus.loading} onclick={() => void refreshStatus()}>Refresh</V2Button></div></V2Stack>
  </V2Card>
  <V2Card title="Run counters">{#if currentRun}<div class="sync-counter-grid">{#each Object.entries(currentRun.counters) as [name, value] (name)}<div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>{/each}</div>{:else if syncStatus.status?.lastSuccess}<div class="sync-counter-grid">{#each Object.entries(syncStatus.status.lastSuccess.counters) as [name, value] (name)}<div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>{/each}</div>{:else}<span class="v2-small v2-muted">No completed synchronization counters are available yet.</span>{/if}</V2Card>
  <V2Section title="Live runtime configuration">
    <V2Card title="Synchronization performance">
      {#snippet actions()}<V2Badge tone={runtimeDirty ? 'warn' : 'ok'} text={runtimeDirty ? 'Unsaved changes' : 'Saved'} />{/snippet}
      {#if runtime}
        <V2Stack gap="md">
          <V2Notice tone="info" title="Changes apply to new synchronization work">All performance controls stay visible and are saved together; there are no presets. Running tasks keep their saved batch and window boundaries. EXIF remains excluded from inventory synchronization because fetching it for every asset previously made routine sync unnecessarily expensive; detailed metadata is requested only when a feature needs it.</V2Notice>
          <div class="sync-settings-grid">
            <div class="sync-setting">
              <V2Field label="Persistence batch size" type="number" min="1" max="500" step="1" value={runtime.fullBatchSize} onchange={(value) => setRuntime('fullBatchSize', value)} />
              <p>Rows committed per database checkpoint in both global and incremental syncs. Larger batches reduce transaction overhead but use more memory and repeat more work after interruption. Start at 250; lower it if memory or retry cost matters more than throughput.</p>
            </div>
            <div class="sync-setting">
              <V2Field label="Minimum global-sync batch duration (seconds)" type="number" min="0" max="60" step="0.1" value={runtime.fullMinBatchDelaySeconds} onchange={(value) => setRuntime('fullMinBatchDelaySeconds', value)} />
              <p>Slows only global sync batches when they finish faster than this duration. It is a minimum total batch time, not an extra fixed delay. Start at 0.2 seconds; use zero for maximum throughput or increase it to leave more capacity for Immich.</p>
            </div>
            <div class="sync-setting">
              <V2Field label="Relationship concurrency" type="number" min="1" max="32" step="1" value={runtime.tagAssociationConcurrency} onchange={(value) => setRuntime('tagAssociationConcurrency', value)} />
              <p>Album and tag membership traversals processed together. Higher values reduce relation-sync time but increase simultaneous Immich and PostgreSQL work. Start at 4 and reduce it if relation sync competes with normal Immich use.</p>
            </div>
            <div class="sync-setting">
              <V2Field label="Metadata request concurrency" type="number" min="1" max="16" step="1" value={runtime.metadataRequestConcurrency} onchange={(value) => setRuntime('metadataRequestConcurrency', value)} />
              <p>Total detailed asset and album requests allowed at once for incremental reconciliation and targeted repairs. It does not increase image download or decoding concurrency. Start at 4; raise it only when Immich has spare API capacity.</p>
            </div>
            <div class="sync-setting">
              <V2Field label="Pages to prefetch" type="number" min="0" max="4" step="1" value={runtime.pagePrefetch} onchange={(value) => setRuntime('pagePrefetch', value)} />
              <p>Fetches upcoming Immich pages while the current page is written. Zero is fully sequential; one usually hides network latency without materially increasing memory. Values above one trade more memory and upstream pressure for additional overlap.</p>
            </div>
            <div class="sync-setting">
              <V2Field label="Immich API page size" type="number" min="25" max="1000" step="25" value={runtime.apiPageSize} onchange={(value) => setRuntime('apiPageSize', value)} />
              <p>Assets or relationship IDs requested per page. Start at 1,000 to minimize HTTP round trips. Smaller pages lower peak response memory, make retries cheaper and may behave better through restrictive proxies.</p>
            </div>
            <div class="sync-setting">
              <V2Field label="Incremental overlap (seconds)" type="number" min="0" max="86400" step="30" value={runtime.incrementalOverlapSeconds} onchange={(value) => setRuntime('incrementalOverlapSeconds', value)} />
              <p>Rechecks this much time before the last successful watermark so boundary-time updates are not missed. Start at 300 seconds (5 minutes). More overlap is safer for clock skew and late updates but repeats more asset work.</p>
            </div>
            <div class="sync-setting">
              <V2SelectField
                id="sync-incremental-strategy"
                label="Incremental relationship strategy"
                value={runtime.incrementalStrategy}
                options={[
                  { value: 'automatic', label: 'Automatic — lower estimated request count' },
                  { value: 'asset', label: 'Changed assets — per-asset lookup' },
                  { value: 'relation', label: 'Complete relations — full traversal' },
                ]}
                onchange={(value) => setRuntimeValue('incrementalStrategy', value as SyncRuntimeSettings['incrementalStrategy'])}
              />
              <p>Automatic estimates which path needs fewer Immich requests and is the recommended default. Changed assets favor small updates; complete relations favor large incremental windows and deliberately perform a full album/tag membership pass.</p>
            </div>
            <div class="sync-setting sync-setting-wide">
              <V2Checkbox variant="switch" label="Adaptive throttling" checked={runtime.adaptiveThrottling} onchange={(checked) => setRuntimeValue('adaptiveThrottling', checked)} />
              <p>Recommended on. It shares Retry-After and exponential cooldowns across concurrent metadata requests after rate limits or temporary Immich failures, preventing parallel workers from immediately adding more pressure. Turn it off only when diagnosing retry behavior.</p>
            </div>
          </div>
          {#if !runtimeValid}<V2Notice tone="error">One or more performance values are outside the supported range.</V2Notice>{/if}
          <div><V2Button variant="primary" disabled={busy || !runtimeDirty || !runtimeValid} onclick={() => void saveRuntime()}>{#if pendingOperation === 'runtime'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Saving…</span>{:else}Save runtime settings{/if}</V2Button></div>
        </V2Stack>
      {:else}<V2Notice tone="error">Runtime settings were not available.</V2Notice>{/if}
    </V2Card>
  </V2Section>
  <V2Section title="Schedules"><V2Stack gap="sm"><div class="sync-control-grid">{#if incrementalSchedule}<V2Card title="Incremental sync schedule">{#snippet actions()}<V2Badge tone={incrementalSchedule.enabled ? 'ok' : 'default'} text={incrementalSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enable incremental sync schedule" checked={incrementalSchedule.enabled} onchange={(checked) => updateSchedule(incrementalSchedule.name, { enabled: checked })} /><V2CronField id="settings-incremental-cron" label="Incremental synchronization" enabled={incrementalSchedule.enabled} lastRunAt={incrementalSchedule.lastRunAt} value={incrementalSchedule.cronExpression ?? ''} onchange={(value) => updateSchedule(incrementalSchedule.name, { cronExpression: value })} /></V2Stack></V2Card>{/if}{#if fullSchedule}<V2Card title="Global full-sync schedule">{#snippet actions()}<V2Badge tone={fullSchedule.enabled ? 'ok' : 'default'} text={fullSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enable global full-sync schedule" checked={fullSchedule.enabled} onchange={(checked) => updateSchedule(fullSchedule.name, { enabled: checked })} /><V2CronField id="settings-global-cron" label="Global full synchronization" enabled={fullSchedule.enabled} lastRunAt={fullSchedule.lastRunAt} value={fullSchedule.cronExpression ?? ''} onchange={(value) => updateSchedule(fullSchedule.name, { cronExpression: value })} /></V2Stack></V2Card>{/if}</div><div class="sync-section-save"><V2Badge tone={schedulesDirty ? 'warn' : 'ok'} text={schedulesDirty ? 'Unsaved changes' : 'Saved'} /><V2Button variant="primary" disabled={busy || !schedulesDirty || !schedulesValid} onclick={() => void saveSchedules()}>{#if pendingOperation === 'schedules'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Saving schedules…</span>{:else}Save schedule changes{/if}</V2Button></div></V2Stack></V2Section>
</V2Stack>{/if}

<style>
  .sync-run-actions,.sync-status-badges,.sync-section-save,.pending-label{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem}.sync-section-save{justify-content:flex-end}.sync-run-summary,.sync-counter-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}.sync-run-summary>div,.sync-counter-grid>div{display:grid;gap:.15rem;padding:.7rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}.sync-run-summary span,.sync-counter-grid span{font-size:.78rem;opacity:.7;text-transform:capitalize}.sync-control-grid,.sync-settings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.sync-setting{display:grid;align-content:start;gap:.4rem;padding:.85rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}.sync-setting p{margin:0;color:var(--v2-muted);font-size:.78rem;line-height:1.45}.sync-setting-wide{grid-column:1/-1}@media(max-width:900px){.sync-control-grid,.sync-settings-grid,.sync-run-summary,.sync-counter-grid{grid-template-columns:1fr}.sync-setting-wide{grid-column:auto}}
</style>

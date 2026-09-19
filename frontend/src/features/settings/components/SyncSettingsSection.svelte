<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '../../../lib/components/ui/LoadingSpinner.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import V2CronField from '../../../v2/components/V2CronField.svelte';
  import V2Field from '../../../v2/components/V2Field.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import V2Progress from '../../../lib/components/ui/Progress.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import { libraryData } from '../../../app/data/currentDataSource.svelte';
  import type { SyncMode, SyncRun, SyncRuntimeSettings, SyncSchedule } from '../../status/types/syncContracts';
  import { syncStatus } from '../../status/state/syncStatus.svelte';

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
  const schedulesDirty = $derived(JSON.stringify(scheduleSnapshot(schedules)) !== JSON.stringify(scheduleSnapshot(savedSchedules)));
  const schedulesValid = $derived(schedules.every((item) => !item.enabled || Boolean(item.cronExpression)));
  const busy = $derived(pendingOperation !== null);

  function scheduleSnapshot(values: SyncSchedule[]) { return values.map(({ name, enabled, cronExpression }) => ({ name, enabled, cronExpression })).sort((a, b) => a.name.localeCompare(b.name)); }
  function message(value: unknown, fallback: string) { return value instanceof Error ? value.message : fallback; }
  function formatNumber(value: number | null | undefined) { return typeof value === 'number' ? value.toLocaleString() : '—'; }
  function runLabel(run: SyncRun | null) { if (!run) return 'Idle'; if (run.status === 'queued') return 'Queued'; if (run.status === 'retrying') return 'Retrying'; if (run.status === 'recovering') return 'Recovering'; if (run.status === 'completed') return 'Completed'; if (run.status === 'failed') return 'Failed'; if (run.status === 'cancelled') return 'Cancelled'; return 'Running'; }
  function runTone(run: SyncRun | null): 'default' | 'ok' | 'warn' | 'bad' { if (!run) return 'default'; if (run.status === 'failed') return 'bad'; if (run.status === 'cancelled') return 'warn'; return 'ok'; }
  function connectionLabel() { if (syncStatus.connectionState === 'connected') return 'Live'; if (syncStatus.connectionState === 'reconnecting') return 'Reconnecting'; if (syncStatus.connectionState === 'connecting') return 'Connecting'; return 'Disconnected'; }
  function scheduleLastRunAt(schedule: SyncSchedule): string | null {
    const mode = schedule.payload.mode; let latest = schedule.lastRunAt; let latestTime = latest ? Date.parse(latest) : Number.NEGATIVE_INFINITY;
    if (mode !== 'full' && mode !== 'incremental') return latest;
    for (const run of [syncStatus.status?.active, syncStatus.status?.pending, syncStatus.status?.lastSuccess, syncStatus.status?.lastFailure]) {
      if (!run?.startedAt || run.mode !== mode) continue; const startedAt = Date.parse(run.startedAt);
      if (Number.isFinite(startedAt) && startedAt > latestTime) { latest = run.startedAt; latestTime = startedAt; }
    }
    return latest;
  }
  async function refreshScheduleRunTimes() { try { const latest = await libraryData.sync.schedules(); if (!active) return; const byName = new Map(latest.map((item) => [item.name, item])); const merge = (item: SyncSchedule) => { const live = byName.get(item.name); return live ? { ...item, lastRunAt: live.lastRunAt, nextRunAt: live.nextRunAt } : item; }; schedules = schedules.map(merge); savedSchedules = savedSchedules.map(merge); } catch { /* status remains useful without schedule metadata */ } }
  async function refreshStatus() { await Promise.all([syncStatus.refresh(), refreshScheduleRunTimes()]); }
  async function loadConfiguration() { loading = true; error = null; try { const [nextRuntime, nextSchedules] = await Promise.all([libraryData.sync.runtimeSettings(), libraryData.sync.schedules()]); if (!active) return; runtime = { ...nextRuntime }; savedRuntime = { ...nextRuntime }; schedules = nextSchedules.map((item) => ({ ...item })); savedSchedules = nextSchedules.map((item) => ({ ...item })); } catch (value) { if (active) error = message(value, 'Could not load live synchronization configuration.'); } finally { if (active) loading = false; } }
  async function start(mode: SyncMode) { if (busy) return; pendingOperation = 'starting'; error = null; success = null; try { await libraryData.sync.start(mode); await refreshStatus(); if (active) success = `${mode === 'full' ? 'Global' : 'Incremental'} synchronization started.`; } catch (value) { if (active) error = message(value, 'Could not start synchronization.'); } finally { if (active) pendingOperation = null; } }
  async function cancelCurrent() { const run = currentRun; if (!run || busy) return; pendingOperation = 'cancelling'; error = null; success = null; try { await libraryData.tasks.cancel(run.taskId ?? run.id); await syncStatus.refresh(); if (active) success = 'Cancellation requested.'; } catch (value) { if (active) error = message(value, 'Could not cancel synchronization.'); } finally { if (active) pendingOperation = null; } }
  function setRuntime<K extends keyof SyncRuntimeSettings>(key: K, raw: string) { if (!runtime) return; const value = Number(raw); if (Number.isFinite(value)) runtime = { ...runtime, [key]: value }; }
  async function saveRuntime() { if (!runtime || !runtimeDirty || busy) return; pendingOperation = 'runtime'; error = null; success = null; try { const saved = await libraryData.sync.saveRuntimeSettings({ ...runtime }); if (!active) return; runtime = { ...saved }; savedRuntime = { ...saved }; success = 'Synchronization runtime settings saved.'; } catch (value) { if (active) error = message(value, 'Could not save synchronization runtime settings. Your unsaved values are still shown.'); } finally { if (active) pendingOperation = null; } }
  function updateSchedule(name: string, patch: Partial<Pick<SyncSchedule, 'enabled' | 'cronExpression'>>) { schedules = schedules.map((item) => item.name === name ? { ...item, ...patch } : item); }
  async function saveSchedules() { if (!schedulesDirty || !schedulesValid || busy) return; pendingOperation = 'schedules'; error = null; success = null; const draft = schedules.map((item) => ({ ...item })); try { const saved = await libraryData.sync.saveSchedules(scheduleSnapshot(draft)); if (!active) return; const byName = new Map(saved.map((item) => [item.name, item])); schedules = draft.map((item) => byName.get(item.name) ?? item); savedSchedules = schedules.map((item) => ({ ...item })); success = 'Synchronization schedules saved.'; } catch (value) { if (!active) return; error = message(value, 'Could not save all synchronization schedules. Unsaved values are still shown.'); try { savedSchedules = (await libraryData.sync.schedules()).map((item) => ({ ...item })); } catch { /* retain last confirmed snapshot */ } } finally { if (active) pendingOperation = null; } }
  onMount(() => { void loadConfiguration(); const release = syncStatus.acquire(); return () => { active = false; release(); }; });
</script>

{#if loading}<V2Notice>Loading live synchronization status and configuration…</V2Notice>
{:else}<V2Stack gap="md">
  {#if error}<V2Notice tone="error" title="Synchronization request failed">{error}</V2Notice>{/if}
  {#if syncStatus.error && !syncStatus.status}<V2Notice tone="error" title="Synchronization status unavailable">{syncStatus.error}</V2Notice>{/if}
  {#if success}<V2Notice tone="success">{success}</V2Notice>{/if}
  {#if syncStatus.connectionState === 'reconnecting' || syncStatus.connectionState === 'disconnected'}<V2Notice tone="warning" title="Live updates interrupted">The last known synchronization state is still shown. Live task updates are {syncStatus.connectionState === 'reconnecting' ? 'reconnecting automatically' : 'disconnected'}; shared status polling continues in the meantime.</V2Notice>{/if}
  <V2Card title="Current synchronization">
    {#snippet actions()}<span class="sync-status-badges"><V2Badge tone={runTone(currentRun)} text={runLabel(currentRun)} /><V2Badge tone={syncStatus.connectionState === 'connected' ? 'ok' : syncStatus.connectionState === 'disconnected' ? 'warn' : 'default'} text={connectionLabel()} /></span>{/snippet}
    <V2Stack gap="sm">{#if currentRun}<div class="sync-run-summary"><div><span>Mode</span><strong>{currentRun.mode === 'full' ? 'Global' : 'Incremental'}</strong></div><div><span>Generation</span><strong>#{currentRun.generation}</strong></div><div><span>Phase</span><strong>{currentRun.progress.phase || currentRun.phase}</strong></div><div><span>Processed</span><strong>{formatNumber(currentRun.progress.completed)} / {formatNumber(currentRun.progress.total)}</strong></div></div><V2Progress value={progressKnown ? currentRun.progress.percent ?? undefined : undefined} indeterminate={!progressKnown} label={`Synchronization ${currentRun.progress.phase || currentRun.phase} progress`} /><div class="v2-small v2-muted">{currentRun.progress.detail ?? (progressKnown ? `${formatNumber(currentRun.progress.completed)} of ${formatNumber(currentRun.progress.total)} processed` : 'Synchronization is running; total work is not known yet.')}</div>{:else}<V2Notice tone="info">No synchronization is currently active or queued.</V2Notice>{/if}<div class="sync-run-actions"><V2Button variant="primary" disabled={busy || Boolean(currentRun)} onclick={() => void start('full')}>{#if pendingOperation === 'starting'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Starting…</span>{:else}Start global sync{/if}</V2Button><V2Button disabled={busy || Boolean(currentRun)} onclick={() => void start('incremental')}>Start incremental sync</V2Button><V2Button variant="danger" disabled={busy || !currentRun || ['completed', 'failed', 'cancelled'].includes(currentRun.status)} onclick={() => void cancelCurrent()}>{pendingOperation === 'cancelling' ? 'Cancelling…' : 'Cancel sync'}</V2Button><V2Button disabled={busy || syncStatus.loading} onclick={() => void refreshStatus()}>Refresh</V2Button></div></V2Stack>
  </V2Card>
  <V2Card title="Run counters">{#if currentRun}<div class="sync-counter-grid">{#each Object.entries(currentRun.counters) as [name, value] (name)}<div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>{/each}</div>{:else if syncStatus.status?.lastSuccess}<div class="sync-counter-grid">{#each Object.entries(syncStatus.status.lastSuccess.counters) as [name, value] (name)}<div><strong>{formatNumber(value)}</strong><span>{name.replaceAll('_', ' ')}</span></div>{/each}</div>{:else}<span class="v2-small v2-muted">No completed synchronization counters are available yet.</span>{/if}</V2Card>
  <V2Section title="Live runtime configuration"><V2Card title="Synchronization load controls">{#snippet actions()}<V2Badge tone={runtimeDirty ? 'warn' : 'ok'} text={runtimeDirty ? 'Unsaved changes' : 'Saved'} />{/snippet}{#if runtime}<V2Stack gap="sm"><V2Field label="Full-sync persistence batch size" type="number" min="1" value={runtime.fullBatchSize} onchange={(value) => setRuntime('fullBatchSize', value)} /><V2Field label="Minimum full-sync batch delay (seconds)" type="number" min="0" step="0.1" value={runtime.fullMinBatchDelaySeconds} onchange={(value) => setRuntime('fullMinBatchDelaySeconds', value)} /><V2Field label="Tag association concurrency" type="number" min="1" max="32" value={runtime.tagAssociationConcurrency} onchange={(value) => setRuntime('tagAssociationConcurrency', value)} /><V2Notice tone="info" title="Only persisted controls are shown">Page concurrency and additional per-step controls remain hidden until their backend implementation is live.</V2Notice><div><V2Button variant="primary" disabled={busy || !runtimeDirty} onclick={() => void saveRuntime()}>{#if pendingOperation === 'runtime'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Saving…</span>{:else}Save runtime settings{/if}</V2Button></div></V2Stack>{:else}<V2Notice tone="error">Runtime settings were not available.</V2Notice>{/if}</V2Card></V2Section>
  <V2Section title="Schedules"><V2Stack gap="sm"><div class="sync-control-grid">{#if incrementalSchedule}<V2Card title="Incremental sync schedule">{#snippet actions()}<V2Badge tone={incrementalSchedule.enabled ? 'ok' : 'default'} text={incrementalSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enable incremental sync schedule" checked={incrementalSchedule.enabled} onchange={(checked) => updateSchedule(incrementalSchedule.name, { enabled: checked })} /><V2CronField id="settings-incremental-cron" label="Incremental synchronization" enabled={incrementalSchedule.enabled} lastRunAt={scheduleLastRunAt(incrementalSchedule)} value={incrementalSchedule.cronExpression ?? ''} onchange={(value) => updateSchedule(incrementalSchedule.name, { cronExpression: value })} /></V2Stack></V2Card>{/if}{#if fullSchedule}<V2Card title="Global full-sync schedule">{#snippet actions()}<V2Badge tone={fullSchedule.enabled ? 'ok' : 'default'} text={fullSchedule.enabled ? 'Enabled' : 'Disabled'} />{/snippet}<V2Stack gap="sm"><V2Checkbox label="Enable global full-sync schedule" checked={fullSchedule.enabled} onchange={(checked) => updateSchedule(fullSchedule.name, { enabled: checked })} /><V2CronField id="settings-global-cron" label="Global full synchronization" enabled={fullSchedule.enabled} lastRunAt={scheduleLastRunAt(fullSchedule)} value={fullSchedule.cronExpression ?? ''} onchange={(value) => updateSchedule(fullSchedule.name, { cronExpression: value })} /></V2Stack></V2Card>{/if}</div><div class="sync-section-save"><V2Badge tone={schedulesDirty ? 'warn' : 'ok'} text={schedulesDirty ? 'Unsaved changes' : 'Saved'} /><V2Button variant="primary" disabled={busy || !schedulesDirty || !schedulesValid} onclick={() => void saveSchedules()}>{#if pendingOperation === 'schedules'}<span class="pending-label"><LoadingSpinner size="0.9rem" thickness="0.11rem"/>Saving schedules…</span>{:else}Save schedule changes{/if}</V2Button></div></V2Stack></V2Section>
</V2Stack>{/if}

<style>
  .sync-run-actions,.sync-status-badges,.sync-section-save,.pending-label{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem}.sync-section-save{justify-content:flex-end}.sync-run-summary,.sync-counter-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}.sync-run-summary>div,.sync-counter-grid>div{display:grid;gap:.15rem;padding:.7rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}.sync-run-summary span,.sync-counter-grid span{font-size:.78rem;opacity:.7;text-transform:capitalize}.sync-control-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}@media(max-width:900px){.sync-control-grid,.sync-run-summary,.sync-counter-grid{grid-template-columns:1fr}}
</style>

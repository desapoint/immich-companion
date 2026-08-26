<script lang="ts">
  import { onMount } from 'svelte';

  import { loadSyncSchedules, saveSyncSchedule } from '../api/settingsApi';
  import type { SyncSchedule } from '../types/settings';

  const defaults: Record<string, string> = {
    'asset-sync-incremental': '*/15 * * * *',
    'asset-sync-full': '0 0 * * 0',
  };
  const labels: Record<string, string> = {
    'asset-sync-incremental': 'Incremental sync',
    'asset-sync-full': 'Global sync',
  };
  const common = [
    { label: 'Every 15 minutes', value: '*/15 * * * *' },
    { label: 'Every hour', value: '0 * * * *' },
    { label: 'Every day at midnight', value: '0 0 * * *' },
    { label: 'Every Sunday at midnight', value: '0 0 * * 0' },
  ];

  let schedules = $state<SyncSchedule[]>([]);
  let drafts = $state<Record<string, { enabled: boolean; cron_expression: string }>>({});
  let loading = $state(true);
  let saving = $state<string | null>(null);
  let message = $state<string | null>(null);
  let error = $state<string | null>(null);

  function hydrate(items: SyncSchedule[]): void {
    schedules = items;
    drafts = Object.fromEntries(items.map((item) => [item.name, {
      enabled: item.enabled,
      cron_expression: item.cron_expression ?? defaults[item.name] ?? '0 * * * *',
    }]));
  }

  function setDraft(name: string, patch: Partial<{ enabled: boolean; cron_expression: string }>): void {
    drafts[name] = { ...drafts[name], ...patch };
  }

  async function save(name: string): Promise<void> {
    const draft = drafts[name];
    if (!draft) return;
    saving = name;
    message = null;
    error = null;
    try {
      const updated = await saveSyncSchedule(name, draft);
      hydrate(schedules.map((item) => item.name === name ? updated : item));
      message = `${labels[name] ?? 'Schedule'} saved.`;
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'Could not save settings.';
    } finally {
      saving = null;
    }
  }

  onMount(async () => {
    try {
      hydrate(await loadSyncSchedules());
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'Could not load settings.';
    } finally {
      loading = false;
    }
  });
</script>

<section class="settings-page" aria-labelledby="settings-title">
  <div class="intro">
    <p class="eyebrow">Configuration</p>
    <h1 id="settings-title">Sync schedules</h1>
    <p>Automatic sync is off by default. Enable each schedule independently, or use a five-field cron expression.</p>
  </div>

  {#if loading}
    <p class="state">Loading sync settings…</p>
  {:else if error && schedules.length === 0}
    <p class="state error" role="alert">{error}</p>
  {:else}
    <div class="cards">
      {#each schedules as schedule}
        {@const draft = drafts[schedule.name]}
        <article class="schedule-card">
          <div class="card-heading">
            <div>
              <p class="eyebrow">{schedule.name === 'asset-sync-full' ? 'Authoritative catalog pass' : 'Recent changes'}</p>
              <h2>{labels[schedule.name] ?? schedule.name}</h2>
            </div>
            <label class="toggle">
              <input type="checkbox" checked={draft?.enabled ?? false} onchange={(event) => setDraft(schedule.name, { enabled: (event.currentTarget as HTMLInputElement).checked })} />
              <span>Enabled</span>
            </label>
          </div>
          <label class="field" for={`cron-${schedule.name}`}>
            <span>Cron expression</span>
            <input id={`cron-${schedule.name}`} value={draft?.cron_expression ?? ''} oninput={(event) => setDraft(schedule.name, { cron_expression: (event.currentTarget as HTMLInputElement).value })} spellcheck="false" />
          </label>
          <div class="presets" aria-label="Common schedules">
            {#each common as option}
              <button type="button" class:chosen={draft?.cron_expression === option.value} onclick={() => setDraft(schedule.name, { cron_expression: option.value })}>{option.label}</button>
            {/each}
          </div>
          <p class="hint">Next run: {draft?.enabled ? new Date(schedule.next_run_at).toLocaleString() : 'disabled'}</p>
          <button class="save" type="button" disabled={saving === schedule.name} onclick={() => void save(schedule.name)}>{saving === schedule.name ? 'Saving…' : 'Save schedule'}</button>
        </article>
      {/each}
    </div>
    {#if message}<p class="success" role="status">{message}</p>{/if}
    {#if error}<p class="state error" role="alert">{error}</p>{/if}
  {/if}
</section>

<style>
  .settings-page { display: grid; gap: 2rem; max-width: 64rem; margin: 0 auto; }
  .intro { max-width: 44rem; }
  .eyebrow { margin: 0 0 0.45rem; color: var(--color-accent-strong); font-size: 0.7rem; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }
  h1, h2 { margin: 0; letter-spacing: -0.04em; }
  h1 { font-size: clamp(2rem, 5vw, 3.5rem); }
  h2 { font-size: 1.25rem; }
  .intro > p:last-child { color: var(--color-ink-muted); line-height: 1.6; }
  .cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
  .schedule-card { display: grid; gap: 1.1rem; padding: 1.25rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); }
  .card-heading { display: flex; justify-content: space-between; gap: 1rem; }
  .toggle { display: flex; align-items: center; gap: 0.45rem; color: var(--color-ink-muted); font-size: 0.78rem; font-weight: 700; white-space: nowrap; }
  .field { display: grid; gap: 0.45rem; color: var(--color-ink-muted); font-size: 0.78rem; font-weight: 700; }
  input:not([type='checkbox']) { width: 100%; padding: 0.7rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); font: 0.9rem ui-monospace, monospace; }
  .presets { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .presets button, .save { padding: 0.5rem 0.65rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); color: var(--color-ink-muted); background: var(--color-surface-soft); font: inherit; font-size: 0.72rem; cursor: pointer; }
  .presets button.chosen { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  .save { border-color: var(--color-accent-strong); color: var(--color-ink-inverse); background: var(--color-accent-strong); font-weight: 800; }
  .save:disabled { opacity: 0.6; cursor: wait; }
  .hint, .state, .success { margin: 0; color: var(--color-ink-muted); font-size: 0.78rem; }
  .error { color: var(--color-danger, #b42318); }
  .success { color: var(--color-accent-strong); font-weight: 700; }
  @media (max-width: 46rem) { .cards { grid-template-columns: 1fr; } }
</style>

<script lang="ts">
  import { onMount } from 'svelte';

  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import MultiSelectField from '../../../lib/components/ui/MultiSelectField.svelte';
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import type { SelectOption } from '../../../lib/types/ui';
  import { loadDuplicatePolicy, loadImmichLibraries, loadSyncRuntimeSettings, loadSyncSchedules, saveDuplicatePolicy, saveSyncRuntimeSettings, saveSyncSchedule } from '../api/settingsApi';
  import type { DuplicatePolicy, ImmichLibraryOption, SyncRuntimeSettings, SyncSchedule } from '../types/settings';

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
  let runtime = $state<SyncRuntimeSettings | null>(null);
  let runtimeDraft = $state<SyncRuntimeSettings>({ full_batch_size: 50, full_min_batch_delay_seconds: 0.2, tag_association_concurrency: 4 });
  let runtimeSaving = $state(false);
  let duplicatePolicy = $state<DuplicatePolicy | null>(null);
  let duplicateDraft = $state<DuplicatePolicy | null>(null);
  let libraries = $state<ImmichLibraryOption[]>([]);
  let duplicateSaving = $state(false);
  const exactActionOptions: SelectOption[] = [
    { value: 'resolve', label: 'Resolve exact files' },
    { value: 'keep_all', label: 'Keep all exact copies' },
    { value: 'stack_all', label: 'Stack exact copies' },
    { value: 'review', label: 'Always review' },
  ];
  const keeperOptions: SelectOption[] = [
    { value: 'prefer_upload', label: 'Prefer Immich uploads' },
    { value: 'prefer_external', label: 'Prefer external files' },
    { value: 'most_recent', label: 'Most recently uploaded' },
    { value: 'first', label: 'First Immich result' },
  ];
  const libraryOptions = $derived<SelectOption[]>(libraries.map((library) => ({
    value: library.id,
    label: `${library.name}${library.assetCount === null ? '' : ` · ${library.assetCount} assets`}`,
  })));

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

  async function saveRuntime(): Promise<void> {
    runtimeSaving = true;
    message = null;
    error = null;
    try {
      runtime = await saveSyncRuntimeSettings(runtimeDraft);
      runtimeDraft = { ...runtime };
      message = 'Background batch load settings saved.';
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'Could not save background batch load settings.';
    } finally {
      runtimeSaving = false;
    }
  }

  async function saveDuplicates(): Promise<void> {
    if (!duplicateDraft) return;
    duplicateSaving = true;
    message = null;
    error = null;
    try {
      duplicatePolicy = await saveDuplicatePolicy(duplicateDraft);
      duplicateDraft = { ...duplicatePolicy };
      message = 'Duplicate handling policy saved.';
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'Could not save duplicate policy.';
    } finally {
      duplicateSaving = false;
    }
  }

  onMount(async () => {
    try {
      const [loadedSchedules, loadedRuntime, loadedPolicy, loadedLibraries] = await Promise.all([
        loadSyncSchedules(), loadSyncRuntimeSettings(), loadDuplicatePolicy(), loadImmichLibraries(),
      ]);
      hydrate(loadedSchedules);
      runtime = loadedRuntime;
      runtimeDraft = { ...loadedRuntime };
      duplicatePolicy = loadedPolicy;
      duplicateDraft = { ...loadedPolicy };
      libraries = loadedLibraries;
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
    <article class="runtime-card" aria-labelledby="runtime-settings-title">
      <div>
        <p class="eyebrow">Host responsiveness</p>
        <h2 id="runtime-settings-title">Background batch load</h2>
        <p class="hint">Global sync and large asset actions rest after each batch for at least this delay and otherwise as long as the batch took, limiting sustained work to about half of available capacity. Tag association concurrency controls parallel tag scans and the adaptive tag strategy: asset-oriented matching is selected when the assets in the sync are no more than the tag count divided by this value.</p>
      </div>
      <div class="runtime-fields">
        <label class="field" for="full-batch-size"><span>Assets per batch</span><input id="full-batch-size" type="number" min="1" max="500" value={runtimeDraft.full_batch_size} oninput={(event) => runtimeDraft = { ...runtimeDraft, full_batch_size: Number(event.currentTarget.value) }} /></label>
        <label class="field" for="full-batch-delay"><span>Minimum delay (seconds)</span><input id="full-batch-delay" type="number" min="0" max="60" step="0.1" value={runtimeDraft.full_min_batch_delay_seconds} oninput={(event) => runtimeDraft = { ...runtimeDraft, full_min_batch_delay_seconds: Number(event.currentTarget.value) }} /></label>
        <label class="field" for="tag-association-concurrency"><span>Tag association concurrency</span><input id="tag-association-concurrency" type="number" min="1" max="32" step="1" value={runtimeDraft.tag_association_concurrency} oninput={(event) => runtimeDraft = { ...runtimeDraft, tag_association_concurrency: Number(event.currentTarget.value) }} /></label>
      </div>
      <button class="save" type="button" disabled={runtimeSaving || !Number.isInteger(runtimeDraft.full_batch_size) || runtimeDraft.full_batch_size < 1 || runtimeDraft.full_batch_size > 500 || runtimeDraft.full_min_batch_delay_seconds < 0 || runtimeDraft.full_min_batch_delay_seconds > 60 || !Number.isInteger(runtimeDraft.tag_association_concurrency) || runtimeDraft.tag_association_concurrency < 1 || runtimeDraft.tag_association_concurrency > 32} onclick={() => void saveRuntime()}>{runtimeSaving ? 'Saving…' : 'Save load settings'}</button>
    </article>
    {#if duplicateDraft}
      <article class="duplicate-policy-card" aria-labelledby="duplicate-policy-title">
        <div>
          <p class="eyebrow">Duplicate review</p>
          <h2 id="duplicate-policy-title">Automatic handling policy</h2>
          <p class="hint">These defaults recompute automatic recommendations only. Saved manual group choices remain unchanged. Delete all is always manual.</p>
        </div>
        <div class="policy-fields">
          <SelectField id="duplicate-exact-action" label="Exact-file action" value={duplicateDraft.exact_file_action} options={exactActionOptions} onchange={(value) => duplicateDraft = { ...duplicateDraft!, exact_file_action: value as DuplicatePolicy['exact_file_action'] }} />
          <SelectField id="duplicate-keeper-policy" label="Primary rule" value={duplicateDraft.keeper_policy} options={keeperOptions} onchange={(value) => duplicateDraft = { ...duplicateDraft!, keeper_policy: value as DuplicatePolicy['keeper_policy'] }} />
          <MultiSelectField id="duplicate-library-policy" label="External libraries" values={duplicateDraft.external_library_ids} options={libraryOptions} placeholder="All external libraries" searchable onchange={(values) => duplicateDraft = { ...duplicateDraft!, external_library_ids: values }} />
        </div>
        <div class="policy-toggles">
          <Checkbox checked={duplicateDraft.automatic_handling_enabled} label="Enable automatic recommendations" variant="switch" onchange={(checked) => duplicateDraft = { ...duplicateDraft!, automatic_handling_enabled: checked }} />
          <Checkbox checked={duplicateDraft.preselect_safe_groups} label="Preselect safe groups" variant="switch" onchange={(checked) => duplicateDraft = { ...duplicateDraft!, preselect_safe_groups: checked }} />
          <Checkbox checked={duplicateDraft.analyze_automatically} label="Analyze candidate files automatically" variant="switch" onchange={(checked) => duplicateDraft = { ...duplicateDraft!, analyze_automatically: checked }} />
          <Checkbox checked={duplicateDraft.verify_upload_streams} label="Verify upload streams too" variant="switch" onchange={(checked) => duplicateDraft = { ...duplicateDraft!, verify_upload_streams: checked }} />
        </div>
        <button class="save" type="button" disabled={duplicateSaving} onclick={() => void saveDuplicates()}>{duplicateSaving ? 'Saving…' : 'Save duplicate policy'}</button>
      </article>
    {/if}
    <div class="cards">
      {#each schedules as schedule (schedule.id)}
        {@const draft = drafts[schedule.name]}
        <article class="schedule-card">
          <div class="card-heading">
            <div>
              <p class="eyebrow">{schedule.name === 'asset-sync-full' ? 'Authoritative catalog pass' : 'Recent changes'}</p>
              <h2>{labels[schedule.name] ?? schedule.name}</h2>
            </div>
            <Checkbox checked={draft?.enabled ?? false} label="Enabled" onchange={(checked) => setDraft(schedule.name, { enabled: checked })} />
          </div>
          <label class="field" for={`cron-${schedule.name}`}>
            <span>Cron expression</span>
            <input id={`cron-${schedule.name}`} value={draft?.cron_expression ?? ''} oninput={(event) => setDraft(schedule.name, { cron_expression: (event.currentTarget as HTMLInputElement).value })} spellcheck="false" />
          </label>
          <div class="presets" aria-label="Common schedules">
            {#each common as option (option.value)}
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
  .schedule-card, .runtime-card, .duplicate-policy-card { display: grid; gap: 1.1rem; padding: 1.25rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); }
  .runtime-card { grid-template-columns: minmax(0, 1fr) auto; align-items: end; }
  .runtime-card .hint { max-width: 48rem; line-height: 1.5; }
  .runtime-fields { display: grid; grid-template-columns: repeat(3, minmax(10rem, 1fr)); gap: .75rem; grid-column: 1 / -1; }
  .policy-fields { display: grid; grid-template-columns: repeat(2, minmax(12rem, 1fr)); gap: .75rem; }
  .policy-toggles { display: grid; grid-template-columns: repeat(2, minmax(12rem, 1fr)); gap: .75rem; }
  .card-heading { display: flex; justify-content: space-between; gap: 1rem; }
  .field { display: grid; gap: 0.45rem; color: var(--color-ink-muted); font-size: 0.78rem; font-weight: 700; }
  .field input { width: 100%; padding: 0.7rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); font: 0.9rem ui-monospace, monospace; }
  .presets { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .presets button, .save { padding: 0.5rem 0.65rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); color: var(--color-ink-muted); background: var(--color-surface-soft); font: inherit; font-size: 0.72rem; cursor: pointer; }
  .presets button.chosen { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  .save { border-color: var(--color-accent-strong); color: var(--color-ink-inverse); background: var(--color-accent-strong); font-weight: 800; }
  .save:disabled { opacity: 0.6; cursor: wait; }
  .hint, .state, .success { margin: 0; color: var(--color-ink-muted); font-size: 0.78rem; }
  .error { color: var(--color-danger, #b42318); }
  .success { color: var(--color-accent-strong); font-weight: 700; }
  @media (max-width: 46rem) { .cards, .runtime-fields, .policy-fields, .policy-toggles { grid-template-columns: 1fr; } .runtime-card { grid-template-columns: 1fr; } }
</style>

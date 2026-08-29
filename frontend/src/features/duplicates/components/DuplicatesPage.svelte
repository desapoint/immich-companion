<script lang="ts">
  import { onMount } from 'svelte';
  import { SvelteSet } from 'svelte/reactivity';

  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import {
    analyzeDuplicateGroups,
    executeDuplicateResolution,
    loadDuplicateGroups,
    loadDuplicateTask,
    planDuplicateResolution,
  } from '../api/duplicateApi';
  import type {
    DuplicateAnalysisOptions,
    DuplicateKeeperPolicy,
    DuplicateResolutionPlan,
    DuplicateResult,
    DuplicateTaskStatus,
    ExactDuplicateGroup,
  } from '../types/duplicates';

  const terminalStatuses = new Set(['completed', 'failed', 'cancelled']);
  const defaultOptions: DuplicateAnalysisOptions = {
    keeper_policy: 'prefer_upload',
    external_library_ids: [],
    verify_upload_streams: false,
  };

  let result = $state.raw<DuplicateResult | null>(null);
  let options = $state<DuplicateAnalysisOptions>({ ...defaultOptions });
  let libraryFilter = $state('');
  const selected = new SvelteSet<string>();
  let keeperOverrides = $state<Record<string, string>>({});
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let message = $state<string | null>(null);
  let task = $state.raw<DuplicateTaskStatus | null>(null);
  let plan = $state.raw<DuplicateResolutionPlan | null>(null);
  let confirmOpen = $state(false);
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  const exactGroups = $derived(result?.groups.filter((group) => group.eligible) ?? []);
  const selectedCount = $derived(selected.size);

  function configuredOptions(): DuplicateAnalysisOptions {
    return {
      ...options,
      external_library_ids: libraryFilter
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean),
    };
  }

  async function load(): Promise<void> {
    loading = true;
    error = null;
    try {
      result = await loadDuplicateGroups(configuredOptions());
      const eligibleIds = new SvelteSet(result.groups.filter((group) => group.eligible).map((group) => group.duplicate_id));
      for (const id of selected) if (!eligibleIds.has(id)) selected.delete(id);
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not load duplicate groups.';
    } finally {
      loading = false;
    }
  }

  function schedulePoll(taskId: string, kind: 'analysis' | 'resolution'): void {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = setTimeout(() => void pollTask(taskId, kind), 700);
  }

  async function pollTask(taskId: string, kind: 'analysis' | 'resolution'): Promise<void> {
    try {
      task = await loadDuplicateTask(taskId);
      if (!terminalStatuses.has(task.status)) {
        schedulePoll(taskId, kind);
        return;
      }
      busy = false;
      if (task.status === 'completed') {
        message = kind === 'analysis'
          ? 'Duplicate candidates were verified.'
          : 'The reviewed duplicate batch completed.';
        selected.clear();
        keeperOverrides = {};
        await load();
      } else {
        error = task.error?.message ?? `${kind === 'analysis' ? 'Analysis' : 'Resolution'} failed.`;
      }
    } catch (reason) {
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not read task progress.';
    }
  }

  async function analyze(): Promise<void> {
    busy = true;
    error = null;
    message = null;
    try {
      const started = await analyzeDuplicateGroups(configuredOptions());
      task = await loadDuplicateTask(started.task_id);
      schedulePoll(started.task_id, 'analysis');
    } catch (reason) {
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not start duplicate analysis.';
    }
  }

  function toggleGroup(groupId: string, checked: boolean): void {
    if (checked) selected.add(groupId);
    else selected.delete(groupId);
  }

  function toggleAllEligible(): void {
    if (selected.size === exactGroups.length) {
      selected.clear();
      return;
    }
    selected.clear();
    for (const group of exactGroups) selected.add(group.duplicate_id);
  }

  function setKeeper(group: ExactDuplicateGroup, assetId: string): void {
    keeperOverrides = { ...keeperOverrides, [group.duplicate_id]: assetId };
  }

  function selectedKeeper(group: ExactDuplicateGroup): string | null {
    return keeperOverrides[group.duplicate_id] ?? group.keeper_asset_id;
  }

  async function reviewBatch(): Promise<void> {
    if (!selected.size) return;
    busy = true;
    error = null;
    message = null;
    try {
      plan = await planDuplicateResolution({
        options: configuredOptions(),
        duplicate_ids: [...selected],
        all_eligible: false,
        keeper_overrides: keeperOverrides,
      });
      confirmOpen = true;
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not prepare the duplicate plan.';
    } finally {
      busy = false;
    }
  }

  async function executePlan(): Promise<void> {
    if (!plan) return;
    busy = true;
    error = null;
    try {
      const started = await executeDuplicateResolution(plan.id);
      confirmOpen = false;
      task = await loadDuplicateTask(started.task_id);
      schedulePoll(started.task_id, 'resolution');
    } catch (reason) {
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not execute the duplicate plan.';
    }
  }

  function setPolicy(value: string): void {
    options.keeper_policy = value as DuplicateKeeperPolicy;
    keeperOverrides = {};
    void load();
  }

  function formatSize(value: number | null): string {
    if (value === null) return 'Size unavailable';
    if (value < 1024) return `${value} B`;
    if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / 1024 ** 2).toFixed(1)} MB`;
  }

  onMount(() => {
    void load();
    return () => { if (pollTimer) clearTimeout(pollTimer); };
  });
</script>

<section class="duplicates-page" aria-labelledby="duplicates-title">
  <header class="page-intro">
    <div><span>Review workspace</span><h1 id="duplicates-title">Duplicates</h1></div>
    <p>Review Immich duplicate groups, verify exact file contents, choose which copy to keep, and resolve approved groups in one guarded batch.</p>
  </header>

  <section class="controls" aria-label="Duplicate rules">
    <label>Keeper rule
      <select value={options.keeper_policy} onchange={(event) => setPolicy(event.currentTarget.value)} disabled={busy}>
        <option value="prefer_upload">Prefer uploads</option>
        <option value="prefer_external">Prefer external files</option>
        <option value="first">First Immich result</option>
      </select>
    </label>
    <label class="library-filter">External library IDs <input value={libraryFilter} oninput={(event) => libraryFilter = event.currentTarget.value} onblur={() => void load()} placeholder="Optional, comma-separated" disabled={busy} /></label>
    <Checkbox checked={options.verify_upload_streams} label="Verify upload streams too" variant="switch" disabled={busy} onchange={(checked) => options.verify_upload_streams = checked} />
    <button class="primary" type="button" disabled={busy} onclick={() => void analyze()}>{busy && task?.status !== 'completed' ? 'Working…' : 'Verify candidates'}</button>
  </section>

  {#if task && !terminalStatuses.has(task.status)}
    <section class="progress" aria-live="polite">
      <div><strong>{task.progress.detail ?? 'Processing duplicate candidates…'}</strong><span>{task.progress.completed ?? 0}{task.progress.total ? ` / ${task.progress.total}` : ''}</span></div>
      <progress value={task.progress.percent ?? undefined} max="100"></progress>
    </section>
  {/if}
  {#if error}<p class="notice error" role="alert">{error}</p>{/if}
  {#if message}<p class="notice success" role="status">{message}</p>{/if}

  {#if result}
    <section class="summary" aria-label="Duplicate summary">
      <div><strong>{result.group_count}</strong><span>Immich groups</span></div>
      <div><strong>{result.exact_group_count}</strong><span>Exact</span></div>
      <div><strong>{result.unverified_group_count}</strong><span>Need verification</span></div>
      <div><strong>{result.mismatch_group_count}</strong><span>Not byte-exact</span></div>
    </section>

    <div class="batch-bar">
      <Checkbox checked={exactGroups.length > 0 && selectedCount === exactGroups.length} label="Select all exact groups" shape="circle" disabled={!exactGroups.length || busy} onchange={toggleAllEligible} />
      <span>{selectedCount} selected</span>
      <button type="button" disabled={!selectedCount || busy} onclick={() => void reviewBatch()}>Review batch</button>
    </div>

    {#if loading}
      <p class="empty">Refreshing duplicate groups…</p>
    {:else if !result.groups.length}
      <p class="empty">Immich currently reports no duplicate groups.</p>
    {:else}
      <div class="groups">
        {#each result.groups as group (group.duplicate_id)}
          <article class:eligible={group.eligible} class="group-card">
            <header>
              <div class="group-heading">
                <Checkbox checked={selected.has(group.duplicate_id)} label={`Select duplicate group ${group.duplicate_id}`} hiddenLabel shape="circle" disabled={!group.eligible || busy} onchange={(checked) => toggleGroup(group.duplicate_id, checked)} />
                <div><strong>{group.members.length} copies</strong><span class={`status ${group.status}`}>{group.status}</span></div>
              </div>
              <p>{group.reason}</p>
            </header>
            <div class="members">
              {#each group.members as member (member.id)}
                <div class:keeper={selectedKeeper(group) === member.id} class="member">
                  <img src={`/api/assets/${encodeURIComponent(member.id)}/thumbnail`} alt="" loading="lazy" />
                  <div class="member-body">
                    <div class="member-title"><strong title={member.original_file_name}>{member.original_file_name}</strong><span>{member.source_kind}</span></div>
                    <small>{formatSize(member.file_size_bytes)} · {member.verification}</small>
                    {#if member.library_id}<small title={member.library_id}>Library {member.library_id}</small>{/if}
                    <div class="member-actions">
                      <button type="button" disabled={!group.eligible || busy} aria-pressed={selectedKeeper(group) === member.id} onclick={() => setKeeper(group, member.id)}>{selectedKeeper(group) === member.id ? 'Keeping' : 'Keep this'}</button>
                      {#if member.immich_url}<a href={member.immich_url} target="_blank" rel="noreferrer">Open in Immich</a>{/if}
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          </article>
        {/each}
      </div>
    {/if}
  {:else if loading}
    <p class="empty">Loading Immich duplicate groups…</p>
  {/if}
</section>

{#if confirmOpen && plan}
  <ConfirmDialog
    title="Resolve exact duplicates"
    message={`Keep one copy in each of ${plan.group_count} groups and ask Immich to merge metadata then trash ${plan.trash_asset_count} duplicate assets?`}
    confirmLabel="Resolve batch"
    icon="trash"
    destructive
    {busy}
    onconfirm={() => void executePlan()}
    onclose={() => { if (!busy) confirmOpen = false; }}
  />
{/if}

<style>
  .duplicates-page { display: grid; gap: 1.25rem; }
  .page-intro { display: grid; grid-template-columns: minmax(15rem, .75fr) minmax(18rem, 1fr); gap: 1.5rem; align-items: end; }
  .page-intro span { color: var(--color-accent-strong); font-size: .68rem; font-weight: 820; letter-spacing: .08em; text-transform: uppercase; }
  h1 { margin: .28rem 0 0; font-size: clamp(2rem, 5vw, 3.6rem); letter-spacing: -.055em; line-height: .98; }
  .page-intro p { max-width: 44rem; margin: 0; color: var(--color-ink-muted); line-height: 1.65; }
  .controls { display: grid; grid-template-columns: minmax(10rem, .7fr) minmax(16rem, 1.2fr) auto auto; gap: .8rem; align-items: end; padding: 1rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); box-shadow: var(--shadow-card); }
  label:not(.checkbox) { display: grid; gap: .35rem; color: var(--color-ink-muted); font-size: .72rem; font-weight: 760; }
  select, input, button { min-height: 2.45rem; padding: .5rem .7rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); font: inherit; }
  button { cursor: pointer; font-size: .75rem; font-weight: 780; }
  button:hover:not(:disabled) { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  button:disabled { cursor: default; opacity: .5; }
  button.primary { border-color: var(--color-accent-strong); color: var(--color-ink-inverse); background: var(--color-accent-strong); }
  .progress, .notice, .batch-bar, .summary, .empty { border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); }
  .progress { display: grid; gap: .6rem; padding: .8rem 1rem; }
  .progress div { display: flex; justify-content: space-between; gap: 1rem; font-size: .76rem; }
  progress { width: 100%; accent-color: var(--color-accent-strong); }
  .notice, .empty { margin: 0; padding: .8rem 1rem; color: var(--color-ink-muted); }
  .notice.error { color: var(--color-negative-ink); border-color: var(--color-negative-border); background: var(--color-negative-surface); }
  .notice.success { color: var(--color-positive-ink); border-color: var(--color-positive-border); background: var(--color-positive-surface); }
  .summary { display: grid; grid-template-columns: repeat(4, 1fr); overflow: hidden; }
  .summary div { display: grid; gap: .15rem; padding: .8rem 1rem; border-right: 1px solid var(--color-border-subtle); }
  .summary div:last-child { border: 0; }
  .summary strong { font-size: 1.3rem; }
  .summary span { color: var(--color-ink-muted); font-size: .7rem; }
  .batch-bar { position: sticky; z-index: 40; top: calc(var(--app-header-height) + .5rem); display: flex; min-height: 3.5rem; align-items: center; gap: .8rem; padding: .55rem .8rem; box-shadow: var(--shadow-card); }
  .batch-bar > span { margin-left: auto; color: var(--color-ink-muted); font-size: .74rem; }
  .groups { display: grid; gap: 1rem; }
  .group-card { overflow: hidden; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); box-shadow: var(--shadow-card); }
  .group-card.eligible { border-color: var(--color-positive-border); }
  .group-card > header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .75rem .9rem; border-bottom: 1px solid var(--color-border-subtle); }
  .group-card header p { margin: 0; color: var(--color-ink-muted); font-size: .73rem; text-align: right; }
  .group-heading { display: flex; align-items: center; gap: .65rem; }
  .group-heading > div { display: flex; align-items: center; gap: .55rem; white-space: nowrap; }
  .status { padding: .2rem .45rem; border-radius: 999px; background: var(--color-surface-soft); font-size: .62rem; font-weight: 800; text-transform: uppercase; }
  .status.exact { color: var(--color-positive-ink); background: var(--color-positive-surface); }
  .status.unverified { color: var(--color-warning-ink); background: var(--color-warning-surface); }
  .status.mismatch, .status.ineligible { color: var(--color-negative-ink); background: var(--color-negative-surface); }
  .members { display: grid; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); gap: .75rem; padding: .75rem; }
  .member { display: grid; grid-template-columns: 6rem minmax(0, 1fr); min-height: 6rem; overflow: hidden; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); background: var(--color-canvas); }
  .member.keeper { border-color: var(--color-accent-strong); box-shadow: inset 0 0 0 1px var(--color-accent-strong); }
  .member img { width: 6rem; height: 100%; min-height: 6rem; object-fit: cover; background: var(--color-surface-soft); }
  .member-body { display: grid; align-content: space-between; gap: .35rem; min-width: 0; padding: .55rem; }
  .member-title { display: grid; gap: .1rem; min-width: 0; }
  .member-title strong { overflow: hidden; font-size: .72rem; text-overflow: ellipsis; white-space: nowrap; }
  .member-title span { color: var(--color-accent-strong); font-size: .6rem; font-weight: 800; text-transform: uppercase; }
  small { color: var(--color-ink-muted); font-size: .63rem; }
  .member-actions { display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; }
  .member-actions button, .member-actions a { min-height: 1.8rem; padding: .3rem .45rem; font-size: .62rem; }
  .member-actions button[aria-pressed='true'] { border-color: var(--color-accent-strong); color: var(--color-ink-inverse); background: var(--color-accent-strong); }
  .member-actions a { display: inline-flex; align-items: center; color: var(--color-accent-strong); font-weight: 760; text-decoration: none; }
  @media (max-width: 58rem) { .controls { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 46rem) { .page-intro, .controls { grid-template-columns: 1fr; } .summary { grid-template-columns: 1fr 1fr; } .group-card > header { align-items: flex-start; flex-direction: column; } .group-card header p { text-align: left; } }
</style>

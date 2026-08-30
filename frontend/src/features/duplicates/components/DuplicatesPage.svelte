<script lang="ts">
  import { onMount } from 'svelte';
  import { SvelteSet } from 'svelte/reactivity';

  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import type { SelectOption } from '../../../lib/types/ui';
  import GroupEvidencePills from './GroupEvidencePills.svelte';
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
    DuplicatePlanAction,
    DuplicateResolutionPlan,
    DuplicateResult,
    DuplicateTaskStatus,
    DuplicateMember,
    DuplicatePreviewRequest,
    ExactDuplicateGroup,
  } from '../types/duplicates';

  interface Props {
    onpreview: (request: DuplicatePreviewRequest) => void;
  }

  let { onpreview }: Props = $props();

  const terminalStatuses = new Set(['completed', 'failed', 'cancelled']);
  const keeperPolicyOptions: SelectOption[] = [
    { value: 'most_recent', label: 'Most recently uploaded' },
    { value: 'prefer_upload', label: 'Prefer uploads' },
    { value: 'prefer_external', label: 'Prefer external files' },
    { value: 'first', label: 'First Immich result' },
  ];
  const defaultOptions: DuplicateAnalysisOptions = {
    keeper_policy: 'most_recent',
    external_library_ids: [],
    verify_upload_streams: false,
  };

  let result = $state.raw<DuplicateResult | null>(null);
  let options = $state<DuplicateAnalysisOptions>({ ...defaultOptions });
  let appliedOptions = $state.raw<DuplicateAnalysisOptions>({ ...defaultOptions });
  let libraryFilter = $state('');
  const selected = new SvelteSet<string>();
  let keeperOverrides = $state<Record<string, string>>({});
  let actionOverrides = $state<Record<string, DuplicatePlanAction>>({});
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let message = $state<string | null>(null);
  let task = $state.raw<DuplicateTaskStatus | null>(null);
  let plan = $state.raw<DuplicateResolutionPlan | null>(null);
  let confirmOpen = $state(false);
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let selectionInitialized = false;

  const autoReadyGroups = $derived(result?.groups.filter((group) => group.auto_selected) ?? []);
  const selectedCount = $derived(selected.size);
  const allAutoReadySelected = $derived(
    autoReadyGroups.length > 0
      && autoReadyGroups.every((group) => selected.has(group.duplicate_id)),
  );
  const rulesChanged = $derived(
    JSON.stringify(configuredOptions()) !== JSON.stringify(appliedOptions),
  );

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
      const loaded = await loadDuplicateGroups(appliedOptions);
      result = loaded;
      const eligibleIds = new SvelteSet(result.groups
        .filter((group) => isActionable(group))
        .map((group) => group.duplicate_id));
      for (const id of selected) if (!eligibleIds.has(id)) selected.delete(id);
      if (!selectionInitialized) {
        for (const group of result.groups) if (group.auto_selected) selected.add(group.duplicate_id);
        selectionInitialized = true;
      }
      if (
        loaded.analysis_task_id
        && (task?.id !== loaded.analysis_task_id || terminalStatuses.has(task.status))
      ) {
        task = await loadDuplicateTask(loaded.analysis_task_id);
        if (!terminalStatuses.has(task.status)) {
          busy = true;
          schedulePoll(task.id, 'analysis');
        }
      }
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
        selectionInitialized = false;
        keeperOverrides = {};
        actionOverrides = {};
        await load();
      } else {
        error = task.error?.message ?? `${kind === 'analysis' ? 'Analysis' : 'Resolution'} failed.`;
      }
    } catch (reason) {
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not read task progress.';
    }
  }

  function toggleGroup(groupId: string, checked: boolean): void {
    if (checked) selected.add(groupId);
    else selected.delete(groupId);
  }

  function toggleAllEligible(): void {
    if (allAutoReadySelected) {
      for (const group of autoReadyGroups) selected.delete(group.duplicate_id);
      return;
    }
    for (const group of autoReadyGroups) {
      actionOverrides = { ...actionOverrides, [group.duplicate_id]: 'resolve' };
      selected.add(group.duplicate_id);
    }
  }

  function setKeeper(group: ExactDuplicateGroup, assetId: string): void {
    keeperOverrides = { ...keeperOverrides, [group.duplicate_id]: assetId };
    if (group.eligible && !actionOverrides[group.duplicate_id]) {
      actionOverrides = { ...actionOverrides, [group.duplicate_id]: 'resolve' };
      selected.add(group.duplicate_id);
    } else if (actionFor(group) !== 'none') {
      selected.add(group.duplicate_id);
    }
  }

  function selectedKeeper(group: ExactDuplicateGroup): string | null {
    return keeperOverrides[group.duplicate_id] ?? group.keeper_asset_id;
  }

  function actionFor(group: ExactDuplicateGroup): DuplicatePlanAction {
    return actionOverrides[group.duplicate_id] ?? (group.auto_selected ? 'resolve' : 'none');
  }

  function isActionable(group: ExactDuplicateGroup): boolean {
    const action = actionFor(group);
    return action !== 'none'
      && selectedKeeper(group) !== null
      && !group.members.some((member) => member.is_offline)
      && (action !== 'resolve' || group.eligible)
      && (action !== 'stack_all' || !group.members.some((member) => member.is_stacked));
  }

  function actionOptions(group: ExactDuplicateGroup): SelectOption[] {
    return [
      { value: 'none', label: 'Skip / review later' },
      { value: 'resolve', label: 'Resolve — keep primary', disabled: !group.eligible },
      {
        value: 'stack_all',
        label: 'Stack all — keep every copy',
        disabled: group.members.some((member) => member.is_offline || member.is_stacked),
      },
    ];
  }

  function setGroupAction(group: ExactDuplicateGroup, value: string): void {
    const action = value as DuplicatePlanAction;
    if (action === 'none') {
      actionOverrides = { ...actionOverrides, [group.duplicate_id]: 'none' };
      selected.delete(group.duplicate_id);
      return;
    }
    actionOverrides = { ...actionOverrides, [group.duplicate_id]: action };
    if (isActionable(group)) selected.add(group.duplicate_id);
    else selected.delete(group.duplicate_id);
  }

  function progressPercent(status: DuplicateTaskStatus): number | undefined {
    if (typeof status.progress.percent !== 'number') return undefined;
    return Math.min(100, Math.max(0, status.progress.percent));
  }

  function previewRequest(group: ExactDuplicateGroup, initialIndex: number): DuplicatePreviewRequest {
    return {
      duplicate_id: group.duplicate_id,
      status: group.status,
      reason: group.reason,
      eligible: group.eligible,
      keeper_policy: appliedOptions.keeper_policy,
      recommended_keeper_asset_id: group.keeper_asset_id,
      selected_keeper_asset_id: selectedKeeper(group),
      selected_action: actionFor(group),
      recommendation_reason_codes: group.recommendation_reason_codes,
      members: group.members,
      initial_index: initialIndex,
      onkeeperchange: (assetId) => {
        setKeeper(group, assetId);
        return actionFor(group);
      },
      onactionchange: (action) => setGroupAction(group, action),
    };
  }

  async function reviewBatch(): Promise<void> {
    if (!selected.size) return;
    busy = true;
    error = null;
    message = null;
    try {
      plan = await planDuplicateResolution({
        options: appliedOptions,
        duplicate_ids: [...selected],
        all_eligible: false,
        keeper_overrides: keeperOverrides,
        action_overrides: Object.fromEntries(
          result?.groups
            .filter((group) => selected.has(group.duplicate_id))
            .map((group) => [group.duplicate_id, actionFor(group)]) ?? [],
        ) as Record<string, Exclude<DuplicatePlanAction, 'none'>>,
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
  }

  async function applyRules(): Promise<void> {
    const nextOptions = configuredOptions();
    busy = true;
    error = null;
    message = null;
    appliedOptions = nextOptions;
    keeperOverrides = {};
    actionOverrides = {};
    selected.clear();
    selectionInitialized = false;
    try {
      const started = await analyzeDuplicateGroups(nextOptions);
      task = await loadDuplicateTask(started.task_id);
      schedulePoll(started.task_id, 'analysis');
    } catch (reason) {
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not apply duplicate rules.';
    }
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
    <SelectField
      id="duplicate-keeper-policy"
      label="Keeper rule"
      value={options.keeper_policy}
      options={keeperPolicyOptions}
      disabled={busy}
      onchange={setPolicy}
    />
    <label class="library-filter">External library IDs <input value={libraryFilter} oninput={(event) => libraryFilter = event.currentTarget.value} placeholder="Optional, comma-separated" disabled={busy} /></label>
    <Checkbox checked={options.verify_upload_streams} label="Verify upload streams too" variant="switch" disabled={busy} onchange={(checked) => options.verify_upload_streams = checked} />
    <button class="apply-rules" type="button" disabled={busy || loading} onclick={() => void applyRules()}>Apply automatic rules</button>
    <div class="analysis-state">
      <span>Candidate analysis</span>
      <strong>{rulesChanged ? 'Rules changed' : result?.analysis_pending_count ? `${result.analysis_pending_count} queued` : loading ? 'Checking…' : 'Current'}</strong>
    </div>
  </section>

  {#if task && !terminalStatuses.has(task.status)}
    <section class="progress" aria-live="polite">
      <div><strong>{task.progress.detail ?? 'Processing duplicate candidates…'}</strong><span>{task.progress.total ? `${task.progress.completed ?? 0} / ${task.progress.total}` : 'Preparing…'}{progressPercent(task) !== undefined ? ` · ${Math.round(progressPercent(task) ?? 0)}%` : ''}</span></div>
      <progress value={progressPercent(task)} max="100"></progress>
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
      <Checkbox checked={allAutoReadySelected} label="Select all auto-ready groups" shape="circle" disabled={!autoReadyGroups.length || busy} onchange={toggleAllEligible} />
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
                <Checkbox checked={selected.has(group.duplicate_id)} label={`Select duplicate group ${group.duplicate_id}`} hiddenLabel shape="circle" disabled={!isActionable(group) || busy} onchange={(checked) => toggleGroup(group.duplicate_id, checked)} />
                <div><strong>{group.members.length} copies</strong><span class={`status ${group.status}`}>{group.status}</span><span class="workflow-status">{actionFor(group) === 'resolve' ? 'Will resolve' : actionFor(group) === 'stack_all' ? 'Will stack' : group.eligible ? 'Choose action' : 'Needs review'}</span></div>
              </div>
              <div class="group-controls">
                <SelectField id={`duplicate-action-${group.duplicate_id}`} label="Group action" value={actionFor(group)} options={actionOptions(group)} compact disabled={busy} onchange={(value) => setGroupAction(group, value)} />
                <p>{group.reason}</p>
              </div>
            </header>
            <div class="members">
              {#each group.members as member, memberIndex (member.id)}
                <div class:keeper={selectedKeeper(group) === member.id} class="member">
                  <div class="member-image">
                    <button class="preview-button" type="button" aria-label={`Preview ${member.original_file_name}`} onclick={() => onpreview(previewRequest(group, memberIndex))}>
                      <img src={`/api/assets/${encodeURIComponent(member.id)}/thumbnail`} alt="" loading="lazy" />
                    </button>
                    <button class="keeper-button" type="button" class:active={selectedKeeper(group) === member.id} disabled={busy} aria-pressed={selectedKeeper(group) === member.id} aria-label={selectedKeeper(group) === member.id ? `${member.original_file_name} is the keeper` : `Choose ${member.original_file_name} as the manual keeper`} onclick={() => setKeeper(group, member.id)}><Icon name="star" size=".92rem" /></button>
                    <button class="view-button" type="button" aria-label={`View complete details for ${member.original_file_name}`} onclick={() => onpreview(previewRequest(group, memberIndex))}><Icon name="view" size=".95rem" /></button>
                    {#if selectedKeeper(group) === member.id}<span class="keeper-label">Keeper</span>{/if}
                  </div>
                  <div class="member-body">
                    <strong title={member.original_file_name}>{member.original_file_name}</strong>
                    <span class={`source-kind ${member.source_kind}`}>{member.source_kind === 'upload' ? 'Immich upload' : 'External library'}</span>
                    {#if member.library_id}<small class="library-id" title={member.library_id}>{member.library_id}</small>{/if}
                    <GroupEvidencePills {member} analysisPending={result.analysis_task_id !== null && member.evidence.analysis_freshness !== 'current'} />
                    <small>{formatSize(member.file_size_bytes)}</small>
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
    title="Process reviewed duplicates"
    message={`Process ${plan.group_count} groups: resolve ${plan.resolve_group_count}, create ${plan.stack_group_count} stacks, and trash ${plan.trash_asset_count} exact duplicate assets?`}
    confirmLabel="Process batch"
    icon={plan.destructive ? 'trash' : 'stack'}
    destructive={plan.destructive}
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
  .controls { display: grid; grid-template-columns: minmax(10rem, .7fr) minmax(16rem, 1.2fr) auto auto minmax(7rem, auto); gap: .8rem; align-items: end; padding: 1rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); box-shadow: var(--shadow-card); }
  .apply-rules { color: var(--color-ink-inverse); border-color: var(--color-accent-strong); background: var(--color-accent-strong); }
  .apply-rules:hover:not(:disabled) { color: var(--color-ink-inverse); border-color: var(--color-accent-strong); background: color-mix(in srgb, var(--color-accent-strong) 88%, black); }
  .analysis-state { display: grid; min-height: 2.45rem; align-content: center; gap: .12rem; padding: .35rem .65rem; border-left: 1px solid var(--color-border-subtle); }
  .analysis-state span { color: var(--color-ink-muted); font-size: .62rem; font-weight: 760; }
  .analysis-state strong { font-size: .72rem; }
  label:not(.checkbox) { display: grid; gap: .35rem; color: var(--color-ink-muted); font-size: .72rem; font-weight: 760; }
  input, button { min-height: 2.45rem; padding: .5rem .7rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); font: inherit; }
  button { cursor: pointer; font-size: .75rem; font-weight: 780; }
  button:hover:not(:disabled) { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  button:disabled { cursor: default; opacity: .5; }
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
  .group-controls { display: flex; min-width: min(100%, 31rem); align-items: end; justify-content: flex-end; gap: .75rem; }
  .group-controls > :global(.select-field) { min-width: 12.5rem; }
  .group-heading { display: flex; align-items: center; gap: .65rem; }
  .group-heading > div { display: flex; align-items: center; gap: .55rem; white-space: nowrap; }
  .status { padding: .2rem .45rem; border-radius: 999px; background: var(--color-surface-soft); font-size: .62rem; font-weight: 800; text-transform: uppercase; }
  .status.exact { color: var(--color-positive-ink); background: var(--color-positive-surface); }
  .status.unverified { color: var(--color-warning-ink); background: var(--color-warning-surface); }
  .status.mismatch, .status.ineligible { color: var(--color-negative-ink); background: var(--color-negative-surface); }
  .workflow-status { color: var(--color-ink-muted); font-size: .6rem; font-weight: 760; }
  .members { display: grid; grid-template-columns: repeat(auto-fill, minmax(11.5rem, 1fr)); gap: .75rem; padding: .75rem; }
  .member { display: grid; min-width: 0; overflow: hidden; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); background: var(--color-canvas); }
  .member.keeper { border-color: var(--color-accent-strong); box-shadow: inset 0 0 0 1px var(--color-accent-strong); }
  .member-image { position: relative; aspect-ratio: 1; overflow: hidden; background: var(--color-surface-soft); }
  .preview-button { display: block; width: 100%; height: 100%; min-height: 0; padding: 0; border: 0; border-radius: 0; background: transparent; }
  .preview-button img { display: block; width: 100%; height: 100%; object-fit: cover; transition: transform .18s ease; }
  .preview-button:hover img { transform: scale(1.025); }
  .keeper-button, .view-button { position: absolute; top: .45rem; display: grid; width: 2rem; height: 2rem; min-height: 0; padding: 0; place-items: center; border: 1px solid rgb(255 255 255 / .4); border-radius: 999px; color: white; background: rgb(12 16 18 / .72); box-shadow: 0 2px 8px rgb(0 0 0 / .28); backdrop-filter: blur(5px); }
  .keeper-button { left: .45rem; } .view-button { right: .45rem; }
  .keeper-button.active { border-color: var(--color-accent-strong); color: var(--color-ink-inverse); background: var(--color-accent-strong); }
  .keeper-label { position: absolute; bottom: .45rem; left: .45rem; padding: .2rem .42rem; border-radius: 999px; color: white; background: rgb(12 16 18 / .76); font-size: .58rem; font-weight: 820; text-transform: uppercase; }
  .member-body { display: grid; gap: .28rem; min-width: 0; padding: .6rem; }
  .member-body strong { overflow: hidden; font-size: .7rem; text-overflow: ellipsis; white-space: nowrap; }
  .source-kind { width: fit-content; padding: .16rem .38rem; border-radius: 999px; color: var(--color-accent-strong); background: var(--color-surface-soft); font-size: .57rem; font-weight: 820; text-transform: uppercase; }
  .source-kind.external { color: var(--color-warning-ink); background: var(--color-warning-surface); }
  .library-id { overflow: hidden; font-family: ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }
  small { color: var(--color-ink-muted); font-size: .63rem; }
  @media (max-width: 58rem) { .controls { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 46rem) { .page-intro, .controls { grid-template-columns: 1fr; } .summary { grid-template-columns: 1fr 1fr; } .group-card > header, .group-controls { align-items: stretch; flex-direction: column; } .group-card header p { text-align: left; } }
</style>

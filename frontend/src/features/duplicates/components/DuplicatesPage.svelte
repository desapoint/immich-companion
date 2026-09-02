<script lang="ts">
  import { onMount } from 'svelte';
  import { SvelteMap, SvelteSet } from 'svelte/reactivity';

  import Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import DuplicateDispositionControls from '../../../lib/components/domain/DuplicateDispositionControls.svelte';
  import StackPrimaryControl from '../../../lib/components/domain/StackPrimaryControl.svelte';
  import Icon from '../../../lib/components/ui/Icon.svelte';
  import MultiSelectField from '../../../lib/components/ui/MultiSelectField.svelte';
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import { loadDuplicatePolicy, loadImmichLibraries, saveDuplicatePolicy } from '../../../lib/api/duplicatePolicyApi';
  import type { SelectOption } from '../../../lib/types/ui';
  import { resolveStackPrimary } from '../../../lib/utils/duplicateReview';
  import GroupEvidencePills from './GroupEvidencePills.svelte';
  import DuplicateReviewFilters from './DuplicateReviewFilters.svelte';
  import {
    analyzeDuplicateGroups,
    applyDuplicateRules,
    cancelDuplicateTask,
    executeDuplicateResolution,
    loadDuplicateGroups,
    loadDuplicateWorkspace,
    loadDuplicateTask,
    loadLatestSimilarityScan,
    loadSimilarityScanTasks,
    planDuplicateResolution,
    resetDuplicateWorkspaceDecisions,
    saveDuplicateGroupDraft,
    saveDuplicateWorkspaceSelection,
    startDuplicateSimilarityScan,
    switchDuplicateSimilarityReference,
  } from '../api/duplicateApi';
  import type {
    DuplicateAnalysisOptions,
    DuplicateActionSelection,
    DuplicateDisposition,
    DuplicateGroupDraft,
    DuplicateKeeperPolicy,
    DuplicatePlanAction,
    DuplicateResolutionPlan,
    DuplicateResult,
    DuplicateTaskStatus,
    DuplicateMember,
    DuplicatePreviewRequest,
    DuplicateWorkspaceState,
    ExactDuplicateGroup,
    SimilarityScanSummary,
  } from '../types/duplicates';
  import {
    countDuplicateReviewFilters,
    duplicateGroupMatchesFilter,
    duplicateWorkflowLabel,
    type DuplicateReviewFilter,
    type DuplicateReviewProjection,
  } from '../state/duplicateReviewFilters';

  interface Props {
    onpreview: (request: DuplicatePreviewRequest) => void;
  }

  let { onpreview }: Props = $props();

  const terminalStatuses = new Set(['completed', 'failed', 'cancelled']);
  const draftSaveDelayMs = 250;
  const keeperPolicyOptions: SelectOption[] = [
    { value: 'most_recent', label: 'Most recently uploaded' },
    { value: 'prefer_upload', label: 'Prefer uploads' },
    { value: 'prefer_external', label: 'Prefer external files' },
    { value: 'first', label: 'First Immich result' },
  ];
  const exactActionOptions: SelectOption[] = [
    { value: 'resolve', label: 'Resolve exact files' },
    { value: 'keep_all', label: 'Keep all exact copies' },
    { value: 'stack_all', label: 'Stack exact copies' },
    { value: 'review', label: 'Always review' },
  ];
  const bulkActionOptions: SelectOption[] = [
    { value: 'keep_all', label: 'Keep all copies' },
    { value: 'delete_all', label: 'Delete every copy' },
    { value: 'stack_all', label: 'Stack each group' },
  ];
  const defaultOptions: DuplicateAnalysisOptions = {
    keeper_policy: 'prefer_upload',
    external_library_ids: [],
    verify_upload_streams: false,
    automatic_handling_enabled: true,
    preselect_safe_groups: true,
    exact_file_action: 'resolve',
    analyze_automatically: true,
  };

  let result = $state.raw<DuplicateResult | null>(null);
  let options = $state<DuplicateAnalysisOptions>({ ...defaultOptions });
  let appliedOptions = $state.raw<DuplicateAnalysisOptions>({ ...defaultOptions });
  let libraryOptions = $state<SelectOption[]>([]);
  let bulkAction = $state<DuplicatePlanAction>('keep_all');
  const selected = new SvelteSet<string>();
  let groupDrafts = $state.raw<Record<string, DuplicateGroupDraft>>({});
  let workspace = $state.raw<DuplicateWorkspaceState | null>(null);
  let activeGroupId = $state<string | null>(null);
  const savingGroups = new SvelteSet<string>();
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let message = $state<string | null>(null);
  let task = $state.raw<DuplicateTaskStatus | null>(null);
  let latestScan = $state.raw<SimilarityScanSummary | null>(null);
  let similarityThreshold = $state(95);
  let plan = $state.raw<DuplicateResolutionPlan | null>(null);
  let confirmOpen = $state(false);
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let workspaceSaveQueue = Promise.resolve();
  const draftSaveQueues = new SvelteMap<string, Promise<void>>();
  const draftSaveTimers = new SvelteMap<string, ReturnType<typeof setTimeout>>();
  const pendingDrafts = new SvelteMap<string, { group: ExactDuplicateGroup; draft: DuplicateGroupDraft }>();
  let selectionInitialized = false;
  let applyRulesAfterAnalysis = false;
  const pendingRuleApplicationTaskKey = 'immich-companion:duplicates:pending-rule-application-task';
  let activeFilter = $state<DuplicateReviewFilter>('all');

  const autoReadyGroups = $derived(
    result?.groups.filter(
      (group) => group.auto_selected && group.manual_action === null && group.review_status === 'pending',
    ) ?? [],
  );
  const selectedGroups = $derived(
    result?.groups.filter((group) => selected.has(group.group_id)) ?? [],
  );
  const selectedCount = $derived(selectedGroups.length);
  const selectedReady = $derived(
    selectedGroups.length > 0 && selectedGroups.every((group) => isActionable(group)),
  );
  const allAutoReadySelected = $derived(
    autoReadyGroups.length > 0
      && autoReadyGroups.every((group) => selected.has(group.group_id)),
  );
  const rulesChanged = $derived(
    JSON.stringify(configuredOptions()) !== JSON.stringify(appliedOptions),
  );
  const reviewEntries = $derived.by<DuplicateReviewProjection[]>(() => {
    const loaded = result;
    if (!loaded) return [];
    return loaded.groups.map((group) => ({
      group,
      effectiveAction: effectiveActionFor(group),
      actionable: isActionable(group),
      analysisPending: loaded.analysis_pending_count > 0,
    }));
  });
  const reviewFilterCounts = $derived(countDuplicateReviewFilters(reviewEntries));
  const visibleReviewEntries = $derived(
    reviewEntries.filter((entry) => duplicateGroupMatchesFilter(entry, activeFilter)),
  );
  const resumableIncompleteWork = $derived(
    task?.status === 'failed'
      && (
        (Array.isArray(task.result?.summary?.follow_up_pending_group_ids)
          && task.result.summary.follow_up_pending_group_ids.length > 0)
        || (Array.isArray(task.result?.summary?.failed_group_ids)
          && task.result.summary.failed_group_ids.length > 0)
      ),
  );

  function configuredOptions(): DuplicateAnalysisOptions {
    return { ...options };
  }

  async function load(): Promise<void> {
    loading = true;
    error = null;
    try {
      const [loaded, latest, scanTasks] = await Promise.all([
        loadDuplicateGroups(appliedOptions),
        loadLatestSimilarityScan(),
        loadSimilarityScanTasks(),
      ]);
      result = loaded;
      latestScan = latest;
      const restored = await loadDuplicateWorkspace();
      workspace = restored;
      groupDrafts = Object.fromEntries(restored.drafts.map((draft) => [draft.group_id, draft]));
      const liveIds = new SvelteSet(result.groups.map((group) => group.group_id));
      for (const id of selected) if (!liveIds.has(id)) selected.delete(id);
      if (!selectionInitialized) {
        selected.clear();
        if (restored.initialized) {
          for (const groupId of restored.selected_group_ids) selected.add(groupId);
          activeGroupId = restored.active_group_id;
        } else {
          for (const group of autoReadyGroups) selected.add(group.group_id);
          if (selected.size) void persistWorkspace();
        }
        selectionInitialized = true;
      }
      const activeScan = scanTasks.find((candidate) => !terminalStatuses.has(candidate.status));
      if (activeScan) {
        task = activeScan;
        busy = true;
        schedulePoll(activeScan.id, 'similarity');
      } else if (
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

  type DuplicateTaskKind = 'analysis' | 'similarity' | 'resolution';

  function schedulePoll(taskId: string, kind: DuplicateTaskKind): void {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = setTimeout(() => void pollTask(taskId, kind), 700);
  }

  async function pollTask(taskId: string, kind: DuplicateTaskKind): Promise<void> {
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
          : kind === 'similarity'
            ? 'The visual similarity scan completed and its matches are ready to review.'
            : 'The reviewed duplicate batch completed.';
        if (kind === 'analysis') {
          selected.clear();
          selectionInitialized = false;
          groupDrafts = {};
        }
        await load();
        const shouldApplyRules = kind === 'analysis' && (
          applyRulesAfterAnalysis
          || localStorage.getItem(pendingRuleApplicationTaskKey) === taskId
        );
        if (shouldApplyRules) {
          applyRulesAfterAnalysis = false;
          await persistAutomaticRules();
          localStorage.removeItem(pendingRuleApplicationTaskKey);
          message = 'Duplicate candidates were verified and safe automatic rules were applied.';
        }
      } else if (task.status === 'cancelled' && kind === 'similarity') {
        message = 'Similarity scan cancelled. The last completed scan remains active.';
        await load();
      } else {
        if (kind === 'analysis') {
          applyRulesAfterAnalysis = false;
          localStorage.removeItem(pendingRuleApplicationTaskKey);
        }
        error = task.error?.message ?? `${kind === 'analysis' ? 'Analysis' : kind === 'similarity' ? 'Similarity scan' : 'Resolution'} failed.`;
        if (kind === 'resolution') await load();
      }
    } catch (reason) {
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not read task progress.';
    }
  }

  function toggleGroup(groupId: string, checked: boolean): void {
    if (checked) selected.add(groupId);
    else selected.delete(groupId);
    void persistWorkspace();
  }

  function toggleAllEligible(): void {
    if (allAutoReadySelected) {
      for (const group of autoReadyGroups) selected.delete(group.group_id);
      void persistWorkspace();
      return;
    }
    for (const group of autoReadyGroups) {
      selected.add(group.group_id);
    }
    void persistWorkspace();
  }

  function persistWorkspace(): void {
    const request = {
      options: { ...appliedOptions },
      selected_group_ids: [...selected],
      active_group_id: activeGroupId,
    };
    workspaceSaveQueue = workspaceSaveQueue.catch(() => undefined).then(async () => {
      try {
        workspace = await saveDuplicateWorkspaceSelection({
          ...request,
          selected_group_ids: request.selected_group_ids,
        });
      } catch (reason) {
        error = reason instanceof Error ? reason.message : 'Could not save duplicate selection.';
      }
    });
  }

  function draftFor(group: ExactDuplicateGroup): DuplicateGroupDraft | null {
    const draft = groupDrafts[group.group_id];
    return draft && !draft.stale && draft.member_fingerprint === group.member_fingerprint
      ? draft
      : null;
  }

  function rawDraftFor(group: ExactDuplicateGroup): DuplicateGroupDraft | null {
    return groupDrafts[group.group_id] ?? null;
  }

  function restoreWorkspaceState(restored: DuplicateWorkspaceState): void {
    workspace = restored;
    groupDrafts = Object.fromEntries(restored.drafts.map((draft) => [draft.group_id, draft]));
    selected.clear();
    for (const groupId of restored.selected_group_ids) selected.add(groupId);
    activeGroupId = restored.active_group_id;
    selectionInitialized = true;
  }

  function dispositionFor(group: ExactDuplicateGroup, assetId: string): DuplicateDisposition | null {
    return draftFor(group)?.decisions.find((decision) => decision.asset_id === assetId)?.disposition ?? null;
  }

  function selectedKeeper(group: ExactDuplicateGroup): string | null {
    const draft = draftFor(group);
    if (draft?.stack_primary_asset_id) return draft.stack_primary_asset_id;
    const kept = draft?.decisions.filter((decision) => decision.disposition === 'keep') ?? [];
    if (kept.length === 1) return kept[0].asset_id;
    return group.effective_primary_asset_id ?? group.keeper_asset_id;
  }

  function actionFor(group: ExactDuplicateGroup): DuplicateActionSelection {
    const draft = draftFor(group);
    if (!draft?.decisions.length) return 'automatic';
    if (draft.decisions.length !== group.members.length) return 'none';
    const values = new Set(draft.decisions.map((decision) => decision.disposition));
    if (values.size === 1) {
      const disposition = draft.decisions[0].disposition;
      return disposition === 'keep' ? 'keep_all' : disposition === 'delete' ? 'delete_all' : 'stack_all';
    }
    const keepCount = draft.decisions.filter((decision) => decision.disposition === 'keep').length;
    const deleteCount = draft.decisions.filter((decision) => decision.disposition === 'delete').length;
    return keepCount === 1 && deleteCount === group.members.length - 1 ? 'resolve' : 'mixed';
  }

  function effectiveActionFor(group: ExactDuplicateGroup): DuplicatePlanAction {
    const selection = actionFor(group);
    return selection === 'automatic' ? group.recommended_action : selection;
  }

  function isActionable(group: ExactDuplicateGroup): boolean {
    const action = effectiveActionFor(group);
    const draft = draftFor(group);
    const hasDraftDecisions = (draft?.decisions.length ?? 0) > 0;
    const draftComplete = draft?.decisions.length === group.members.length;
    const stackDecisions = draft?.decisions.filter((decision) => decision.disposition === 'stack') ?? [];
    const hasDeletions = draft?.decisions.some((decision) => decision.disposition === 'delete')
      ?? (action === 'resolve' || action === 'delete_all');
    const requiresPrimary = action === 'resolve' || action === 'stack_all' || stackDecisions.length > 0;
    return action !== 'none'
      && (!hasDraftDecisions || draftComplete)
      && (!requiresPrimary || selectedKeeper(group) !== null)
      && stackDecisions.length !== 1
      && (!hasDeletions || action === 'delete_all' || (group.eligible && !group.members.some((member) => member.is_offline)))
      && (!stackDecisions.length || !group.members.some((member) => (
        stackDecisions.some((decision) => decision.asset_id === member.id)
        && (member.is_offline || member.is_stacked)
      )));
  }

  function sameDraftState(left: DuplicateGroupDraft | null, right: DuplicateGroupDraft): boolean {
    return left !== null
      && left.member_fingerprint === right.member_fingerprint
      && left.stack_primary_asset_id === right.stack_primary_asset_id
      && left.metadata_keeper_asset_id === right.metadata_keeper_asset_id
      && left.status === right.status
      && JSON.stringify(left.decisions) === JSON.stringify(right.decisions);
  }

  async function persistDraft(group: ExactDuplicateGroup, draft: DuplicateGroupDraft): Promise<void> {
    savingGroups.add(group.group_id);
    error = null;
    try {
      const updated = await saveDuplicateGroupDraft({
        group_id: group.group_id,
        member_fingerprint: group.member_fingerprint,
        options: appliedOptions,
        decisions: draft.decisions,
        stack_primary_asset_id: draft.stack_primary_asset_id,
        metadata_keeper_asset_id: draft.metadata_keeper_asset_id,
        status: draft.status,
      });
      if (sameDraftState(draftFor(group), draft)) {
        groupDrafts = { ...groupDrafts, [group.group_id]: updated };
      }
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not save the duplicate decision.';
    } finally {
      savingGroups.delete(group.group_id);
    }
  }

  function enqueueDraftPersistence(group: ExactDuplicateGroup, draft: DuplicateGroupDraft): Promise<void> {
    const previous = draftSaveQueues.get(group.group_id) ?? Promise.resolve();
    const next = previous.catch(() => undefined).then(() => persistDraft(group, draft));
    draftSaveQueues.set(group.group_id, next);
    void next.finally(() => {
      if (draftSaveQueues.get(group.group_id) === next) draftSaveQueues.delete(group.group_id);
    });
    return next;
  }

  function flushPendingDraft(groupId: string): Promise<void> | null {
    const timer = draftSaveTimers.get(groupId);
    if (timer) {
      clearTimeout(timer);
      draftSaveTimers.delete(groupId);
    }
    const pending = pendingDrafts.get(groupId);
    if (!pending) return draftSaveQueues.get(groupId) ?? null;
    pendingDrafts.delete(groupId);
    return enqueueDraftPersistence(pending.group, pending.draft);
  }

  async function flushDraftPersistence(groupIds: string[]): Promise<void> {
    const pending = groupIds
      .map((groupId) => flushPendingDraft(groupId))
      .filter((save): save is Promise<void> => save !== null);
    await Promise.all(pending);
  }

  function queueDraftPersistence(group: ExactDuplicateGroup, draft: DuplicateGroupDraft): void {
    pendingDrafts.set(group.group_id, { group, draft });
    const existingTimer = draftSaveTimers.get(group.group_id);
    if (existingTimer) clearTimeout(existingTimer);
    const timer = setTimeout(() => {
      draftSaveTimers.delete(group.group_id);
      void flushPendingDraft(group.group_id);
    }, draftSaveDelayMs);
    draftSaveTimers.set(group.group_id, timer);
  }

  function updateDraft(
    group: ExactDuplicateGroup,
    decisions: DuplicateGroupDraft['decisions'],
    stackPrimaryAssetId: string | null,
  ): void {
    const existing = draftFor(group);
    const stackIds = decisions
      .filter((decision) => decision.disposition === 'stack')
      .map((decision) => decision.asset_id);
    const resolvedPrimary = resolveStackPrimary(
      stackIds,
      stackPrimaryAssetId,
      [group.effective_primary_asset_id, group.keeper_asset_id],
    );
    const draft: DuplicateGroupDraft = {
      group_id: group.group_id,
      discovery_source: group.discovery_source,
      member_fingerprint: group.member_fingerprint,
      decisions,
      stack_primary_asset_id: resolvedPrimary,
      metadata_keeper_asset_id: existing?.metadata_keeper_asset_id ?? null,
      status: 'pending',
      stale: false,
    };
    groupDrafts = { ...groupDrafts, [group.group_id]: draft };
    const wasSelected = selected.has(group.group_id);
    selected.add(group.group_id);
    if (!wasSelected) void persistWorkspace();
    queueDraftPersistence(group, draft);
  }

  function setMemberDisposition(
    group: ExactDuplicateGroup,
    assetId: string,
    disposition: DuplicateDisposition,
  ): void {
    const existing = draftFor(group);
    const decisions = [...(existing?.decisions ?? [])];
    const index = decisions.findIndex((decision) => decision.asset_id === assetId);
    const next = { asset_id: assetId, disposition, source: 'manual' as const, status: 'pending' as const };
    if (index >= 0) decisions[index] = next;
    else decisions.push(next);
    const primary = disposition !== 'stack' && existing?.stack_primary_asset_id === assetId
      ? null
      : existing?.stack_primary_asset_id ?? null;
    updateDraft(group, decisions, primary);
  }

  function setStackPrimary(group: ExactDuplicateGroup, assetId: string): void {
    if (dispositionFor(group, assetId) !== 'stack') return;
    const draft = draftFor(group);
    if (!draft) return;
    updateDraft(group, draft.decisions, assetId);
  }

  function applyGroupPreset(group: ExactDuplicateGroup, disposition: DuplicateDisposition): void {
    updateDraft(
      group,
      group.members.map((member) => ({
        asset_id: member.id,
        disposition,
        source: 'manual',
        status: 'pending',
      })),
      disposition === 'stack' ? draftFor(group)?.stack_primary_asset_id ?? null : null,
    );
  }

  async function applyBulkAction(): Promise<void> {
    if (!result || !selected.size) return;
    busy = true;
    error = null;
    const groups = result.groups.filter((group) => selected.has(group.group_id));
    try {
      for (const group of groups) {
        if (bulkAction === 'keep_all') applyGroupPreset(group, 'keep');
        else if (bulkAction === 'delete_all') applyGroupPreset(group, 'delete');
        else if (bulkAction === 'stack_all') applyGroupPreset(group, 'stack');
      }
      if (bulkAction === 'none') selected.clear();
    } finally {
      busy = false;
    }
  }

  async function clearDecisions(groupIds: string[]): Promise<void> {
    if (!groupIds.length) return;
    busy = true;
    error = null;
    message = null;
    try {
      await flushDraftPersistence(groupIds);
      const restored = await resetDuplicateWorkspaceDecisions({
        options: appliedOptions,
        group_ids: groupIds,
      });
      restoreWorkspaceState(restored);
      message = groupIds.length === 1
        ? 'Saved decisions were cleared for this group.'
        : `Saved decisions were cleared for ${groupIds.length} groups.`;
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not clear saved decisions.';
    } finally {
      busy = false;
    }
  }

  async function dismissStaleSelection(): Promise<void> {
    try {
      const restored = await saveDuplicateWorkspaceSelection({
        options: appliedOptions,
        selected_group_ids: [...selected],
        active_group_id: activeGroupId,
      });
      restoreWorkspaceState(restored);
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not clear stale selection entries.';
    }
  }

  function progressPercent(status: DuplicateTaskStatus): number | undefined {
    if (typeof status.progress.percent !== 'number') return undefined;
    return Math.min(100, Math.max(0, status.progress.percent));
  }

  function previewRequest(group: ExactDuplicateGroup, initialIndex: number): DuplicatePreviewRequest {
    const groups = result?.groups ?? [];
    const groupIndex = groups.findIndex((candidate) => candidate.group_id === group.group_id);
    return {
      group_id: group.group_id,
      discovery_source: group.discovery_source,
      discovery_metadata: group.discovery_metadata ?? {},
      classification: group.classification,
      status: group.status,
      reason: group.reason,
      eligible: group.eligible,
      keeper_policy: appliedOptions.keeper_policy,
      recommended_keeper_asset_id: group.keeper_asset_id,
      selected_keeper_asset_id: selectedKeeper(group),
      selected_action: actionFor(group),
      member_decisions: Object.fromEntries(
        (draftFor(group)?.decisions ?? []).map((decision) => [decision.asset_id, decision.disposition]),
      ),
      stack_primary_asset_id: draftFor(group)?.stack_primary_asset_id ?? null,
      recommendation_reason_codes: group.recommendation_reason_codes,
      members: group.members,
      initial_index: initialIndex,
      onmemberdispositionchange: (assetId, disposition) => setMemberDisposition(group, assetId, disposition),
      onstackprimarychange: (assetId) => setStackPrimary(group, assetId),
      onsimilarityreferencechange: async (assetId) => {
        const updated = await switchDuplicateSimilarityReference(group.group_id, assetId);
        if (result) {
          result = {
            ...result,
            groups: result.groups.map((candidate) => (
              candidate.group_id === updated.group_id ? updated : candidate
            )),
          };
        }
        return updated.members;
      },
      onpreviousgroup: groupIndex > 0
        ? () => openPreview(groups[groupIndex - 1], 0)
        : undefined,
      onnextgroup: groupIndex >= 0 && groupIndex < groups.length - 1
        ? () => openPreview(groups[groupIndex + 1], 0)
        : undefined,
    };
  }

  function openPreview(group: ExactDuplicateGroup, index: number): void {
    activeGroupId = group.group_id;
    void persistWorkspace();
    onpreview(previewRequest(group, index));
  }

  async function reviewBatch(): Promise<void> {
    if (!selectedGroups.length) return;
    busy = true;
    error = null;
    message = null;
    const groupIds = selectedGroups.map((group) => group.group_id);
    try {
      await flushDraftPersistence(groupIds);
      await workspaceSaveQueue.catch(() => undefined);
      plan = await planDuplicateResolution({
        options: appliedOptions,
        group_ids: groupIds,
        all_eligible: false,
        keeper_overrides: Object.fromEntries(
          selectedGroups
            .filter((group) => selectedKeeper(group) !== null)
            .map((group) => [group.group_id, selectedKeeper(group)!]),
        ),
        action_overrides: Object.fromEntries(
          selectedGroups.map((group) => [group.group_id, effectiveActionFor(group)]),
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

  async function persistAutomaticRules(): Promise<void> {
    const restored = await applyDuplicateRules({
      ...appliedOptions,
      analyze_automatically: false,
    });
    restoreWorkspaceState(restored);
  }

  async function applyRules(): Promise<void> {
    const nextOptions = configuredOptions();
    busy = true;
    error = null;
    message = null;
    appliedOptions = nextOptions;
    try {
      await saveDuplicatePolicy({
        automatic_handling_enabled: nextOptions.automatic_handling_enabled,
        preselect_safe_groups: nextOptions.preselect_safe_groups,
        exact_file_action: nextOptions.exact_file_action,
        keeper_policy: nextOptions.keeper_policy,
        analyze_automatically: nextOptions.analyze_automatically,
        verify_upload_streams: nextOptions.verify_upload_streams,
        external_library_ids: nextOptions.external_library_ids,
        similarity_threshold_percent: similarityThreshold,
      });
      if (nextOptions.analyze_automatically) {
        applyRulesAfterAnalysis = true;
        const started = await analyzeDuplicateGroups(nextOptions);
        localStorage.setItem(pendingRuleApplicationTaskKey, started.task_id);
        task = await loadDuplicateTask(started.task_id);
        schedulePoll(started.task_id, 'analysis');
      } else {
        await load();
        await persistAutomaticRules();
        busy = false;
        message = 'Duplicate policy saved and safe automatic rules were applied.';
      }
    } catch (reason) {
      applyRulesAfterAnalysis = false;
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not apply duplicate rules.';
    }
  }

  async function scanForSimilarImages(): Promise<void> {
    busy = true;
    error = null;
    message = null;
    try {
      await saveDuplicatePolicy({
        ...appliedOptions,
        similarity_threshold_percent: similarityThreshold,
      });
      const started = await startDuplicateSimilarityScan(similarityThreshold);
      task = await loadDuplicateTask(started.task_id);
      schedulePoll(started.task_id, 'similarity');
    } catch (reason) {
      busy = false;
      error = reason instanceof Error ? reason.message : 'Could not start the similarity scan.';
    }
  }

  async function cancelSimilarityScan(): Promise<void> {
    if (!task || task.task_type !== 'similarity_scan') return;
    error = null;
    try {
      task = await cancelDuplicateTask(task.id);
      if (task.status === 'cancelled') {
        busy = false;
        message = 'Similarity scan cancelled. The last completed scan remains active.';
        await load();
      } else {
        schedulePoll(task.id, 'similarity');
      }
    } catch (reason) {
      error = reason instanceof Error ? reason.message : 'Could not cancel the similarity scan.';
    }
  }

  function discoveryLabel(group: ExactDuplicateGroup): string {
    if (group.discovery_source === 'immich_duplicate') return 'Immich duplicate';
    const score = group.discovery_metadata?.similarity_percent;
    return score ? `Companion scan · ${Number(score).toFixed(1)}%` : 'Companion similarity scan';
  }

  function formatSize(value: number | null): string {
    if (value === null) return 'Size unavailable';
    if (value < 1024) return `${value} B`;
    if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / 1024 ** 2).toFixed(1)} MB`;
  }

  onMount(() => {
    void (async () => {
      try {
        const [policy, libraries] = await Promise.all([
          loadDuplicatePolicy(),
          loadImmichLibraries(),
        ]);
        options = { ...policy };
        appliedOptions = { ...policy };
        similarityThreshold = policy.similarity_threshold_percent;
        libraryOptions = libraries.map((library) => ({
          value: library.id,
          label: `${library.name}${library.assetCount === null ? '' : ` · ${library.assetCount} assets`}`,
        }));
      } catch (reason) {
        error = reason instanceof Error ? reason.message : 'Could not load duplicate policy.';
      }
      await load();
    })();
    return () => {
      if (pollTimer) clearTimeout(pollTimer);
      for (const timer of draftSaveTimers.values()) clearTimeout(timer);
    };
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
    <SelectField id="duplicate-exact-policy" label="Exact-file default" value={options.exact_file_action} options={exactActionOptions} disabled={busy} onchange={(value) => options.exact_file_action = value as DuplicateAnalysisOptions['exact_file_action']} />
    <MultiSelectField id="duplicate-library-filter" label="External libraries" values={options.external_library_ids} options={libraryOptions} placeholder="All external libraries" searchable disabled={busy} onchange={(values) => options.external_library_ids = values} />
    <Checkbox checked={options.verify_upload_streams} label="Verify upload streams too" variant="switch" disabled={busy} onchange={(checked) => options.verify_upload_streams = checked} />
    <button class="apply-rules" type="button" disabled={busy || loading} onclick={() => void applyRules()}>Apply automatic rules</button>
    <div class="analysis-state">
      <span>Candidate analysis</span>
      <strong>{rulesChanged ? 'Rules changed' : result?.analysis_pending_count ? `${result.analysis_pending_count} queued` : loading ? 'Checking…' : result ? `${result.analysis_cached_count} cached` : 'Current'}</strong>
    </div>
  </section>

  <section class="similarity-controls" aria-labelledby="similarity-scan-title">
    <div class="similarity-copy">
      <span>Companion discovery</span>
      <strong id="similarity-scan-title">Similarity scan</strong>
      <small>Scope: all eligible assets. Similarity is review evidence, never permission to delete.</small>
    </div>
    <label for="similarity-threshold">
      <span>Minimum similarity</span>
      <input id="similarity-threshold" type="number" min="50" max="100" step="0.1" bind:value={similarityThreshold} disabled={busy} />
    </label>
    <button class="scan-similar" type="button" disabled={busy || loading || similarityThreshold < 50 || similarityThreshold > 100} onclick={() => void scanForSimilarImages()}><Icon name="integrity" size=".9rem" /> {latestScan ? 'Scan again' : 'Scan for similar images'}</button>
    {#if latestScan}
      <div class="last-scan">
        <span>Last completed</span>
        <strong>{latestScan.similarity_threshold.toFixed(1)}% · {latestScan.match_count} matches</strong>
        <small>{latestScan.asset_count} assets · model {latestScan.model_version} · {new Date(latestScan.completed_at).toLocaleString()}</small>
      </div>
    {/if}
  </section>

  {#if task && !terminalStatuses.has(task.status)}
    <section class="progress" aria-live="polite">
      <div><strong>{task.progress.detail ?? 'Processing duplicate candidates…'}</strong><span>{task.progress.total ? `${task.progress.completed ?? 0} / ${task.progress.total}` : 'Preparing…'}{progressPercent(task) !== undefined ? ` · ${Math.round(progressPercent(task) ?? 0)}%` : ''}</span></div>
      <progress value={progressPercent(task)} max="100"></progress>
      {#if task.task_type === 'similarity_scan'}<button class="cancel-scan" type="button" onclick={() => void cancelSimilarityScan()}>Cancel scan</button>{/if}
    </section>
  {/if}
  {#if error}
    <div class="notice error" role="alert">
      <span>{error}</span>
      {#if resumableIncompleteWork && plan}
        <button type="button" disabled={busy} onclick={() => void executePlan()}>Resume incomplete work</button>
      {/if}
    </div>
  {/if}
  {#if message}<p class="notice success" role="status">{message}</p>{/if}

  {#if result}
    <section class="summary" aria-label="Duplicate summary">
      <div><strong>{result.group_count}</strong><span>Review groups</span></div>
      <div><strong>{reviewFilterCounts.auto_ready}</strong><span>Auto ready</span></div>
      <div><strong>{reviewFilterCounts.resolve_ready}</strong><span>Resolve ready</span></div>
      <div><strong>{reviewFilterCounts.stack_ready}</strong><span>Stack ready</span></div>
      <div><strong>{reviewFilterCounts.needs_review}</strong><span>Needs review</span></div>
      <div><strong>{reviewFilterCounts.analyzing}</strong><span>Analyzing</span></div>
    </section>

    <DuplicateReviewFilters active={activeFilter} counts={reviewFilterCounts} disabled={loading} onchange={(filter) => activeFilter = filter} />

    {#if workspace?.stale_selected_groups.length}
      <div class="notice stale-workspace" role="status">
        <span>{workspace.stale_selected_groups.length} previously selected {workspace.stale_selected_groups.length === 1 ? 'group has' : 'groups have'} changed or disappeared and will not be executed.</span>
        <button type="button" disabled={busy} onclick={() => void dismissStaleSelection()}>Dismiss stale selection</button>
      </div>
    {/if}

    <div class="batch-bar">
      <Checkbox checked={allAutoReadySelected} label="Select all auto-ready groups" shape="circle" disabled={!autoReadyGroups.length || busy} onchange={toggleAllEligible} />
      <span>{selectedCount} selected</span>
      <SelectField id="duplicate-bulk-action" label="Apply to selected" value={bulkAction} options={bulkActionOptions} compact disabled={!selectedCount || busy} onchange={(value) => bulkAction = value as DuplicatePlanAction} />
      <button type="button" disabled={!selectedCount || busy} onclick={() => void applyBulkAction()}>Apply action</button>
      <button type="button" disabled={!selectedCount || busy} onclick={() => void clearDecisions(selectedGroups.map((group) => group.group_id))}>Clear selected decisions</button>
      <button type="button" disabled={!selectedReady || busy} onclick={() => void reviewBatch()}>Review batch</button>
    </div>

    {#if loading}
      <p class="empty">Refreshing duplicate groups…</p>
    {:else if !result.groups.length}
      <p class="empty">Immich currently reports no duplicate groups.</p>
    {:else if !visibleReviewEntries.length}
      <p class="empty">No duplicate groups match this review filter.</p>
    {:else}
      <div class="groups">
        {#each visibleReviewEntries as entry (entry.group.group_id)}
          {@const group = entry.group}
          <article class:eligible={group.eligible} class="group-card">
            <header>
              <div class="group-heading">
                <Checkbox checked={selected.has(group.group_id)} label={`Select duplicate group ${group.group_id}`} hiddenLabel shape="circle" disabled={busy} onchange={(checked) => toggleGroup(group.group_id, checked)} />
                <div><strong>{group.members.length} copies</strong><span class={`status ${group.status}`}>{group.status}</span><span class="discovery-source">{discoveryLabel(group)}</span><span class="workflow-status">{duplicateWorkflowLabel(entry)}</span><span class:stale={rawDraftFor(group)?.stale} class="decision-status">{savingGroups.has(group.group_id) ? 'Saving…' : pendingDrafts.has(group.group_id) ? 'Unsaved changes' : rawDraftFor(group)?.stale ? 'Decisions stale' : rawDraftFor(group)?.decisions.length ? rawDraftFor(group)?.status === 'completed' ? 'Completed' : 'Saved decisions' : 'No decisions'}</span></div>
              </div>
              <div class="group-controls">
                <p>{group.reason}</p>
                <div class="group-presets" aria-label="Set every image decision">
                  <button type="button" disabled={busy} onclick={() => applyGroupPreset(group, 'keep')}>Keep all</button>
                  <button type="button" disabled={busy} onclick={() => applyGroupPreset(group, 'delete')}>Delete all</button>
                  <button type="button" disabled={busy} onclick={() => applyGroupPreset(group, 'stack')}>Stack all</button>
                  <button type="button" disabled={busy || !rawDraftFor(group)?.decisions.length} onclick={() => void clearDecisions([group.group_id])}>Clear</button>
                </div>
              </div>
            </header>
            <div class="members">
              {#each group.members as member, memberIndex (member.id)}
                <div
                  class:keep={dispositionFor(group, member.id) === 'keep'}
                  class:delete={dispositionFor(group, member.id) === 'delete'}
                  class:stack={dispositionFor(group, member.id) === 'stack'}
                  class="member"
                >
                  <div class="member-image">
                    <button class="preview-button" type="button" aria-label={`Preview ${member.original_file_name}`} onclick={() => openPreview(group, memberIndex)}>
                      <img src={`/api/assets/${encodeURIComponent(member.id)}/thumbnail`} alt="" loading="lazy" />
                    </button>
                    <button class="view-button" type="button" aria-label={`View complete details for ${member.original_file_name}`} onclick={() => openPreview(group, memberIndex)}><Icon name="view" size=".95rem" /></button>
                    {#if draftFor(group)?.stack_primary_asset_id === member.id}<span class="keeper-label">Stack main</span>{/if}
                  </div>
                  <div class="member-body">
                    <strong title={member.original_file_name}>{member.original_file_name}</strong>
                    <span class={`source-kind ${member.source_kind}`}>{member.source_kind === 'upload' ? 'Immich upload' : 'External library'}</span>
                    {#if member.library_id}<small class="library-id" title={member.library_id}>{member.library_id}</small>{/if}
                    <GroupEvidencePills {member} analysisPending={result.analysis_task_id !== null && member.evidence.analysis_freshness !== 'current'} />
                    {#if member.recommended_disposition}
                      <small class="rule-recommendation" title={(member.recommendation_reason_codes ?? []).join(', ')}>Rule · {member.recommended_disposition}</small>
                    {/if}
                    <small>{formatSize(member.file_size_bytes)}</small>
                    <DuplicateDispositionControls
                      value={dispositionFor(group, member.id)}
                      disabled={busy}
                      compact
                      onchange={(disposition) => setMemberDisposition(group, member.id, disposition)}
                    />
                    <StackPrimaryControl
                      eligible={dispositionFor(group, member.id) === 'stack'}
                      selected={draftFor(group)?.stack_primary_asset_id === member.id}
                      disabled={busy}
                      compact
                      onchange={() => setStackPrimary(group, member.id)}
                    />
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
    message={`Process ${plan.group_count} reviewed Immich duplicate groups: ${plan.resolve_group_count} keeper resolutions, ${plan.keep_all_group_count} keep-all groups, ${plan.delete_all_group_count} delete-all groups, and ${plan.mixed_group_count} mixed groups. This retains ${plan.retained_asset_count} assets and trashes ${plan.trash_asset_count}.${plan.stack_group_count ? ` After resolution, create ${plan.stack_group_count} stacks; incomplete stacks can resume without resolving the group again.` : ''}${plan.zero_survivor_group_count ? ` ${plan.zero_survivor_group_count} groups will retain zero copies.` : ''}`}
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
  .controls { display: grid; grid-template-columns: repeat(3, minmax(12rem, 1fr)); gap: .8rem; align-items: end; padding: 1rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); box-shadow: var(--shadow-card); }
  .apply-rules { color: var(--color-ink-inverse); border-color: var(--color-accent-strong); background: var(--color-accent-strong); }
  .apply-rules:hover:not(:disabled) { color: var(--color-ink-inverse); border-color: var(--color-accent-strong); background: color-mix(in srgb, var(--color-accent-strong) 88%, black); }
  .scan-similar { display: flex; align-items: center; justify-content: center; gap: .4rem; }
  .similarity-controls { display: grid; grid-template-columns: minmax(14rem, 1.2fr) minmax(10rem, .5fr) auto minmax(15rem, .8fr); gap: 1rem; align-items: end; padding: 1rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); box-shadow: var(--shadow-card); }
  .similarity-copy, .last-scan, .similarity-controls label { display: grid; gap: .25rem; }
  .similarity-copy > span, .last-scan > span, .similarity-controls label > span { color: var(--color-ink-muted); font-size: .62rem; font-weight: 780; text-transform: uppercase; }
  .similarity-controls input { min-height: 2.45rem; padding: .45rem .6rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); font: inherit; }
  .last-scan { padding-left: 1rem; border-left: 1px solid var(--color-border-subtle); }
  .cancel-scan { justify-self: end; }
  .analysis-state { display: grid; min-height: 2.45rem; align-content: center; gap: .12rem; padding: .35rem .65rem; border-left: 1px solid var(--color-border-subtle); }
  .analysis-state span { color: var(--color-ink-muted); font-size: .62rem; font-weight: 760; }
  .analysis-state strong { font-size: .72rem; }
  button { min-height: 2.45rem; padding: .5rem .7rem; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); color: var(--color-ink-strong); background: var(--color-canvas); font: inherit; }
  button { cursor: pointer; font-size: .75rem; font-weight: 780; }
  button:hover:not(:disabled) { border-color: var(--color-accent-strong); color: var(--color-accent-strong); }
  button:disabled { cursor: default; opacity: .5; }
  .progress, .notice, .batch-bar, .summary, .empty { border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); }
  .progress { display: grid; gap: .6rem; padding: .8rem 1rem; }
  .progress div { display: flex; justify-content: space-between; gap: 1rem; font-size: .76rem; }
  progress { width: 100%; accent-color: var(--color-accent-strong); }
  .notice, .empty { margin: 0; padding: .8rem 1rem; color: var(--color-ink-muted); }
  .notice.error { color: var(--color-negative-ink); border-color: var(--color-negative-border); background: var(--color-negative-surface); }
  .notice.error { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
  .notice.success { color: var(--color-positive-ink); border-color: var(--color-positive-border); background: var(--color-positive-surface); }
  .summary { display: grid; grid-template-columns: repeat(6, 1fr); overflow: hidden; }
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
  .group-card header p { flex: 1; margin: 0; color: var(--color-ink-muted); font-size: .73rem; text-align: right; }
  .group-controls { display: flex; min-width: min(100%, 31rem); flex: 1; align-items: center; justify-content: flex-end; gap: .75rem; }
  .group-presets { display: inline-flex; flex: none; overflow: hidden; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); }
  .group-presets button { min-height: 2rem; border: 0; border-right: 1px solid var(--color-border-subtle); border-radius: 0; }
  .group-presets button:last-child { border-right: 0; }
  .group-heading { display: flex; align-items: center; gap: .65rem; }
  .group-heading > div { display: flex; align-items: center; gap: .55rem; white-space: nowrap; }
  .status { padding: .2rem .45rem; border-radius: 999px; background: var(--color-surface-soft); font-size: .62rem; font-weight: 800; text-transform: uppercase; }
  .status.exact { color: var(--color-positive-ink); background: var(--color-positive-surface); }
  .status.unverified { color: var(--color-warning-ink); background: var(--color-warning-surface); }
  .status.mismatch, .status.ineligible { color: var(--color-negative-ink); background: var(--color-negative-surface); }
  .workflow-status { color: var(--color-ink-muted); font-size: .6rem; font-weight: 760; }
  .decision-status { color: var(--color-positive-ink); font-size: .6rem; font-weight: 760; }
  .decision-status.stale { color: var(--color-warning-ink); }
  .stale-workspace { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
  .discovery-source { padding: .18rem .4rem; border-radius: 999px; color: var(--color-accent-strong); background: var(--color-surface-soft); font-size: .6rem; font-weight: 780; }
  .members { display: grid; grid-template-columns: repeat(auto-fill, minmax(11.5rem, 1fr)); gap: .75rem; padding: .75rem; }
  .member { display: grid; min-width: 0; overflow: hidden; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); background: var(--color-canvas); }
  .member.keep { border-color: var(--color-positive-border); box-shadow: inset 0 0 0 1px var(--color-positive-border); }
  .member.delete { border-color: var(--color-negative-border); box-shadow: inset 0 0 0 1px var(--color-negative-border); }
  .member.stack { border-color: var(--color-accent-strong); box-shadow: inset 0 0 0 1px var(--color-accent-strong); }
  .member-image { position: relative; aspect-ratio: 1; overflow: hidden; background: var(--color-surface-soft); }
  .preview-button { display: block; width: 100%; height: 100%; min-height: 0; padding: 0; border: 0; border-radius: 0; background: transparent; }
  .preview-button img { display: block; width: 100%; height: 100%; object-fit: cover; transition: transform .18s ease; }
  .preview-button:hover img { transform: scale(1.025); }
  .view-button { position: absolute; top: .45rem; right: .45rem; display: grid; width: 2rem; height: 2rem; min-height: 0; padding: 0; place-items: center; border: 1px solid rgb(255 255 255 / .4); border-radius: 999px; color: white; background: rgb(12 16 18 / .72); box-shadow: 0 2px 8px rgb(0 0 0 / .28); backdrop-filter: blur(5px); }
  .keeper-label { position: absolute; bottom: .45rem; left: .45rem; padding: .2rem .42rem; border-radius: 999px; color: white; background: rgb(12 16 18 / .76); font-size: .58rem; font-weight: 820; text-transform: uppercase; }
  .member-body { display: grid; gap: .28rem; min-width: 0; padding: .6rem; }
  .member-body strong { overflow: hidden; font-size: .7rem; text-overflow: ellipsis; white-space: nowrap; }
  .source-kind { width: fit-content; padding: .16rem .38rem; border-radius: 999px; color: var(--color-accent-strong); background: var(--color-surface-soft); font-size: .57rem; font-weight: 820; text-transform: uppercase; }
  .source-kind.external { color: var(--color-warning-ink); background: var(--color-warning-surface); }
  .rule-recommendation { width: fit-content; padding: .16rem .38rem; border-radius: 999px; color: var(--color-positive-ink); background: var(--color-positive-surface); font-weight: 780; text-transform: capitalize; }
  .library-id { overflow: hidden; font-family: ui-monospace, monospace; text-overflow: ellipsis; white-space: nowrap; }
  small { color: var(--color-ink-muted); font-size: .63rem; }
  @media (max-width: 58rem) { .controls, .similarity-controls { grid-template-columns: 1fr 1fr; } .summary { grid-template-columns: repeat(3, 1fr); } }
  @media (max-width: 46rem) { .page-intro, .controls, .similarity-controls { grid-template-columns: 1fr; } .last-scan { padding: .75rem 0 0; border-top: 1px solid var(--color-border-subtle); border-left: 0; } .summary { grid-template-columns: 1fr 1fr; } .group-card > header, .group-controls { align-items: stretch; flex-direction: column; } .group-card header p { text-align: left; } }
</style>

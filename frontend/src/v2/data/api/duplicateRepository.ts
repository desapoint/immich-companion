import { jsonRequest, requestJson } from '../../../lib/api/http';
import type {
  AssetRecord,
  DuplicateDecision,
  DuplicateDiscoveryOptions,
  DuplicateGroupRecord,
  DuplicatePreparedPlan,
  DuplicateRepository,
  DuplicateResolutionPlan,
  DuplicateSearchQuery,
  DuplicateState,
  MutationResult,
  PageResult,
} from '../contracts';
import type { TaskRecord, TaskRepository } from '../syncContracts';

type AnalysisOptions = {
  keeper_policy: 'prefer_upload';
  external_library_ids: string[];
  verify_upload_streams: boolean;
  automatic_handling_enabled: boolean;
  preselect_safe_groups: boolean;
  exact_file_action: 'resolve';
  analyze_automatically: boolean;
};
type ApiDuplicateMember = {
  id: string;
  source_kind: 'upload' | 'external';
  library_id: string | null;
  original_file_name: string;
  original_mime_type: string | null;
  file_size_bytes: number | null;
  file_modified_at: string;
  uploaded_at: string | null;
  is_offline: boolean;
  is_stacked: boolean;
  verification: 'matching' | 'mismatch' | 'unverified';
  evidence: {
    decoded_width?: number | null;
    decoded_height?: number | null;
  };
  similarity: { state: 'reference' | 'current' | 'pending' | 'unavailable'; similarity_percent: number | null } | null;
};
type ApiDuplicateGroup = {
  group_id: string;
  classification: 'exact_file' | 'exact_pixels' | 'likely_same' | 'similar' | 'mismatch' | 'unverified' | 'unavailable' | 'ineligible';
  status: 'exact' | 'unverified' | 'mismatch' | 'ineligible';
  reason: string | null;
  auto_resolvable: boolean;
  auto_selected: boolean;
  member_fingerprint: string;
  members: ApiDuplicateMember[];
  eligible: boolean;
};
type ApiDuplicateResult = { group_count: number; groups: ApiDuplicateGroup[] };
type ApiDuplicateDraft = {
  group_id: string;
  member_fingerprint: string;
  decisions: Array<{ asset_id: string; disposition: DuplicateDecision }>;
  stack_primary_asset_id: string | null;
  stack_resolution: 'keep_existing' | 'move_selected' | 'include_existing';
  status: 'pending' | 'completed';
  stale: boolean;
};
type ApiDuplicateWorkspace = {
  initialized: boolean;
  selected_group_ids: string[];
  active_group_id: string | null;
  stale_selected_groups: Array<{ group_id: string }>;
  drafts: ApiDuplicateDraft[];
};

const ANALYSIS_OPTIONS: AnalysisOptions = {
  keeper_policy: 'prefer_upload',
  external_library_ids: [],
  verify_upload_streams: false,
  automatic_handling_enabled: true,
  preselect_safe_groups: true,
  exact_file_action: 'resolve',
  analyze_automatically: false,
};

const TERMINAL_TASK_STATES = new Set(['completed', 'failed', 'cancelled']);

type TaskStart = { task_id: string };
type PlanResponse = { id: string };

function pageNumber(query: DuplicateSearchQuery): number {
  if (query.page) return query.page;
  const cursor = Number.parseInt(query.cursor ?? '', 10);
  return Number.isSafeInteger(cursor) && cursor > 0 ? cursor : 1;
}

function similarity(member: ApiDuplicateMember): number {
  if (member.similarity?.state === 'reference') return 100;
  return member.similarity?.similarity_percent ?? (member.verification === 'matching' ? 100 : 0);
}

function assetType(mimeType: string | null): AssetRecord['asset_type'] {
  if (mimeType?.startsWith('video/')) return 'VIDEO';
  if (mimeType?.startsWith('audio/')) return 'AUDIO';
  if (mimeType?.startsWith('image/')) return 'IMAGE';
  return 'OTHER';
}

function assetFromMember(member: ApiDuplicateMember): AssetRecord {
  return {
    id: member.id,
    owner_id: null,
    library_id: member.library_id,
    asset_type: assetType(member.original_mime_type),
    original_file_name: member.original_file_name,
    original_path: null,
    original_mime_type: member.original_mime_type,
    checksum: null,
    file_size_bytes: member.file_size_bytes,
    width: member.evidence.decoded_width ?? null,
    height: member.evidence.decoded_height ?? null,
    duration: null,
    file_created_at: member.uploaded_at ?? member.file_modified_at,
    file_modified_at: member.file_modified_at,
    local_date_time: null,
    immich_created_at: member.uploaded_at,
    immich_updated_at: null,
    is_favorite: false,
    is_archived: false,
    is_offline: member.is_offline,
    is_edited: false,
    has_metadata: false,
    visibility: null,
    live_photo_video_id: null,
    tags: [],
    albums: [],
    stack: null,
    synced_at: member.file_modified_at,
  };
}

function savedDecisions(draft: ApiDuplicateDraft | undefined): Record<string, DuplicateDecision> {
  return Object.fromEntries(
    (draft?.decisions ?? [])
      .map((decision) => [decision.asset_id, decision.disposition]),
  ) as Record<string, DuplicateDecision>;
}

function groupState(group: ApiDuplicateGroup, draft: ApiDuplicateDraft | undefined): DuplicateState {
  if (!group.eligible || group.status === 'ineligible' || group.members.some((member) => member.is_offline) || draft?.stale) return 'Blocked';
  const decisionCount = draft?.decisions.length ?? 0;
  if (decisionCount > 0 && decisionCount < group.members.length) return 'Needs decisions';
  if (decisionCount === group.members.length || group.auto_resolvable || group.auto_selected) return 'Actionable';
  return 'Needs review';
}

function actionFor(decisions: Record<string, DuplicateDecision>): 'resolve' | 'keep_all' | 'stack_all' | 'mixed' {
  const values = Object.values(decisions);
  if (values.every((decision) => decision === 'keep')) return 'keep_all';
  if (values.every((decision) => decision === 'stack')) return 'stack_all';
  if (values.includes('stack')) return 'mixed';
  return 'resolve';
}

function primaryFor(resolution: DuplicateResolutionPlan, memberIds: readonly string[]): string | null {
  const stack = resolution.stacks.find((candidate) => candidate.assetIds.some((id) => memberIds.includes(id)));
  if (stack?.primaryAssetId) return stack.primaryAssetId;
  return memberIds.find((id) => resolution.decisions[id] === 'keep')
    ?? memberIds.find((id) => resolution.decisions[id] !== 'delete')
    ?? null;
}

function groupResolution(resolution: DuplicateResolutionPlan, group: ApiDuplicateGroup): DuplicateResolutionPlan {
  const ids = new Set(group.members.map((member) => member.id));
  return {
    decisions: Object.fromEntries(Object.entries(resolution.decisions).filter(([id]) => ids.has(id))),
    stacks: resolution.stacks.filter((stack) => stack.groupId === group.group_id),
  };
}

function failureResult(groups: readonly ApiDuplicateGroup[], failedGroupIds: readonly string[]): MutationResult {
  const failed = new Set(failedGroupIds);
  return {
    affectedIds: groups.filter((group) => !failed.has(group.group_id)).flatMap((group) => group.members.map((member) => member.id)),
    failed: groups.filter((group) => failed.has(group.group_id)).flatMap((group) => group.members.map((member) => ({ id: member.id, reason: `Duplicate group ${group.group_id} could not be resolved.` }))),
  };
}

async function waitForTask(tasks: TaskRepository, taskId: string): Promise<TaskRecord> {
  for (;;) {
    const task = await tasks.get(taskId);
    if (TERMINAL_TASK_STATES.has(task.status)) {
      if (task.status !== 'completed') throw new Error(task.error?.message ?? `Duplicate task ${task.status}.`);
      return task;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
}

export function createDuplicateRepository(tasks: TaskRepository): DuplicateRepository {
  let rawGroups = new Map<string, ApiDuplicateGroup>();
  let visibleGroupIds = new Set<string>();
  let workspace: ApiDuplicateWorkspace = { initialized: false, selected_group_ids: [], active_group_id: null, stale_selected_groups: [], drafts: [] };
  const draftQueues = new Map<string, Promise<void>>();

  const draftFor = (groupId: string): ApiDuplicateDraft | undefined => workspace.drafts.find((draft) => draft.group_id === groupId && !draft.stale);

  const materialize = (group: ApiDuplicateGroup): DuplicateGroupRecord => {
    const draft = draftFor(group.group_id);
    return {
      id: group.group_id,
      state: groupState(group, draft),
      kind: group.classification.replaceAll('_', ' '),
      reason: group.reason,
      memberFingerprint: group.member_fingerprint,
      selected: workspace.selected_group_ids.includes(group.group_id),
      savedDecisions: savedDecisions(draft),
      stackPrimaryAssetId: draft?.stack_primary_asset_id ?? null,
      stackResolution: draft?.stack_resolution ?? 'move_selected',
      members: group.members.map((member) => ({ asset: assetFromMember(member), similarity: similarity(member) })),
    };
  };

  const writeDraft = async (groupId: string, resolution: DuplicateResolutionPlan): Promise<void> => {
    const group = rawGroups.get(groupId);
    if (!group) throw new Error(`Duplicate group ${groupId} is no longer available.`);
    const scoped = groupResolution(resolution, group);
    if (scoped.stacks.length > 1) throw new Error('Immich can create only one resulting stack per duplicate group.');
    if (scoped.stacks.some((stack) => stack.assetIds.length === 1)) throw new Error('A stack needs at least two images.');
    const memberIds = group.members.map((member) => member.id);
    const primary = primaryFor(scoped, memberIds);
    const survivors = memberIds.filter((id) => scoped.decisions[id] !== 'delete');
    const draft = await requestJson<ApiDuplicateDraft>('/api/assets/duplicates/workspace/group', jsonRequest('PUT', {
      group_id: groupId,
      member_fingerprint: group.member_fingerprint,
      options: ANALYSIS_OPTIONS,
      decisions: Object.entries(scoped.decisions).map(([asset_id, disposition]) => ({ asset_id, disposition, source: 'manual', status: 'pending' })),
      stack_primary_asset_id: scoped.stacks[0]?.primaryAssetId ?? (Object.values(scoped.decisions).includes('stack') ? primary : null),
      stack_resolution: 'move_selected',
      metadata_keeper_asset_id: Object.values(scoped.decisions).includes('delete') && survivors.length > 1 ? primary : null,
      status: Object.keys(scoped.decisions).length === memberIds.length ? 'completed' : 'pending',
    }));
    workspace = { ...workspace, drafts: [...workspace.drafts.filter((candidate) => candidate.group_id !== groupId), draft] };
  };

  const saveDraft = (groupId: string, resolution: DuplicateResolutionPlan): Promise<void> => {
    const queued = (draftQueues.get(groupId) ?? Promise.resolve())
      .catch(() => undefined)
      .then(() => writeDraft(groupId, resolution));
    draftQueues.set(groupId, queued);
    void queued.then(
      () => { if (draftQueues.get(groupId) === queued) draftQueues.delete(groupId); },
      () => { if (draftQueues.get(groupId) === queued) draftQueues.delete(groupId); },
    );
    return queued;
  };

  const saveSelection = async (groupIds: readonly string[], activeGroupId: string | null): Promise<void> => {
    const selectedGroupIds = [
      ...workspace.selected_group_ids.filter((groupId) => !visibleGroupIds.has(groupId)),
      ...groupIds,
    ];
    workspace = await requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace/selection', jsonRequest('PUT', {
      options: ANALYSIS_OPTIONS,
      selected_group_ids: [...new Set(selectedGroupIds)],
      active_group_id: activeGroupId,
    }));
  };

  return {
    async capabilities() {
      return { canRunDiscovery: true, canApplyDecisions: true, canViewHistory: false, reviewFilters: ['All groups', 'Needs review', 'Auto-ready', 'Blocked', 'Actionable', 'Needs decisions'], decisions: ['keep', 'delete', 'stack'] };
    },
    async search(query): Promise<PageResult<DuplicateGroupRecord>> {
      const [result, restored] = await Promise.all([
        requestJson<ApiDuplicateResult>('/api/assets/duplicates/cross-source/search', { ...jsonRequest('POST', ANALYSIS_OPTIONS), signal: query.signal }),
        requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace', { signal: query.signal }),
      ]);
      workspace = restored;
      rawGroups = new Map(result.groups.map((group) => [group.group_id, group]));
      const filtered = result.groups.filter((group) => {
        const state = groupState(group, draftFor(group.group_id));
        return !query.state || query.state === 'All groups' || (query.state === 'Auto-ready' ? state === 'Actionable' : state === query.state);
      });
      const page = pageNumber(query);
      const start = (page - 1) * query.pageSize;
      const items = filtered.slice(start, start + query.pageSize).map(materialize);
      visibleGroupIds = new Set(items.map((group) => group.id));
      return { items, total: filtered.length, pageSize: query.pageSize, page, nextCursor: start + query.pageSize < filtered.length ? String(page + 1) : null };
    },
    saveDraft,
    saveSelection,
    async switchReference(groupId, referenceAssetId) {
      const group = await requestJson<ApiDuplicateGroup>(`/api/assets/duplicates/cross-source/${encodeURIComponent(groupId)}/similarity-reference`, jsonRequest('POST', { reference_asset_id: referenceAssetId }));
      rawGroups.set(groupId, group);
      return materialize(group);
    },
    async runDiscovery(options: DuplicateDiscoveryOptions) {
      if (options.includeExact) {
        const started = await requestJson<TaskStart>('/api/assets/duplicates/cross-source/analyze', jsonRequest('POST', ANALYSIS_OPTIONS));
        await waitForTask(tasks, started.task_id);
      }
      if (options.includeSimilar) {
        const started = await requestJson<TaskStart>('/api/assets/duplicates/similarity-scan', jsonRequest('POST', {
          similarity_threshold: options.similarityThreshold,
          scope: 'all_eligible_assets',
          maximum_perceptual_distance: 12,
          maximum_aspect_difference: 0.05,
          maximum_neighbors_per_asset: Math.min(64, Math.max(1, options.maxCandidates)),
          maximum_matches: 5000,
        }));
        await waitForTask(tasks, started.task_id);
      }
      const result = await requestJson<ApiDuplicateResult>('/api/assets/duplicates/cross-source/search', jsonRequest('POST', ANALYSIS_OPTIONS));
      return { groupCount: result.group_count, candidateCount: result.groups.reduce((count, group) => count + group.members.length, 0) };
    },
    async prepareDecisions(resolution: DuplicateResolutionPlan): Promise<DuplicatePreparedPlan> {
      const groups = [...rawGroups.values()].filter((group) => group.members.some((member) => resolution.decisions[member.id]));
      if (!groups.length) throw new Error('Choose at least one complete duplicate group before review.');
      for (const group of groups) {
        const scoped = groupResolution(resolution, group);
        if (Object.keys(scoped.decisions).length !== group.members.length) throw new Error(`Group ${group.group_id} still has images without a decision.`);
        await saveDraft(group.group_id, scoped);
      }
      await saveSelection(groups.map((group) => group.group_id), groups[0]?.group_id ?? null);
      const action_overrides = Object.fromEntries(groups.map((group) => [group.group_id, actionFor(groupResolution(resolution, group).decisions)]));
      const keeper_overrides = Object.fromEntries(groups.flatMap((group) => {
        const primary = primaryFor(groupResolution(resolution, group), group.members.map((member) => member.id));
        return primary ? [[group.group_id, primary]] : [];
      }));
      const plan = await requestJson<PlanResponse>('/api/assets/duplicates/cross-source/plan', jsonRequest('POST', {
        options: ANALYSIS_OPTIONS,
        group_ids: groups.map((group) => group.group_id),
        all_eligible: false,
        keeper_overrides,
        action_overrides,
      }));
      return { id: plan.id, resolution, groupIds: groups.map((group) => group.group_id) };
    },
    async executePlan(plan: DuplicatePreparedPlan) {
      const groups = plan.groupIds.flatMap((groupId) => {
        const group = rawGroups.get(groupId);
        return group ? [group] : [];
      });
      if (groups.length !== plan.groupIds.length) throw new Error('A duplicate group changed after review. Prepare the actions again.');
      const started = await requestJson<TaskStart>('/api/assets/duplicates/cross-source/execute', jsonRequest('POST', { plan_id: plan.id }));
      const completed = await waitForTask(tasks, started.task_id);
      const summary = completed.result?.summary as Record<string, unknown> | undefined;
      const rawFailed = summary?.failed_group_ids;
      const failed = Array.isArray(rawFailed) ? rawFailed.filter((id: unknown): id is string => typeof id === 'string') : [];
      return failureResult(groups, failed);
    },
    async history(query) {
      return { items: [], total: 0, pageSize: query.pageSize, page: pageNumber(query), nextCursor: null };
    },
  };
}

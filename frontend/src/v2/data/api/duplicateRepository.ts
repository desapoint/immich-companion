import { jsonRequest, requestJson } from '../../../lib/api/http';
import type {
  AssetRecord,
  DuplicateDecision,
  DuplicateDiscoveryOptions,
  DuplicateDiscoveryProgress,
  DuplicateGroupRecord,
  DuplicatePreparedPlan,
  DuplicateRepository,
  DuplicateResolutionPlan,
  DuplicateSearchQuery,
  DuplicateState,
  MutationResult,
  PageResult,
  SimilarityCacheStatus,
} from '../contracts';
import type { TaskRecord, TaskRepository } from '../syncContracts';
import { referenceFirstDuplicateMembers } from '../duplicatePresentation';

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
  similarity: {
    state: 'reference' | 'current' | 'pending' | 'unavailable';
    similarity_percent: number | null;
    structural_percent: number | null;
    perceptual_percent: number | null;
    color_percent: number | null;
  } | null;
  admission: {
    admitted_by_asset_id: string | null;
    admission_similarity_percent: number | null;
    best_group_match_asset_id: string | null;
    best_group_match_similarity_percent: number | null;
    link_depth: number;
    model_version: string;
    feature_version: number;
    comparison_version: number;
    config_fingerprint: string;
  } | null;
};
type ApiDuplicateGroup = {
  group_id: string;
  reference_asset_id: string | null;
  group_similarity_percent: number | null;
  similarity_engine: string | null;
  similarity_model_version: string | null;
  similarity_feature_version: number | null;
  similarity_comparison_version: number | null;
  similarity_validation_mode: 'reference' | 'linked' | 'strict' | null;
  similarity_threshold_percent: number | null;
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
  revision?: number;
  selected_count?: number;
  selected_group_ids: string[];
  active_group_id: string | null;
  stale_selected_groups: Array<{ group_id: string }>;
  drafts: ApiDuplicateDraft[];
  last_applied_group_ids?: string[];
  last_skipped_group_ids?: string[];
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
type PlanResponse = {
  id: string;
  destructive?: boolean;
  groups?: Array<{
    group_id: string;
    members: Array<{ asset_id: string; disposition: DuplicateDecision }>;
    follow_up?: { primary_asset_id: string; member_asset_ids: string[] } | null;
  }>;
};
type ApiDiskCacheStatus = { path:string;healthy:boolean;used_bytes:number;max_bytes:number;free_bytes:number;entry_count:number;hits:number;misses:number;evictions:number;cleanup_failures:number };
type ApiSimilarityCacheStatus = { config_fingerprint:string;feature_count:number;feature_estimated_bytes:number;pair_count:number;pair_estimated_bytes:number;pair_max_bytes:number;pair_hits:number;pair_misses:number;pair_evictions:number;hot_count:number;hot_estimated_bytes:number;hot_max_bytes:number;hot_hits:number;hot_misses:number;hot_evictions:number;reference_latency_p50_ms:number|null;reference_latency_p95_ms:number|null;previews:ApiDiskCacheStatus;decode:ApiDiskCacheStatus;generated_at:string };
type ApiSimilarityCacheClearResult = { status:ApiSimilarityCacheStatus };

function diskCacheStatus(value:ApiDiskCacheStatus){return{path:value.path,healthy:value.healthy,usedBytes:value.used_bytes,maxBytes:value.max_bytes,freeBytes:value.free_bytes,entryCount:value.entry_count,hits:value.hits,misses:value.misses,evictions:value.evictions,cleanupFailures:value.cleanup_failures}}
function cacheStatus(value:ApiSimilarityCacheStatus):SimilarityCacheStatus{return{configFingerprint:value.config_fingerprint,featureCount:value.feature_count,featureEstimatedBytes:value.feature_estimated_bytes,pairCount:value.pair_count,pairEstimatedBytes:value.pair_estimated_bytes,pairMaxBytes:value.pair_max_bytes,pairHits:value.pair_hits,pairMisses:value.pair_misses,pairEvictions:value.pair_evictions,hotCount:value.hot_count,hotEstimatedBytes:value.hot_estimated_bytes,hotMaxBytes:value.hot_max_bytes,hotHits:value.hot_hits,hotMisses:value.hot_misses,hotEvictions:value.hot_evictions,referenceLatencyP50Ms:value.reference_latency_p50_ms,referenceLatencyP95Ms:value.reference_latency_p95_ms,previews:diskCacheStatus(value.previews),decode:diskCacheStatus(value.decode),generatedAt:value.generated_at}}

function pageNumber(query: DuplicateSearchQuery): number {
  if (query.page) return query.page;
  const cursor = Number.parseInt(query.cursor ?? '', 10);
  return Number.isSafeInteger(cursor) && cursor > 0 ? cursor : 1;
}

function similarity(member: ApiDuplicateMember): number | null {
  if (!member.similarity) return null;
  if (member.similarity?.state === 'reference') return 100;
  return member.similarity.similarity_percent;
}

function similarityEvidence(member: ApiDuplicateMember) {
  if (!member.similarity) return null;
  return {
    structuralPercent: member.similarity.structural_percent,
    perceptualPercent: member.similarity.perceptual_percent,
    colorPercent: member.similarity.color_percent,
  };
}

function admissionEvidence(member: ApiDuplicateMember) {
  if (!member.admission) return null;
  return {
    admittedByAssetId: member.admission.admitted_by_asset_id,
    admissionSimilarityPercent: member.admission.admission_similarity_percent,
    bestGroupMatchAssetId: member.admission.best_group_match_asset_id,
    bestGroupMatchSimilarityPercent: member.admission.best_group_match_similarity_percent,
    linkDepth: member.admission.link_depth,
    modelVersion: member.admission.model_version,
    featureVersion: member.admission.feature_version,
    comparisonVersion: member.admission.comparison_version,
    configFingerprint: member.admission.config_fingerprint,
  };
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

function numericProgress(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function discoveryProgress(task: TaskRecord, similarity: boolean, rangeStart: number, rangeEnd: number): DuplicateDiscoveryProgress {
  const rawPhase = typeof task.progress.phase === 'string' ? task.progress.phase : '';
  const phases: Record<string, string> = {
    duplicate_fingerprints: 'Verifying file evidence',
    similarity_candidates: 'Indexing similarity candidates',
    similarity_scoring: 'Comparing candidate pairs',
    similarity_finalizing: 'Finalizing duplicate groups',
    complete: 'Completing analysis',
  };
  const rawPercent = numericProgress(task.progress.percent);
  const overallPercent = rawPercent === null
    ? null
    : Math.min(rangeEnd, rangeStart + (rangeEnd - rangeStart) * rawPercent / 100);
  const matches = numericProgress(task.counters.matches_retained);
  const detail = typeof task.progress.detail === 'string'
    ? task.progress.detail
    : task.status === 'queued'
      ? 'Waiting for the background worker…'
      : 'Preparing duplicate analysis…';
  return {
    label: `Duplicate discovery · ${phases[rawPhase] ?? (similarity ? 'Preparing similarity scan' : 'Preparing exact matches')}`,
    detail: matches === null ? detail : `${detail} · ${matches.toLocaleString()} matches retained`,
    completed: numericProgress(task.progress.completed) ?? 0,
    total: numericProgress(task.progress.total),
    percent: overallPercent,
  };
}

async function waitForTask(tasks: TaskRepository, taskId: string, similarity = false, rangeStart = 0, rangeEnd = 98, onprogress?: (progress: DuplicateDiscoveryProgress) => void): Promise<TaskRecord> {
  for (;;) {
    const task = await tasks.get(taskId);
    onprogress?.(discoveryProgress(task, similarity, rangeStart, rangeEnd));
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
  let workspace: ApiDuplicateWorkspace = { initialized: false, revision: 0, selected_count: 0, selected_group_ids: [], active_group_id: null, stale_selected_groups: [], drafts: [] };
  const draftQueues = new Map<string, Promise<void>>();

  const draftFor = (groupId: string): ApiDuplicateDraft | undefined => workspace.drafts.find((draft) => draft.group_id === groupId && !draft.stale);

  const materialize = (group: ApiDuplicateGroup): DuplicateGroupRecord => {
    const draft = draftFor(group.group_id);
    return {
      id: group.group_id,
      state: groupState(group, draft),
      kind: group.classification.replaceAll('_', ' '),
      reason: group.reason,
      referenceAssetId: group.reference_asset_id ?? null,
      groupSimilarity: group.group_similarity_percent ?? null,
      similarityEngine: group.similarity_engine ?? null,
      similarityModelVersion: group.similarity_model_version ?? null,
      similarityFeatureVersion: group.similarity_feature_version ?? null,
      similarityComparisonVersion: group.similarity_comparison_version ?? null,
      similarityValidationMode: group.similarity_validation_mode ?? null,
      similarityThresholdPercent: group.similarity_threshold_percent ?? null,
      memberFingerprint: group.member_fingerprint,
      selected: workspace.selected_group_ids.includes(group.group_id),
      savedDecisions: savedDecisions(draft),
      stackPrimaryAssetId: draft?.stack_primary_asset_id ?? null,
      stackResolution: draft?.stack_resolution ?? 'move_selected',
      members: referenceFirstDuplicateMembers(
        group.members.map((member) => ({ asset: assetFromMember(member), similarity: similarity(member), similarityEvidence: similarityEvidence(member), admission: admissionEvidence(member) })),
        group.reference_asset_id,
      ),
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
      revision: workspace.revision,
    }));
  };

  return {
    async capabilities() {
      return { canRunDiscovery: true, canApplyDecisions: true, canViewHistory: false, reviewFilters: ['All groups', 'Needs review', 'Auto-ready', 'Blocked', 'Actionable', 'Needs decisions'], decisions: ['keep', 'delete', 'stack'] };
    },
    selectedGroupIds() { return [...workspace.selected_group_ids]; },
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
    async applyPreset(disposition,scope,groupIds){
      await Promise.all([...draftQueues.values()]);
      workspace=await requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace/preset',jsonRequest('POST',{options:ANALYSIS_OPTIONS,scope,group_ids:[...new Set(groupIds)],disposition}));
      return{appliedGroupIds:workspace.last_applied_group_ids??[],skippedGroupIds:workspace.last_skipped_group_ids??[]};
    },
    async clearDecisions() {
      const groupIds = [...rawGroups.keys()];
      await Promise.all(
        groupIds.flatMap((groupId) => {
          const pending = draftQueues.get(groupId);
          return pending ? [pending] : [];
        }),
      );
      workspace = await requestJson<ApiDuplicateWorkspace>(
        '/api/assets/duplicates/workspace/reset',
        jsonRequest('POST', { options: ANALYSIS_OPTIONS, group_ids: groupIds }),
      );
      return groupIds.length;
    },
    async cacheStatus(){return cacheStatus(await requestJson<ApiSimilarityCacheStatus>('/api/assets/duplicates/cache'))},
    async clearCache(cache){const result=await requestJson<ApiSimilarityCacheClearResult>('/api/assets/duplicates/cache/clear',jsonRequest('POST',{cache}));return cacheStatus(result.status)},
    async switchReference(groupId, referenceAssetId) {
      const group = await requestJson<ApiDuplicateGroup>(`/api/assets/duplicates/cross-source/${encodeURIComponent(groupId)}/similarity-reference`, jsonRequest('POST', { reference_asset_id: referenceAssetId }));
      rawGroups.set(groupId, group);
      return materialize(group);
    },
    async runDiscovery(options: DuplicateDiscoveryOptions, onprogress) {
      const exactEnd = options.includeSimilar ? 25 : 98;
      if (options.includeExact) {
        const started = await requestJson<TaskStart>('/api/assets/duplicates/cross-source/analyze', jsonRequest('POST', ANALYSIS_OPTIONS));
        await waitForTask(tasks, started.task_id, false, 0, exactEnd, onprogress);
      }
      if (options.includeSimilar) {
        const started = await requestJson<TaskStart>('/api/assets/duplicates/similarity-scan', jsonRequest('POST', {
          similarity_threshold: options.similarityThreshold,
          validation_mode: options.validationMode,
          anchor_asset_id: options.anchorAssetId,
          scope: 'all_eligible_assets',
          maximum_perceptual_distance: 12,
          maximum_aspect_difference: 0.05,
          maximum_neighbors_per_asset: Math.min(64, Math.max(1, options.maxCandidates)),
          maximum_matches: 5000,
        }));
        await waitForTask(tasks, started.task_id, true, options.includeExact ? exactEnd : 0, 98, onprogress);
      }
      const result = await requestJson<ApiDuplicateResult>('/api/assets/duplicates/cross-source/search', jsonRequest('POST', ANALYSIS_OPTIONS));
      onprogress?.({label:'Duplicate discovery · Preparing results',detail:'Preparing the completed duplicate groups for refresh…',completed:1,total:1,percent:99});
      return { groupCount: result.group_count, candidateCount: result.groups.reduce((count, group) => count + group.members.length, 0) };
    },
    async prepareDecisions(resolution: DuplicateResolutionPlan, groupIds: readonly string[]): Promise<DuplicatePreparedPlan> {
      const uniqueGroupIds = [...new Set(groupIds)];
      if (!uniqueGroupIds.length) {
        const plan = await requestJson<PlanResponse>('/api/assets/duplicates/cross-source/plan', jsonRequest('POST', {
          options: ANALYSIS_OPTIONS,
          group_ids: [],
          all_eligible: false,
          workspace_selected: true,
        }));
        const frozenGroups = plan.groups ?? [];
        const frozenResolution: DuplicateResolutionPlan = {
          decisions: Object.fromEntries(frozenGroups.flatMap((group) => group.members.map((member) => [member.asset_id, member.disposition]))),
          stacks: frozenGroups.flatMap((group) => group.follow_up ? [{
            id: `plan:${group.group_id}`,
            groupId: group.group_id,
            label: 'Frozen stack',
            assetIds: group.follow_up.member_asset_ids,
            primaryAssetId: group.follow_up.primary_asset_id,
          }] : []),
        };
        return {
          id: plan.id,
          resolution: frozenResolution,
          groupIds: frozenGroups.map((group) => group.group_id),
          groupMemberIds: Object.fromEntries(frozenGroups.map((group) => [group.group_id, group.members.map((member) => member.asset_id)])),
          destructive: plan.destructive,
        };
      }
      const groups = uniqueGroupIds.flatMap((groupId) => {
        const group = rawGroups.get(groupId);
        return group ? [group] : [];
      });
      if (groups.length !== uniqueGroupIds.length) throw new Error('A selected duplicate group is no longer available. Refresh the list and try again.');
      if (!groups.length) throw new Error('Choose at least one complete duplicate group before review.');
      for (const group of groups) {
        const scoped = groupResolution(resolution, group);
        if (Object.keys(scoped.decisions).length !== group.members.length) throw new Error(`Group ${group.group_id} still has images without a decision.`);
        await saveDraft(group.group_id, scoped);
      }
      const action_overrides = Object.fromEntries(groups.map((group) => [group.group_id, actionFor(groupResolution(resolution, group).decisions)]));
      const keeper_overrides = Object.fromEntries(groups.flatMap((group) => {
        const primary = primaryFor(groupResolution(resolution, group), group.members.map((member) => member.id));
        return primary ? [[group.group_id, primary]] : [];
      }));
      const plan = await requestJson<PlanResponse>('/api/assets/duplicates/cross-source/plan', jsonRequest('POST', {
        options: ANALYSIS_OPTIONS,
        group_ids: groups.map((group) => group.group_id),
        all_eligible: false,
        workspace_selected: false,
        keeper_overrides,
        action_overrides,
      }));
      return { id: plan.id, resolution, groupIds: groups.map((group) => group.group_id), destructive: plan.destructive };
    },
    async executePlan(plan: DuplicatePreparedPlan) {
      const started = await requestJson<TaskStart>('/api/assets/duplicates/cross-source/execute', jsonRequest('POST', { plan_id: plan.id }));
      const completed = await waitForTask(tasks, started.task_id);
      const summary = completed.result?.summary as Record<string, unknown> | undefined;
      const rawFailed = summary?.failed_group_ids;
      const failed = Array.isArray(rawFailed) ? rawFailed.filter((id: unknown): id is string => typeof id === 'string') : [];
      if (plan.groupMemberIds) {
        const failedGroups = new Set(failed);
        return {
          affectedIds: plan.groupIds.filter((id) => !failedGroups.has(id)).flatMap((id) => plan.groupMemberIds?.[id] ?? []),
          failed: plan.groupIds.filter((id) => failedGroups.has(id)).flatMap((id) => (plan.groupMemberIds?.[id] ?? []).map((memberId) => ({ id: memberId, reason: `Duplicate group ${id} could not be resolved.` }))),
        };
      }
      return failureResult(plan.groupIds.flatMap((id) => rawGroups.get(id) ?? []), failed);
    },
    async history(query) {
      return { items: [], total: 0, pageSize: query.pageSize, page: pageNumber(query), nextCursor: null };
    },
  };
}

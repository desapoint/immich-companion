import { jsonRequest, requestJson } from '../../../lib/api/http';
import type {
  DuplicateDecision,
  DuplicateDiscoveryOptions,
  DuplicateGroupRecord,
  DuplicateKeeperSelectionInput,
  DuplicatePreparedPlan,
  DuplicateRepository,
  DuplicateResolutionPlan,
  DuplicateSearchQuery,
  DuplicateSource,
  MutationResult,
  PageResult,
} from '../types/contracts';
import type { TaskRecord, TaskRepository } from '../../status/types/syncContracts';
import { actionFor, groupResolution, mapDuplicateGroup, primaryFor } from './duplicateMapping';
import { discoveryProgress, waitForTask } from './duplicateDiscovery';
import { cacheStatus, historyDays, historySummary, pageNumber, reviewStateParam } from './duplicateRepositorySupport';
import { createDuplicateDraftController } from './duplicateRepositoryDrafts';
import { createKeeperSelectionController } from './duplicateRepositoryKeeperSelection';

export { discoveryProgress } from './duplicateDiscovery';

import type { AnalysisOptions, ApiDuplicateGroup, ApiDuplicateGroupIds, ApiDuplicateHistoryItem, ApiDuplicateHistoryPage, ApiDuplicateKeeperSelectionResult, ApiDuplicateMember, ApiDuplicatePage, ApiDuplicateDraft, ApiDuplicateSummary, ApiDuplicateWorkspace, ApiDiskCacheStatus, ApiSimilarityCacheStatus, ApiSimilarityCacheClearResult, PlanResponse, TaskStart } from './duplicateApiTypes';
export type { AnalysisOptions, ApiDuplicateGroup, ApiDuplicateGroupIds, ApiDuplicateHistoryItem, ApiDuplicateHistoryPage, ApiDuplicateKeeperSelectionResult, ApiDuplicateMember, ApiDuplicatePage, ApiDuplicateDraft, ApiDuplicateSummary, ApiDuplicateWorkspace, ApiDiskCacheStatus, ApiSimilarityCacheStatus, ApiSimilarityCacheClearResult, PlanResponse, TaskStart } from './duplicateApiTypes';

export const ANALYSIS_OPTIONS: AnalysisOptions = {
  keeper_policy: 'prefer_upload',
  external_library_ids: [],
  verify_upload_streams: false,
  automatic_handling_enabled: true,
  preselect_safe_groups: true,
  exact_file_action: 'resolve',
  analyze_automatically: false,
};

function failureResult(groups: readonly ApiDuplicateGroup[], failedGroupIds: readonly string[]): MutationResult {
  const failed = new Set(failedGroupIds);
  return {
    affectedIds: groups.filter((group) => !failed.has(group.group_id)).flatMap((group) => group.members.map((member) => member.id)),
    failed: groups.filter((group) => failed.has(group.group_id)).flatMap((group) => group.members.map((member) => ({ id: member.id, reason: `Duplicate group ${group.group_id} could not be resolved.` }))),
  };
}

export function createDuplicateRepository(tasks: TaskRepository): DuplicateRepository {
  let rawGroups = new Map<string, ApiDuplicateGroup>();
  let hasWorkspaceSnapshot = false;
  let visibleGroupIds = new Set<string>();
  let workspace: ApiDuplicateWorkspace = { initialized: false, revision: 0, selected_count: 0, selected_group_ids: [], active_group_id: null, stale_selected_groups: [], drafts: [] };
  const drafts = createDuplicateDraftController({ rawGroups, getWorkspace: () => workspace, setWorkspace: (next) => { workspace = next; }, analysisOptions: ANALYSIS_OPTIONS });
  const { draftFor, saveDraft, flushDrafts, saveWorkspaceStackResolution, draftQueues, draftErrors } = drafts;

  const materialize = (group: ApiDuplicateGroup): DuplicateGroupRecord => {
    const draft = draftFor(group.group_id);
    return mapDuplicateGroup(group, draft, workspace.selected_group_ids.includes(group.group_id));
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

  const selectedPage = async (
    query: DuplicateSearchQuery,
    page: number,
  ): Promise<ApiDuplicatePage> => {
    if (!workspace.selected_group_ids.length) {
      return { items: [], total: 0, page, page_size: query.pageSize, pages: 0 };
    }
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(query.pageSize),
      source: query.source ?? 'both',
      sort: query.sort?.field ?? 'reclaimable',
      direction: query.sort?.direction ?? 'desc',
    });
    return requestJson<ApiDuplicatePage>(
      `/api/assets/duplicates/cross-source/selected-page?${params.toString()}`,
      { ...jsonRequest('POST', ANALYSIS_OPTIONS), signal: query.signal },
    );
  };

  const keeperSelection = createKeeperSelectionController({ getWorkspace: () => workspace, setWorkspace: (next) => { workspace = next; }, draftQueues, setWorkspaceSnapshot: (value) => { hasWorkspaceSnapshot = value; }, analysisOptions: ANALYSIS_OPTIONS });

  return {
    async capabilities() {
      return { canRunDiscovery: true, canApplyDecisions: true, canViewHistory: true, reviewFilters: ['All groups', 'Selected', 'Actionable', 'Needs review', 'Needs decisions', 'Blocked'], decisions: ['keep', 'delete', 'stack'] };
    },
    selectedGroupIds() { return [...workspace.selected_group_ids]; },
    async selectAllGroups() {
      const params = new URLSearchParams({
        source: 'both',
        state: 'all',
        limit: '10000',
      });
      const result = await requestJson<ApiDuplicateGroupIds>(
        `/api/assets/duplicates/group-ids?${params.toString()}`,
      );
      if (result.limit_exceeded) {
        throw new Error('Duplicate selection is limited to 10,000 groups.');
      }
      await saveSelection(result.group_ids, null);
      return [...result.group_ids];
    },

    async search(query): Promise<PageResult<DuplicateGroupRecord>> {
      const page = pageNumber(query);
      const restoreWorkspace = !hasWorkspaceSnapshot || !query.reuseCachedGroups;
      let result: ApiDuplicatePage;
      if (query.state === 'Selected') {
        if (restoreWorkspace) {
          workspace = await requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace', { signal: query.signal });
          hasWorkspaceSnapshot = true;
        }
        result = await selectedPage(query, page);
      } else {
        const params = new URLSearchParams({
          page: String(page),
          page_size: String(query.pageSize),
          source: query.source ?? 'both',
          sort: query.sort?.field ?? 'reclaimable',
          direction: query.sort?.direction ?? 'desc',
          state: reviewStateParam(query.state),
        });
        const [rawPage, restored] = await Promise.all([
          requestJson<ApiDuplicatePage>(`/api/assets/duplicates/cross-source/page?${params.toString()}`, { ...jsonRequest('POST', ANALYSIS_OPTIONS), signal: query.signal }),
          restoreWorkspace
            ? requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace', { signal: query.signal })
            : Promise.resolve(null),
        ]);
        if (restored) {
          workspace = restored;
          hasWorkspaceSnapshot = true;
        }
        result = rawPage;
      }
      if (!query.reuseCachedGroups) rawGroups.clear();
      for (const group of result.items) rawGroups.set(group.group_id, group);
      const items = result.items.map(materialize);
      visibleGroupIds = new Set(items.map((group) => group.id));
      return {
        items,
        total: result.total,
        pageSize: result.page_size,
        page: result.page,
        nextCursor: result.page < result.pages ? String(result.page + 1) : null,
      };
    },
    saveDraft,
    flushDrafts,
    saveSelection,
    async applyPreset(disposition,scope,groupIds,reviewFilter,sourceFilter){
      await Promise.all([...draftQueues.values()]);
      const selectedView=reviewFilter==='Selected';
      const targetGroupIds=selectedView&&scope==='all_matching'?workspace.selected_group_ids:groupIds;
      workspace=await requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace/preset',jsonRequest('POST',{options:ANALYSIS_OPTIONS,scope:selectedView?'current_page':scope,group_ids:[...new Set(targetGroupIds)],review_filter:selectedView?'All groups':reviewFilter??'All groups',source_filter:sourceFilter,disposition}));
      return{appliedGroupIds:workspace.last_applied_group_ids??[],skippedGroupIds:workspace.last_skipped_group_ids??[]};
    },
    previewKeeperRules(input){return keeperSelection('preview',input)},
    applyKeeperRules(input){return keeperSelection('apply',input)},
    async clearDecisions() {
      const pendingDrafts = [...draftQueues.values()];
      if (pendingDrafts.length) await Promise.allSettled(pendingDrafts);
      workspace = await requestJson<ApiDuplicateWorkspace>(
        '/api/assets/duplicates/workspace/reset',
        jsonRequest('POST', { options: ANALYSIS_OPTIONS, all_decisions: true }),
      );
      draftQueues.clear();
      draftErrors.clear();
      hasWorkspaceSnapshot = true;
      return workspace.cleared_group_count ?? 0;
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
          max_link_depth: Math.min(64, Math.max(0, Math.round(options.maxLinkDepth))),
          anchor_asset_id: options.anchorAssetId,
          scope: 'all_eligible_assets',
          maximum_perceptual_distance: 12,
          maximum_aspect_difference: 0.05,
          maximum_neighbors_per_asset: Math.min(64, Math.max(1, options.maxCandidates)),
          maximum_matches: 5000,
        }));
        await waitForTask(tasks, started.task_id, true, options.includeExact ? exactEnd : 0, 98, onprogress);
      }
      const result = await requestJson<ApiDuplicateSummary>('/api/assets/duplicates/summary');
      onprogress?.({label:'Duplicate discovery · Preparing results',detail:'Preparing the completed duplicate groups for refresh…',completed:1,total:1,percent:99});
      return { groupCount: result.group_count, candidateCount: result.member_count };
    },
    async prepareDecisions(resolution: DuplicateResolutionPlan, groupIds: readonly string[]): Promise<DuplicatePreparedPlan> {
      const uniqueGroupIds = [...new Set(groupIds)];
      if (!uniqueGroupIds.length) {
        for (const stack of resolution.stacks) await saveWorkspaceStackResolution(stack);
        const requestedStackResolution = new Map(resolution.stacks.map((stack) => [stack.groupId, stack.stackResolution]));
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
            ...(requestedStackResolution.get(group.group_id) !== undefined ? { stackResolution: requestedStackResolution.get(group.group_id) } : {}),
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
      const page = pageNumber(query);
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(query.pageSize),
      });
      const days = historyDays(query.range);
      if (days !== null) params.set('days', String(days));
      const result = await requestJson<ApiDuplicateHistoryPage>(
        `/api/assets/duplicates/history?${params.toString()}`,
        { signal: query.signal },
      );
      return {
        items: result.items.map((item) => ({
          id: item.id,
          occurredAt: item.occurred_at,
          groupLabel: `Duplicate group · ${item.member_count} assets`,
          summary: historySummary(item),
        })),
        total: result.total,
        pageSize: result.page_size,
        page: result.page,
        nextCursor: result.page < result.pages ? String(result.page + 1) : null,
      };
    },
  };
}

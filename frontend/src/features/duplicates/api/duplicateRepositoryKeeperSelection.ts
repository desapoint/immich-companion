import { jsonRequest, requestJson } from '../../../lib/api/http';
import type { DuplicateKeeperSelectionInput, DuplicateKeeperSelectionResult } from '../types/contracts';
import type { ApiDuplicateKeeperSelectionResult, ApiDuplicateWorkspace, AnalysisOptions } from './duplicateRepository';

export function createKeeperSelectionController({
  getWorkspace, setWorkspace, draftQueues, setWorkspaceSnapshot, analysisOptions,
}: { getWorkspace: () => ApiDuplicateWorkspace; setWorkspace: (workspace: ApiDuplicateWorkspace) => void; draftQueues: Map<string, Promise<void>>; setWorkspaceSnapshot: (value: boolean) => void; analysisOptions: AnalysisOptions }) {
  return async (mode: 'preview' | 'apply', input: DuplicateKeeperSelectionInput): Promise<DuplicateKeeperSelectionResult> => {
    await Promise.all([...draftQueues.values()]);
    const workspace = getWorkspace();
    const selectedView = input.reviewFilter === 'Selected';
    const targetGroupIds = selectedView && input.scope === 'all_matching' ? workspace.selected_group_ids : input.groupIds;
    const result = await requestJson<ApiDuplicateKeeperSelectionResult>(`/api/assets/duplicates/workspace/auto-select/${mode}`, jsonRequest('POST', {
      options: analysisOptions, scope: selectedView ? 'current_page' : input.scope, group_ids: [...new Set(targetGroupIds)],
      review_filter: selectedView ? 'All groups' : input.reviewFilter ?? 'All groups', source_filter: input.sourceFilter, rules: input.rules, overwrite_manual: input.overwriteManual ?? false,
    }));
    if (mode === 'apply' && !result.limit_exceeded) {
      const refreshed = await requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace');
      const automatic = new Set(refreshed.drafts.filter((draft) => !draft.stale && draft.status === 'completed' && draft.decisions.length > 0 && draft.decisions.every((decision) => decision.source === 'automatic')).map((draft) => draft.group_id));
      setWorkspace(await requestJson<ApiDuplicateWorkspace>('/api/assets/duplicates/workspace/selection', jsonRequest('PUT', { options: analysisOptions, selected_group_ids: [...automatic], active_group_id: refreshed.active_group_id && automatic.has(refreshed.active_group_id) ? refreshed.active_group_id : null, revision: refreshed.revision })));
      setWorkspaceSnapshot(true);
    }
    return { matchedGroupCount: result.matched_group_count, validGroupCount: result.valid_group_count, resolvedGroupCount: result.resolved_group_count, wouldApplyGroupCount: result.would_apply_group_count, appliedGroupCount: result.applied_group_count, ambiguousGroupCount: result.ambiguous_group_count, blockedGroupCount: result.blocked_group_count, preservedManualGroupCount: result.preserved_manual_group_count, missingGroupCount: result.missing_group_count, keeperCount: result.keeper_count, trashCount: result.trash_count, limitExceeded: result.limit_exceeded };
  };
}

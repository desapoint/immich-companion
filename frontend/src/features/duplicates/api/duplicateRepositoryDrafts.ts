import { jsonRequest, requestJson } from '../../../lib/api/http';
import type { DuplicateResolutionPlan } from '../types/contracts';
import type { ApiDuplicateDraft, ApiDuplicateGroup, ApiDuplicateWorkspace, AnalysisOptions } from './duplicateRepository';
import { groupResolution, primaryFor } from './duplicateMapping';

export function createDuplicateDraftController({
  rawGroups,
  getWorkspace,
  setWorkspace,
  analysisOptions,
}: {
  rawGroups: Map<string, ApiDuplicateGroup>;
  getWorkspace: () => ApiDuplicateWorkspace;
  setWorkspace: (workspace: ApiDuplicateWorkspace) => void;
  analysisOptions: AnalysisOptions;
}) {
  const draftQueues = new Map<string, Promise<void>>();
  const draftErrors = new Map<string, unknown>();
  const draftFor = (groupId: string): ApiDuplicateDraft | undefined => getWorkspace().drafts.find((draft) => draft.group_id === groupId && !draft.stale);
  const replaceDraft = (draft: ApiDuplicateDraft): void => {
    const workspace = getWorkspace();
    setWorkspace({ ...workspace, drafts: [...workspace.drafts.filter((candidate) => candidate.group_id !== draft.group_id), draft] });
  };
  const writeDraft = async (groupId: string, resolution: DuplicateResolutionPlan): Promise<void> => {
    const group = rawGroups.get(groupId);
    if (!group) throw new Error(`Duplicate group ${groupId} is no longer available.`);
    const scoped = groupResolution(resolution, group);
    const memberIds = group.members.map((member) => member.id);
    const primary = primaryFor(scoped, memberIds);
    const survivors = memberIds.filter((id) => scoped.decisions[id] !== 'delete');
    const stackByAsset = new Map(scoped.stacks.flatMap((stack) => stack.assetIds.map((assetId) => [assetId, stack] as const)));
    const draft = await requestJson<ApiDuplicateDraft>('/api/assets/duplicates/workspace/group', jsonRequest('PUT', {
      group_id: groupId, member_fingerprint: group.member_fingerprint, options: analysisOptions,
      decisions: Object.entries(scoped.decisions).map(([asset_id, disposition]) => {
        const stack = stackByAsset.get(asset_id);
        return {
          asset_id, disposition, source: 'manual', status: 'pending',
          ...(stack ? {
            stack_id: stack.id,
            stack_primary: stack.primaryAssetId === asset_id,
          } : {}),
        };
      }),
      stack_primary_asset_id: scoped.stacks[0]?.primaryAssetId ?? (Object.values(scoped.decisions).includes('stack') ? primary : null),
      // Existing-Immich reconciliation is review-time state. Draft autosave only
      // persists the user's pending topology so intermediate stack construction
      // cannot fail validation against stale/live Immich stack choices.
      stack_resolution: 'move_selected',
      metadata_keeper_asset_id: Object.values(scoped.decisions).includes('delete') && survivors.length === 1 ? survivors[0] : null,
      status: Object.keys(scoped.decisions).length === memberIds.length ? 'completed' : 'pending',
    }));
    replaceDraft(draft);
  };
  const saveDraft = (groupId: string, resolution: DuplicateResolutionPlan): Promise<void> => {
    const queued = (draftQueues.get(groupId) ?? Promise.resolve()).catch(() => undefined).then(() => writeDraft(groupId, resolution));
    draftQueues.set(groupId, queued);
    void queued.then(() => { draftErrors.delete(groupId); if (draftQueues.get(groupId) === queued) draftQueues.delete(groupId); }, (error) => { draftErrors.set(groupId, error); if (draftQueues.get(groupId) === queued) draftQueues.delete(groupId); });
    return queued;
  };
  const flushDrafts = async (): Promise<void> => { await Promise.all([...draftQueues.values()]); const failure = draftErrors.values().next().value; if (failure !== undefined) throw failure; };
  return { draftFor, saveDraft, flushDrafts, draftQueues, draftErrors };
}

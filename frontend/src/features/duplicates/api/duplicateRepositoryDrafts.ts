import { jsonRequest, requestJson } from '../../../lib/api/http';
import type { DuplicateResolutionPlan } from '../types/contracts';
import { serializeStackResolution } from '../types/stackResolution';
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
            stack_resolution: stack.primaryAssetId === asset_id ? serializeStackResolution(stack.stackResolution) : null,
          } : {}),
        };
      }),
      stack_primary_asset_id: scoped.stacks[0]?.primaryAssetId ?? (Object.values(scoped.decisions).includes('stack') ? primary : null),
      stack_resolution: serializeStackResolution(scoped.stacks[0]?.stackResolution),
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
  const saveWorkspaceStackResolution = async (stack: DuplicateResolutionPlan['stacks'][number]): Promise<void> => {
    if (stack.stackResolution === undefined) return;
    const draft = draftFor(stack.groupId);
    if (!draft) throw new Error(`Duplicate group ${stack.groupId} no longer has a current saved draft.`);
    const targetIds = [...stack.assetIds].sort().join('\n');
    const grouped = new Map<string, string[]>();
    for (const decision of draft.decisions) {
      if (!decision.stack_id) continue;
      grouped.set(decision.stack_id, [...(grouped.get(decision.stack_id) ?? []), decision.asset_id]);
    }
    const persistedId = [...grouped].find(([, ids]) => [...ids].sort().join('\n') === targetIds)?.[0] ?? stack.id;
    const stackIds = new Set(stack.assetIds);
    const serialized = serializeStackResolution(stack.stackResolution);
    const decisions = draft.decisions.map((decision) => (
      stackIds.has(decision.asset_id)
        ? {
            ...decision,
            stack_id: persistedId,
            stack_primary: decision.asset_id === stack.primaryAssetId,
            stack_resolution: decision.asset_id === stack.primaryAssetId ? serialized : null,
          }
        : decision
    ));
    const updated = await requestJson<ApiDuplicateDraft>('/api/assets/duplicates/workspace/group', jsonRequest('PUT', {
      group_id: stack.groupId, member_fingerprint: draft.member_fingerprint, options: analysisOptions, decisions,
      stack_primary_asset_id: stack.primaryAssetId ?? draft.stack_primary_asset_id, stack_resolution: serialized,
      metadata_keeper_asset_id: draft.metadata_keeper_asset_id ?? null, status: draft.status,
    }));
    replaceDraft(updated);
  };
  return { draftFor, saveDraft, flushDrafts, saveWorkspaceStackResolution, draftQueues, draftErrors };
}

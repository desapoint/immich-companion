import type { DuplicateGroupRecord, DuplicateResolutionPlan } from '../types/contracts';
import { flattenDecisionWorkspace, decisionsForGroup, type DuplicateDecisionWorkspace } from './duplicateDecisionWorkspace';
import { stacksForGroup, type DuplicateStackWorkspace } from './duplicateStackResolution';

export function currentResolution(workspace: DuplicateStackWorkspace, decisions: Readonly<DuplicateDecisionWorkspace>): DuplicateResolutionPlan {
  const flat = flattenDecisionWorkspace(decisions);
  return {
    decisions: flat,
    stacks: Object.values(workspace.stacks)
      .filter((stack) => {
        const group = decisionsForGroup(decisions, stack.groupId);
        return stack.assetIds.length > 0
          && stack.primaryAssetId
          && stack.assetIds.includes(stack.primaryAssetId)
          && stack.assetIds.every((id) => group[id] === 'stack');
      })
      .map((stack) => ({ ...stack, assetIds: [...stack.assetIds] })),
  };
}

export function groupResolution(workspace: DuplicateStackWorkspace, item: DuplicateGroupRecord, decisions: Readonly<DuplicateDecisionWorkspace>): DuplicateResolutionPlan {
  const ids = new Set(item.members.map((entry) => entry.asset.id));
  const current = decisionsForGroup(decisions, item.id);
  const groupDecisions = Object.fromEntries(Object.entries(current).filter(([id]) => ids.has(id)));
  return {
    decisions: groupDecisions,
    stacks: stacksForGroup(workspace, item.id)
      .filter((stack) => stack.assetIds.length > 0 && stack.primaryAssetId && stack.assetIds.includes(stack.primaryAssetId) && stack.assetIds.every((id) => groupDecisions[id] === 'stack'))
      .map((stack) => ({ ...stack, assetIds: [...stack.assetIds] })),
  };
}

export function groupComplete(item: DuplicateGroupRecord, decisions: Readonly<DuplicateDecisionWorkspace>): boolean {
  const current = decisionsForGroup(decisions, item.id);
  return item.members.length > 0 && item.members.every((entry) => Boolean(current[entry.asset.id]));
}

export function groupHasInvalidStack(workspace: DuplicateStackWorkspace, item: DuplicateGroupRecord): boolean {
  return stacksForGroup(workspace, item.id).some((stack) => stack.assetIds.length === 1);
}

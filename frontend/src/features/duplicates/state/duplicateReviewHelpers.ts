import type { DuplicateDecision, DuplicateGroupRecord, DuplicateResolutionPlan } from '../types/contracts';
import { stacksForGroup, type DuplicateStackWorkspace } from './duplicateStackResolution';

export function currentResolution(workspace: DuplicateStackWorkspace, decisions: Readonly<Record<string, DuplicateDecision>>): DuplicateResolutionPlan {
  return { decisions: { ...decisions }, stacks: Object.values(workspace.stacks).filter((stack) => stack.assetIds.length > 0 && stack.primaryAssetId && stack.assetIds.includes(stack.primaryAssetId) && stack.assetIds.every((id) => decisions[id] === 'stack')).map((stack) => ({ ...stack, assetIds: [...stack.assetIds] })) };
}

export function groupResolution(workspace: DuplicateStackWorkspace, item: DuplicateGroupRecord, decisions: Readonly<Record<string, DuplicateDecision>>): DuplicateResolutionPlan {
  const ids = new Set(item.members.map((entry) => entry.asset.id));
  const groupDecisions = Object.fromEntries(Object.entries(decisions).filter(([id]) => ids.has(id))) as Record<string, DuplicateDecision>;
  return { decisions: groupDecisions, stacks: stacksForGroup(workspace, item.id).filter((stack) => stack.assetIds.length > 0 && stack.primaryAssetId && stack.assetIds.includes(stack.primaryAssetId) && stack.assetIds.every((id) => groupDecisions[id] === 'stack')).map((stack) => ({ ...stack, assetIds: [...stack.assetIds] })) };
}

export function groupComplete(item: DuplicateGroupRecord, decisions: Readonly<Record<string, DuplicateDecision>>): boolean {
  return item.members.length > 0 && item.members.every((entry) => Boolean(decisions[entry.asset.id]));
}

export function groupHasInvalidStack(workspace: DuplicateStackWorkspace, item: DuplicateGroupRecord): boolean {
  return stacksForGroup(workspace, item.id).some((stack) => stack.assetIds.length === 1);
}

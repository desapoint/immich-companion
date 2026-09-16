import type { DuplicateGroupRecord, DuplicatePendingStack } from '../data/contracts';

export type DuplicateStackWorkspace = {
  activeByGroup: Record<string, string>;
  nextOrdinalByGroup: Record<string, number>;
  assetToStack: Record<string, string>;
  stacks: Record<string, DuplicatePendingStack>;
};

export function createDuplicateStackWorkspace(): DuplicateStackWorkspace {
  return { activeByGroup: {}, nextOrdinalByGroup: {}, assetToStack: {}, stacks: {} };
}

function stackId(groupId: string, ordinal: number): string {
  return `group-${groupId}-stack-${ordinal}`;
}

export function createPendingStack(workspace: DuplicateStackWorkspace, groupId: string): DuplicateStackWorkspace {
  const ordinal = workspace.nextOrdinalByGroup[groupId] ?? 1;
  const id = stackId(groupId, ordinal);
  return {
    ...workspace,
    activeByGroup: { ...workspace.activeByGroup, [groupId]: id },
    nextOrdinalByGroup: { ...workspace.nextOrdinalByGroup, [groupId]: ordinal + 1 },
    stacks: {
      ...workspace.stacks,
      [id]: { id, groupId, label: `Stack ${ordinal}`, assetIds: [], primaryAssetId: null },
    },
  };
}

export function ensurePendingStack(workspace: DuplicateStackWorkspace, groupId: string): DuplicateStackWorkspace {
  const active = workspace.activeByGroup[groupId];
  if (active && workspace.stacks[active]) return workspace;
  return createPendingStack(workspace, groupId);
}

export function selectPendingStack(workspace: DuplicateStackWorkspace, groupId: string, id: string): DuplicateStackWorkspace {
  const stack = workspace.stacks[id];
  if (!stack || stack.groupId !== groupId) return workspace;
  return { ...workspace, activeByGroup: { ...workspace.activeByGroup, [groupId]: id } };
}

export function assignAssetToActiveStack(workspace: DuplicateStackWorkspace, groupId: string, assetId: string): DuplicateStackWorkspace {
  let next = ensurePendingStack(workspace, groupId);
  const targetId = next.activeByGroup[groupId];
  if (!targetId) return next;
  const previousId = next.assetToStack[assetId];
  if (previousId === targetId) return next;
  if (previousId) next = removeAssetFromPendingStack(next, assetId);
  const target = next.stacks[targetId];
  if (!target) return next;
  const assetIds = [...target.assetIds, assetId];
  return {
    ...next,
    assetToStack: { ...next.assetToStack, [assetId]: targetId },
    stacks: {
      ...next.stacks,
      [targetId]: {
        ...target,
        assetIds,
        primaryAssetId: target.primaryAssetId ?? assetId,
      },
    },
  };
}

export function removeAssetFromPendingStack(workspace: DuplicateStackWorkspace, assetId: string): DuplicateStackWorkspace {
  const id = workspace.assetToStack[assetId];
  if (!id) return workspace;
  const stack = workspace.stacks[id];
  if (!stack) return workspace;
  const assetIds = stack.assetIds.filter((value) => value !== assetId);
  const assetToStack = { ...workspace.assetToStack };
  delete assetToStack[assetId];
  const primaryAssetId = stack.primaryAssetId === assetId ? (assetIds[0] ?? null) : stack.primaryAssetId;
  return {
    ...workspace,
    assetToStack,
    stacks: { ...workspace.stacks, [id]: { ...stack, assetIds, primaryAssetId } },
  };
}

export function setPendingStackPrimary(workspace: DuplicateStackWorkspace, assetId: string): DuplicateStackWorkspace {
  const id = workspace.assetToStack[assetId];
  if (!id) return workspace;
  const stack = workspace.stacks[id];
  if (!stack?.assetIds.includes(assetId)) return workspace;
  return { ...workspace, stacks: { ...workspace.stacks, [id]: { ...stack, primaryAssetId: assetId } } };
}

export function stackForAsset(workspace: DuplicateStackWorkspace, assetId: string): DuplicatePendingStack | null {
  const id = workspace.assetToStack[assetId];
  return id ? workspace.stacks[id] ?? null : null;
}

export function stacksForGroup(workspace: DuplicateStackWorkspace, groupId: string): DuplicatePendingStack[] {
  return Object.values(workspace.stacks)
    .filter((stack) => stack.groupId === groupId)
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
}

export function resolutionStacks(workspace: DuplicateStackWorkspace): DuplicatePendingStack[] {
  return Object.values(workspace.stacks)
    .filter((stack) => stack.assetIds.length >= 2 && stack.primaryAssetId && stack.assetIds.includes(stack.primaryAssetId))
    .map((stack) => ({ ...stack, assetIds: [...stack.assetIds] }));
}

export function invalidPendingStacks(workspace: DuplicateStackWorkspace): DuplicatePendingStack[] {
  return Object.values(workspace.stacks).filter((stack) => stack.assetIds.length === 1);
}

export function clearGroupStacks(workspace: DuplicateStackWorkspace, groupId: string): DuplicateStackWorkspace {
  const groupStackIds = new Set(stacksForGroup(workspace, groupId).map((stack) => stack.id));
  const stacks = Object.fromEntries(Object.entries(workspace.stacks).filter(([id]) => !groupStackIds.has(id)));
  const assetToStack = Object.fromEntries(Object.entries(workspace.assetToStack).filter(([, id]) => !groupStackIds.has(id)));
  const activeByGroup = { ...workspace.activeByGroup };
  delete activeByGroup[groupId];
  return { ...workspace, stacks, assetToStack, activeByGroup };
}

export function assignGroupToSingleStack(workspace: DuplicateStackWorkspace, group: DuplicateGroupRecord): DuplicateStackWorkspace {
  let next = createPendingStack(clearGroupStacks(workspace, group.id), group.id);
  for (const member of group.members) next = assignAssetToActiveStack(next, group.id, member.asset.id);
  return next;
}

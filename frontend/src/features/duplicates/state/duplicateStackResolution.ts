import type { DuplicateGroupRecord, DuplicatePendingStack, StackResolutionSelection } from '../types/contracts';

export type DuplicateStackWorkspace = {
  activeByGroup: Record<string, string>;
  nextOrdinalByGroup: Record<string, number>;
  assetToStackByGroup: Record<string, Record<string, string>>;
  stacks: Record<string, DuplicatePendingStack>;
};

export function createDuplicateStackWorkspace(): DuplicateStackWorkspace {
  return { activeByGroup: {}, nextOrdinalByGroup: {}, assetToStackByGroup: {}, stacks: {} };
}

function stackId(groupId: string, ordinal: number): string {
  return `group-${groupId}-stack-${ordinal}`;
}

function assetStackId(workspace: DuplicateStackWorkspace, groupId: string, assetId: string): string | undefined {
  return workspace.assetToStackByGroup[groupId]?.[assetId];
}

function withAssetStack(
  workspace: DuplicateStackWorkspace,
  groupId: string,
  assetId: string,
  stackIdValue: string | null,
): Record<string, Record<string, string>> {
  const next = { ...workspace.assetToStackByGroup };
  const group = { ...(next[groupId] ?? {}) };
  if (stackIdValue) group[assetId] = stackIdValue;
  else delete group[assetId];
  if (Object.keys(group).length) next[groupId] = group;
  else delete next[groupId];
  return next;
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
  const previousId = assetStackId(next, groupId, assetId);
  if (previousId === targetId) return next;
  if (previousId) next = removeAssetFromPendingStack(next, groupId, assetId);
  const target = next.stacks[targetId];
  if (!target) return next;
  const assetIds = [...target.assetIds, assetId];
  return {
    ...next,
    assetToStackByGroup: withAssetStack(next, groupId, assetId, targetId),
    stacks: {
      ...next.stacks,
      [targetId]: {
        ...target,
        assetIds,
        primaryAssetId: target.primaryAssetId ?? assetId,
        stackResolution: undefined,
      },
    },
  };
}

export function removeAssetFromPendingStack(workspace: DuplicateStackWorkspace, groupId: string, assetId: string): DuplicateStackWorkspace {
  const id = assetStackId(workspace, groupId, assetId);
  if (!id) return workspace;
  const stack = workspace.stacks[id];
  if (!stack || stack.groupId !== groupId) return workspace;
  const assetIds = stack.assetIds.filter((value) => value !== assetId);
  const assetToStackByGroup = withAssetStack(workspace, groupId, assetId, null);
  if (!assetIds.length) {
    const stacks = { ...workspace.stacks };
    delete stacks[id];
    const activeByGroup = { ...workspace.activeByGroup };
    if (activeByGroup[groupId] === id) {
      const replacement = Object.values(stacks).find((candidate) => candidate.groupId === groupId);
      if (replacement) activeByGroup[groupId] = replacement.id;
      else delete activeByGroup[groupId];
    }
    return { ...workspace, assetToStackByGroup, stacks, activeByGroup };
  }
  const primaryAssetId = stack.primaryAssetId === assetId ? assetIds[0] : stack.primaryAssetId;
  return {
    ...workspace,
    assetToStackByGroup,
    stacks: { ...workspace.stacks, [id]: { ...stack, assetIds, primaryAssetId, stackResolution: undefined } },
  };
}

export function setPendingStackPrimary(workspace: DuplicateStackWorkspace, groupId: string, assetId: string): DuplicateStackWorkspace {
  const id = assetStackId(workspace, groupId, assetId);
  if (!id) return workspace;
  const stack = workspace.stacks[id];
  if (!stack || stack.groupId !== groupId || !stack.assetIds.includes(assetId)) return workspace;
  return { ...workspace, stacks: { ...workspace.stacks, [id]: { ...stack, primaryAssetId: assetId, stackResolution: undefined } } };
}

export function setPendingStackResolution(workspace: DuplicateStackWorkspace, id: string, stackResolution: StackResolutionSelection | undefined): DuplicateStackWorkspace {
  const stack = workspace.stacks[id];
  if (!stack) return workspace;
  return { ...workspace, stacks: { ...workspace.stacks, [id]: { ...stack, stackResolution } } };
}

export function stackForAsset(workspace: DuplicateStackWorkspace, groupId: string, assetId: string): DuplicatePendingStack | null {
  const id = assetStackId(workspace, groupId, assetId);
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
  const assetToStackByGroup = { ...workspace.assetToStackByGroup };
  delete assetToStackByGroup[groupId];
  const activeByGroup = { ...workspace.activeByGroup };
  const nextOrdinalByGroup = { ...workspace.nextOrdinalByGroup };
  delete activeByGroup[groupId];
  delete nextOrdinalByGroup[groupId];
  return { ...workspace, stacks, assetToStackByGroup, activeByGroup, nextOrdinalByGroup };
}

export function assignGroupToSingleStack(workspace: DuplicateStackWorkspace, group: DuplicateGroupRecord): DuplicateStackWorkspace {
  let next = createPendingStack(clearGroupStacks(workspace, group.id), group.id);
  for (const member of group.members) next = assignAssetToActiveStack(next, group.id, member.asset.id);
  return next;
}

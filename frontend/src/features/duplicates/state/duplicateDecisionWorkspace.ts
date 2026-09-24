import type { DuplicateDecision } from '../types/contracts';

export type DuplicateDecisionWorkspace = Record<string, Record<string, DuplicateDecision>>;

export function decisionsForGroup(
  workspace: Readonly<DuplicateDecisionWorkspace>,
  groupId: string,
): Readonly<Record<string, DuplicateDecision>> {
  return workspace[groupId] ?? {};
}

export function decisionFor(
  workspace: Readonly<DuplicateDecisionWorkspace>,
  groupId: string,
  assetId: string,
): DuplicateDecision | undefined {
  return workspace[groupId]?.[assetId];
}

export function setGroupDecision(
  workspace: Readonly<DuplicateDecisionWorkspace>,
  groupId: string,
  assetId: string,
  decision: DuplicateDecision,
): DuplicateDecisionWorkspace {
  return {
    ...workspace,
    [groupId]: {
      ...(workspace[groupId] ?? {}),
      [assetId]: decision,
    },
  };
}

export function clearGroupDecision(
  workspace: Readonly<DuplicateDecisionWorkspace>,
  groupId: string,
  assetId: string,
): DuplicateDecisionWorkspace {
  const current = workspace[groupId];
  if (!current?.[assetId]) return workspace as DuplicateDecisionWorkspace;
  const nextGroup = { ...current };
  delete nextGroup[assetId];
  const next = { ...workspace };
  if (Object.keys(nextGroup).length) next[groupId] = nextGroup;
  else delete next[groupId];
  return next;
}

export function replaceGroupDecisions(
  workspace: Readonly<DuplicateDecisionWorkspace>,
  groupId: string,
  decisions: Readonly<Record<string, DuplicateDecision>>,
): DuplicateDecisionWorkspace {
  const next = { ...workspace };
  if (Object.keys(decisions).length) next[groupId] = { ...decisions };
  else delete next[groupId];
  return next;
}

export function clearGroupDecisions(
  workspace: Readonly<DuplicateDecisionWorkspace>,
  groupId: string,
): DuplicateDecisionWorkspace {
  if (!(groupId in workspace)) return workspace as DuplicateDecisionWorkspace;
  const next = { ...workspace };
  delete next[groupId];
  return next;
}

export function decisionCount(workspace: Readonly<DuplicateDecisionWorkspace>): number {
  return Object.values(workspace).reduce((total, group) => total + Object.keys(group).length, 0);
}

export function flattenDecisionWorkspace(
  workspace: Readonly<DuplicateDecisionWorkspace>,
): Record<string, DuplicateDecision> {
  return Object.assign({}, ...Object.values(workspace));
}

export function filterDecisionWorkspaceByAssets(
  workspace: Readonly<DuplicateDecisionWorkspace>,
  assetIds: ReadonlySet<string>,
): DuplicateDecisionWorkspace {
  const next: DuplicateDecisionWorkspace = {};
  for (const [groupId, group] of Object.entries(workspace)) {
    const filtered = Object.fromEntries(
      Object.entries(group).filter(([assetId]) => assetIds.has(assetId)),
    ) as Record<string, DuplicateDecision>;
    if (Object.keys(filtered).length) next[groupId] = filtered;
  }
  return next;
}

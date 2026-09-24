import type { DuplicatePendingStack, DuplicateResolutionPlan } from '../types/contracts';

export type DuplicateDestinationConflictTarget = {
  id: string;
  stackIds: string[];
  sharedAssetIds: string[];
  options: DuplicatePendingStack[];
};

export type DuplicateDestinationConflictResult = Record<string, string>;

function stable(values: readonly string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}

function sourceGroups(stack: DuplicatePendingStack): string[] {
  return stable(stack.sourceGroupIds?.length ? stack.sourceGroupIds : [stack.groupId]);
}

export function duplicateDestinationConflicts(
  stacks: readonly DuplicatePendingStack[],
): DuplicateDestinationConflictTarget[] {
  const valid = stacks.filter((stack) => (
    stack.assetIds.length >= 2
    && stack.primaryAssetId !== null
    && stack.assetIds.includes(stack.primaryAssetId)
  ));
  const byAsset = new Map<string, number[]>();
  valid.forEach((stack, index) => {
    for (const assetId of new Set(stack.assetIds)) {
      byAsset.set(assetId, [...(byAsset.get(assetId) ?? []), index]);
    }
  });

  const adjacency = valid.map(() => new Set<number>());
  for (const indices of byAsset.values()) {
    if (indices.length < 2) continue;
    for (const left of indices) {
      for (const right of indices) {
        if (left !== right) adjacency[left].add(right);
      }
    }
  }

  const visited = new Set<number>();
  const conflicts: DuplicateDestinationConflictTarget[] = [];
  for (let start = 0; start < valid.length; start += 1) {
    if (visited.has(start) || adjacency[start].size === 0) continue;
    const queue = [start];
    const component: number[] = [];
    visited.add(start);
    while (queue.length) {
      const current = queue.shift();
      if (current === undefined) break;
      component.push(current);
      for (const neighbor of adjacency[current]) {
        if (visited.has(neighbor)) continue;
        visited.add(neighbor);
        queue.push(neighbor);
      }
    }
    if (component.length < 2) continue;
    const options = component.map((index) => valid[index]);
    const counts = new Map<string, number>();
    for (const stack of options) {
      for (const assetId of new Set(stack.assetIds)) {
        counts.set(assetId, (counts.get(assetId) ?? 0) + 1);
      }
    }
    const stackIds = stable(options.map((stack) => stack.id));
    conflicts.push({
      id: `proposed-stack-conflict:${stackIds.join('|')}`,
      stackIds,
      sharedAssetIds: stable([...counts].filter(([, count]) => count > 1).map(([assetId]) => assetId)),
      options: options.map((stack) => ({ ...stack, assetIds: [...stack.assetIds], sourceGroupIds: sourceGroups(stack) })),
    });
  }
  return conflicts.sort((left, right) => left.id.localeCompare(right.id));
}

export function applyDuplicateDestinationReview(
  resolution: DuplicateResolutionPlan,
  targets: readonly DuplicateDestinationConflictTarget[],
  choices: Readonly<DuplicateDestinationConflictResult>,
): DuplicateResolutionPlan {
  if (!targets.length) return resolution;
  const consumed = new Set(targets.flatMap((target) => target.stackIds));
  const merged = targets.map((target) => {
    const preferredId = choices[target.id];
    const preferred = target.options.find((stack) => stack.id === preferredId);
    if (!preferred) throw new Error('Every overlapping proposed stack needs a preferred destination.');
    const orderedOptions = [
      preferred,
      ...target.options.filter((stack) => stack.id !== preferred.id),
    ];
    const assetIds = [...new Set(orderedOptions.flatMap((stack) => stack.assetIds))];
    const sourceGroupIds = stable(orderedOptions.flatMap(sourceGroups));
    return {
      ...preferred,
      label: preferred.label.startsWith('Merged ') ? preferred.label : `Merged ${preferred.label}`,
      assetIds,
      primaryAssetId: preferred.primaryAssetId && assetIds.includes(preferred.primaryAssetId)
        ? preferred.primaryAssetId
        : assetIds[0] ?? null,
      stackResolution: undefined,
      sourceGroupIds,
    } satisfies DuplicatePendingStack;
  });

  return {
    decisions: { ...resolution.decisions },
    stacks: [
      ...resolution.stacks.filter((stack) => !consumed.has(stack.id)).map((stack) => ({ ...stack, assetIds: [...stack.assetIds] })),
      ...merged,
    ],
  };
}

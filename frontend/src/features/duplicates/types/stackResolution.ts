import type {
  StackActionPlan,
  StackResolution,
  StackResolutionMap,
  StackResolutionSelection,
} from '../types/contracts';

const STACK_RESOLUTIONS = new Set<StackResolution>(['keep_existing', 'move_selected', 'include_existing']);

export type StackConflictReviewTarget = {
  id: string;
  label: string;
  primaryLabel: string;
  plan: StackActionPlan;
  resolution: StackResolutionSelection | null;
};

function normalizedMap(value: Record<string, unknown>): StackResolutionMap {
  return Object.fromEntries(
    Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([stackId, choice]) => {
        if (typeof choice !== 'string' || !STACK_RESOLUTIONS.has(choice as StackResolution)) {
          throw new Error(`Unknown stack resolution for ${stackId}.`);
        }
        return [stackId, choice as StackResolution];
      }),
  );
}

export function parseStackResolution(value: unknown): StackResolutionSelection {
  if (typeof value === 'string') {
    if (STACK_RESOLUTIONS.has(value as StackResolution)) return value as StackResolution;
    let decoded: unknown;
    try {
      decoded = JSON.parse(value);
    } catch {
      throw new Error('Saved stack conflict resolution is invalid.');
    }
    if (!decoded || typeof decoded !== 'object' || Array.isArray(decoded)) {
      throw new Error('Saved stack conflict resolution is invalid.');
    }
    return normalizedMap(decoded as Record<string, unknown>);
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return normalizedMap(value as Record<string, unknown>);
  }
  throw new Error('Saved stack conflict resolution is invalid.');
}

export function serializeStackResolution(value: StackResolutionSelection | null | undefined): string {
  const normalized = parseStackResolution(value ?? 'move_selected');
  return typeof normalized === 'string' ? normalized : JSON.stringify(normalized);
}

function normalizedSelection(
  resolution: StackResolutionSelection | null | undefined,
): StackResolutionSelection | null {
  if (!resolution) return null;
  if (typeof resolution !== 'string' || STACK_RESOLUTIONS.has(resolution as StackResolution)) return resolution;
  // The Assets page historically stores the reviewed resolution in scalar state.
  // Accept a canonical serialized map so that page can use the shared multi-conflict modal
  // without weakening the public StackResolution literal type.
  return parseStackResolution(resolution);
}

export function conflictResolutionMap(
  plan: StackActionPlan,
  resolution: StackResolutionSelection | null | undefined,
): StackResolutionMap {
  const normalized = normalizedSelection(resolution);
  if (!normalized) return {};
  if (typeof normalized === 'string') {
    return Object.fromEntries(plan.conflicts.map((conflict) => [conflict.stackId, normalized]));
  }
  const ids = new Set(plan.conflicts.map((conflict) => conflict.stackId));
  return Object.fromEntries(Object.entries(normalized).filter(([stackId]) => ids.has(stackId)));
}

export function withConflictResolution(
  plan: StackActionPlan,
  resolution: StackResolutionSelection | null | undefined,
  stackId: string,
  choice: StackResolution,
): StackResolutionMap {
  return { ...conflictResolutionMap(plan, resolution), [stackId]: choice };
}

export function projectedStackCount(
  plan: StackActionPlan,
  resolution: StackResolutionSelection | null | undefined,
): number {
  const choices = conflictResolutionMap(plan, resolution);
  let count = plan.targetCount;
  for (const conflict of plan.conflicts) {
    const choice = choices[conflict.stackId];
    if (choice === 'keep_existing') count -= conflict.selectedCount;
    if (choice === 'include_existing') count += conflict.memberCount - conflict.selectedCount;
  }
  return count;
}

export function stackReviewComplete(target: StackConflictReviewTarget): boolean {
  const choices = conflictResolutionMap(target.plan, target.resolution);
  if (target.plan.conflicts.some((conflict) => !choices[conflict.stackId])) return false;
  if (projectedStackCount(target.plan, target.resolution) < 2) return false;
  return !target.plan.conflicts.some((conflict) => (
    choices[conflict.stackId] === 'keep_existing'
    && (conflict.selectedAssetIds ?? []).includes(target.plan.primaryAssetId)
  ));
}

export function sharedConflictIds(targets: readonly StackConflictReviewTarget[]): Set<string> {
  const counts = new Map<string, number>();
  for (const target of targets) {
    for (const conflict of target.plan.conflicts) {
      counts.set(conflict.stackId, (counts.get(conflict.stackId) ?? 0) + 1);
    }
  }
  return new Set([...counts].filter(([, count]) => count > 1).map(([stackId]) => stackId));
}

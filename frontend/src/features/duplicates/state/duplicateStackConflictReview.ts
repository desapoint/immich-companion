import type {
  AssetRecord,
  AssetRepository,
  DuplicatePendingStack,
  StackActionPlan,
  StackConflict,
  StackResolutionMap,
} from '../types/contracts';
import { stackReviewComplete, type StackConflictReviewTarget } from '../types/stackResolution';

function stableIds(ids: readonly string[]): string[] {
  return [...new Set(ids)].sort((left, right) => left.localeCompare(right));
}

function topologyKey(stack: NonNullable<AssetRecord['stack']>): string {
  return JSON.stringify({
    id: stack.id,
    primaryAssetId: stack.primaryAssetId,
    assets: stableIds(stack.assets),
  });
}

export async function duplicateStackConflictReviews(
  stacks: readonly DuplicatePendingStack[],
  assets: AssetRepository,
): Promise<StackConflictReviewTarget[]> {
  const destinations = stacks.filter((stack) => (
    stack.assetIds.length >= 2
    && stack.primaryAssetId !== null
    && stack.assetIds.includes(stack.primaryAssetId)
  ));
  if (!destinations.length) return [];

  const requestedIds = stableIds(destinations.flatMap((stack) => stack.assetIds));
  const loaded = await assets.getMany(requestedIds);
  const byId = new Map(loaded.map((asset) => [asset.id, asset]));
  const missing = requestedIds.filter((id) => !byId.has(id));
  if (missing.length) {
    throw new Error(`${missing.length.toLocaleString()} stack asset${missing.length === 1 ? '' : 's'} changed or disappeared while conflict review was being prepared. Refresh duplicates and review again.`);
  }

  const topologyByStack = new Map<string, string>();
  const sourceByStack = new Map<string, NonNullable<AssetRecord['stack']>>();
  for (const asset of loaded) {
    if (!asset.stack) continue;
    const key = topologyKey(asset.stack);
    const previous = topologyByStack.get(asset.stack.id);
    if (previous !== undefined && previous !== key) {
      throw new Error('Existing stack membership changed while conflict review was being prepared. Refresh duplicates and review again.');
    }
    topologyByStack.set(asset.stack.id, key);
    sourceByStack.set(asset.stack.id, asset.stack);
  }

  return destinations.flatMap((destination, index) => {
    const selected = new Set(destination.assetIds);
    const touched = new Map<string, StackConflict>();
    for (const assetId of destination.assetIds) {
      const source = byId.get(assetId)?.stack;
      if (!source || touched.has(source.id)) continue;
      const authoritative = sourceByStack.get(source.id) ?? source;
      const members = stableIds(authoritative.assets);
      if (members.length !== authoritative.assetCount) {
        throw new Error('An existing stack could not be loaded completely for visual conflict review. Refresh assets and try again.');
      }
      const selectedAssetIds = members.filter((id) => selected.has(id));
      if (!selectedAssetIds.length) continue;
      touched.set(source.id, {
        stackId: source.id,
        primaryAssetId: authoritative.primaryAssetId,
        memberAssetIds: members,
        selectedAssetIds,
        selectedCount: selectedAssetIds.length,
        memberCount: members.length,
        includesUnselected: selectedAssetIds.length < members.length,
      });
    }
    if (!touched.size) return [];
    const plan: StackActionPlan = {
      id: `duplicate-stack-review:${destination.id}`,
      targetCount: destination.assetIds.length,
      primaryAssetId: destination.primaryAssetId as string,
      targetAssetIds: [...destination.assetIds],
      conflicts: [...touched.values()].sort((left, right) => left.stackId.localeCompare(right.stackId)),
    };
    const primary = byId.get(destination.primaryAssetId as string);
    return [{
      id: destination.id,
      label: destination.label === 'Frozen stack' ? `Duplicate stack ${index + 1}` : destination.label,
      primaryLabel: primary?.original_file_name ?? `Asset ${(destination.primaryAssetId as string).slice(0, 8)}`,
      plan,
      // Scalar move_selected is the historical default, not evidence that the user reviewed
      // these specific current source stacks. Only seed a previously reviewed map.
      resolution: destination.stackResolution && typeof destination.stackResolution !== 'string'
        ? destination.stackResolution
        : null,
    } satisfies StackConflictReviewTarget];
  });
}

export function applyDuplicateStackReview(
  stacks: readonly DuplicatePendingStack[],
  result: Readonly<Record<string, StackResolutionMap>>,
): DuplicatePendingStack[] {
  return stacks.map((stack) => result[stack.id] ? { ...stack, stackResolution: result[stack.id] } : { ...stack });
}

export function duplicateStackReviewIsCurrent(
  targets: readonly StackConflictReviewTarget[],
): boolean {
  return targets.every((target) => stackReviewComplete(target));
}

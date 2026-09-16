import type { AssetRepository, DuplicateRepository, DuplicateResolutionPlan } from './contracts';
import {
  applyDuplicateStackReview,
  duplicateStackConflictReviews,
  duplicateStackReviewIsCurrent,
} from './duplicateStackConflictReview';
import { requestStackConflictReview } from './stackConflictReviewBridge';
import { conflictResolutionMap, sharedConflictIds, type StackConflictReviewTarget } from './stackResolution';

function reviewedTargetsAreSafe(targets: readonly StackConflictReviewTarget[]): boolean {
  if (!duplicateStackReviewIsCurrent(targets)) return false;
  const shared = sharedConflictIds(targets);
  if (!shared.size) return true;
  return targets.every((target) => {
    const choices = conflictResolutionMap(target.plan, target.resolution);
    return target.plan.conflicts.every((conflict) => (
      !shared.has(conflict.stackId) || choices[conflict.stackId] === 'keep_existing'
    ));
  });
}

function stable(values: readonly string[] | undefined): string[] {
  return [...new Set(values ?? [])].sort((left, right) => left.localeCompare(right));
}

function reviewTopology(target: StackConflictReviewTarget): string {
  return JSON.stringify({
    destinationId: target.id,
    primaryAssetId: target.plan.primaryAssetId,
    selectedAssetIds: stable(target.plan.conflicts.flatMap((conflict) => conflict.selectedAssetIds ?? [])),
    conflicts: target.plan.conflicts
      .map((conflict) => ({
        stackId: conflict.stackId,
        primaryAssetId: conflict.primaryAssetId ?? null,
        memberAssetIds: stable(conflict.memberAssetIds),
        selectedAssetIds: stable(conflict.selectedAssetIds),
      }))
      .sort((left, right) => left.stackId.localeCompare(right.stackId)),
  });
}

function sameReviewTopology(
  reviewed: readonly StackConflictReviewTarget[],
  current: readonly StackConflictReviewTarget[],
): boolean {
  if (reviewed.length !== current.length) return false;
  const currentById = new Map(current.map((target) => [target.id, reviewTopology(target)]));
  return reviewed.every((target) => currentById.get(target.id) === reviewTopology(target));
}

async function reviewResolution(
  resolution: DuplicateResolutionPlan,
  assets: AssetRepository,
): Promise<{ resolution: DuplicateResolutionPlan; targets: StackConflictReviewTarget[] }> {
  const targets = await duplicateStackConflictReviews(resolution.stacks, assets);
  if (!targets.length) return { resolution, targets: [] };
  const result = await requestStackConflictReview(targets);
  const reviewedStacks = applyDuplicateStackReview(resolution.stacks, result);
  return {
    resolution: {
      decisions: { ...resolution.decisions },
      stacks: reviewedStacks,
    },
    targets: targets.map((target) => ({
      ...target,
      resolution: result[target.id] ?? target.resolution,
    })),
  };
}

export function withDuplicateStackConflictReview(
  duplicates: DuplicateRepository,
  assets: AssetRepository,
): DuplicateRepository {
  const prepare = duplicates.prepareDecisions.bind(duplicates);

  return new Proxy(duplicates, {
    get(target, property, receiver) {
      if (property !== 'prepareDecisions') return Reflect.get(target, property, receiver);
      return async (resolution: DuplicateResolutionPlan, groupIds: readonly string[]) => {
        let reviewedResolution = resolution;
        let reviewedTargets: StackConflictReviewTarget[] = [];

        // Explicit/current-group review already has every proposed destination locally, so
        // resolve environmental stack conflicts before creating its immutable action plan.
        if (groupIds.length) {
          const reviewed = await reviewResolution(reviewedResolution, assets);
          reviewedResolution = reviewed.resolution;
          reviewedTargets = reviewed.targets;
        }

        // Bulk workspace review may include selected groups that are not loaded in the page.
        // One bounded preview plan materializes those frozen destinations; it is never executed.
        let plan = await prepare(reviewedResolution, groupIds);
        if (!groupIds.length) {
          const reviewed = await reviewResolution(plan.resolution, assets);
          reviewedResolution = reviewed.resolution;
          reviewedTargets = reviewed.targets;
          if (reviewedResolution !== plan.resolution) plan = await prepare(reviewedResolution, groupIds);
        }

        // Compare the exact topology shown in the modal (members, selected members and primary),
        // not just source stack IDs. This closes the review-to-plan window where a source stack
        // could gain or lose members before the immutable backend fingerprint is created.
        for (let attempt = 0; attempt < 3; attempt += 1) {
          const currentTargets = await duplicateStackConflictReviews(plan.resolution.stacks, assets);
          if (
            sameReviewTopology(reviewedTargets, currentTargets)
            && reviewedTargetsAreSafe(currentTargets)
          ) return plan;

          if (!currentTargets.length) {
            // A reviewed conflict disappeared. Re-plan once against the now conflict-free
            // topology so the backend fingerprint reflects what will actually execute.
            reviewedTargets = [];
            reviewedResolution = plan.resolution;
            plan = await prepare(reviewedResolution, groupIds);
            continue;
          }

          const result = await requestStackConflictReview(currentTargets);
          reviewedResolution = {
            decisions: { ...plan.resolution.decisions },
            stacks: applyDuplicateStackReview(plan.resolution.stacks, result),
          };
          reviewedTargets = currentTargets.map((target) => ({
            ...target,
            resolution: result[target.id] ?? target.resolution,
          }));
          plan = await prepare(reviewedResolution, groupIds);
        }

        const finalTargets = await duplicateStackConflictReviews(plan.resolution.stacks, assets);
        if (
          !sameReviewTopology(reviewedTargets, finalTargets)
          || !reviewedTargetsAreSafe(finalTargets)
        ) {
          throw new Error('Existing stack membership kept changing during conflict review. Refresh duplicates and review the actions again.');
        }
        return plan;
      };
    },
  }) as DuplicateRepository;
}

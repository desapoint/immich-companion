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

async function reviewResolution(
  resolution: DuplicateResolutionPlan,
  assets: AssetRepository,
): Promise<DuplicateResolutionPlan> {
  const targets = await duplicateStackConflictReviews(resolution.stacks, assets);
  if (!targets.length) return resolution;
  const result = await requestStackConflictReview(targets);
  return {
    decisions: { ...resolution.decisions },
    stacks: applyDuplicateStackReview(resolution.stacks, result),
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

        // Explicit/current-group review already has every proposed destination locally, so
        // resolve environmental stack conflicts before creating its immutable action plan.
        if (groupIds.length) reviewedResolution = await reviewResolution(reviewedResolution, assets);

        // Bulk workspace review may include selected groups that are not loaded in the page.
        // One bounded preview plan materializes those frozen destinations; it is never executed.
        let plan = await prepare(reviewedResolution, groupIds);
        if (!groupIds.length) {
          reviewedResolution = await reviewResolution(plan.resolution, assets);
          if (reviewedResolution !== plan.resolution) plan = await prepare(reviewedResolution, groupIds);
        }

        // Re-read live stack summaries after the final backend plan. If topology changed while
        // the modal was open, re-review rather than silently applying choices to a new stack.
        for (let attempt = 0; attempt < 2; attempt += 1) {
          const currentTargets = await duplicateStackConflictReviews(plan.resolution.stacks, assets);
          if (!currentTargets.length || reviewedTargetsAreSafe(currentTargets)) return plan;
          const result = await requestStackConflictReview(currentTargets);
          reviewedResolution = {
            decisions: { ...plan.resolution.decisions },
            stacks: applyDuplicateStackReview(plan.resolution.stacks, result),
          };
          plan = await prepare(reviewedResolution, groupIds);
        }

        const finalTargets = await duplicateStackConflictReviews(plan.resolution.stacks, assets);
        if (finalTargets.length && !reviewedTargetsAreSafe(finalTargets)) {
          throw new Error('Existing stack membership kept changing during conflict review. Refresh duplicates and review the actions again.');
        }
        return plan;
      };
    },
  }) as DuplicateRepository;
}

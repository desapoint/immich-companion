import type { StackResolutionMap } from './contracts';
import type { StackConflictReviewTarget } from './stackResolution';

export type StackConflictReviewResult = Record<string, StackResolutionMap>;
export type StackConflictReviewer = (targets: StackConflictReviewTarget[]) => Promise<StackConflictReviewResult>;

let reviewer: StackConflictReviewer | null = null;

export class StackConflictReviewCancelled extends Error {
  constructor() {
    super('Stack conflict review was cancelled.');
    this.name = 'StackConflictReviewCancelled';
  }
}

export function registerStackConflictReviewer(next: StackConflictReviewer): () => void {
  reviewer = next;
  return () => {
    if (reviewer === next) reviewer = null;
  };
}

export function requestStackConflictReview(targets: StackConflictReviewTarget[]): Promise<StackConflictReviewResult> {
  if (!targets.length) return Promise.resolve({});
  if (!reviewer) throw new Error('Stack conflict review is unavailable in the current V2 surface.');
  return reviewer(targets.map((target) => ({ ...target, plan: { ...target.plan, conflicts: target.plan.conflicts.map((conflict) => ({ ...conflict })) } })));
}

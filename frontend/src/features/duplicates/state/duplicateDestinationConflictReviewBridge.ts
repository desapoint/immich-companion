import type {
  DuplicateDestinationConflictResult,
  DuplicateDestinationConflictTarget,
} from './duplicateDestinationConflictReview';

export type DuplicateDestinationConflictReviewer = (
  targets: DuplicateDestinationConflictTarget[],
) => Promise<DuplicateDestinationConflictResult>;

let reviewer: DuplicateDestinationConflictReviewer | null = null;

export class DuplicateDestinationConflictReviewCancelled extends Error {
  constructor() {
    super('Proposed stack destination review was cancelled.');
    this.name = 'DuplicateDestinationConflictReviewCancelled';
  }
}

export function registerDuplicateDestinationConflictReviewer(
  next: DuplicateDestinationConflictReviewer,
): () => void {
  reviewer = next;
  return () => {
    if (reviewer === next) reviewer = null;
  };
}

export function requestDuplicateDestinationConflictReview(
  targets: DuplicateDestinationConflictTarget[],
): Promise<DuplicateDestinationConflictResult> {
  if (!targets.length) return Promise.resolve({});
  if (!reviewer) throw new Error('Proposed stack destination review is unavailable in the current V2 surface.');
  return reviewer(targets.map((target) => ({
    ...target,
    stackIds: [...target.stackIds],
    sharedAssetIds: [...target.sharedAssetIds],
    options: target.options.map((stack) => ({
      ...stack,
      assetIds: [...stack.assetIds],
      sourceGroupIds: stack.sourceGroupIds ? [...stack.sourceGroupIds] : undefined,
    })),
  })));
}

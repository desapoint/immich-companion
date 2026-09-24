import type { DuplicateDecision, DuplicatePendingStack } from '../types/contracts';
import type { DuplicateStackWorkspace } from './duplicateStackResolution';

export type DuplicateReviewIssueKind = 'incomplete_stack' | 'primary_disposition' | 'member_disposition';

export type DuplicateReviewIssue = {
  kind: DuplicateReviewIssueKind;
  groupId: string;
  stackId: string;
  stackLabel: string;
  assetId: string;
  message: string;
};

function issueForStack(
  stack: DuplicatePendingStack,
  decisions: Readonly<Record<string, DuplicateDecision>>,
): DuplicateReviewIssue | null {
  if (stack.assetIds.length === 0) return null;

  if (stack.assetIds.length === 1) {
    return {
      kind: 'incomplete_stack',
      groupId: stack.groupId,
      stackId: stack.id,
      stackLabel: stack.label,
      assetId: stack.assetIds[0],
      message: `${stack.label} has only one image. Add another image to the stack or keep the remaining image instead.`,
    };
  }

  if (!stack.primaryAssetId || !stack.assetIds.includes(stack.primaryAssetId)) {
    return {
      kind: 'primary_disposition',
      groupId: stack.groupId,
      stackId: stack.id,
      stackLabel: stack.label,
      assetId: stack.assetIds[0] ?? '',
      message: `${stack.label} needs a primary image before this review can continue.`,
    };
  }

  if (decisions[stack.primaryAssetId] !== 'stack') {
    return {
      kind: 'primary_disposition',
      groupId: stack.groupId,
      stackId: stack.id,
      stackLabel: stack.label,
      assetId: stack.primaryAssetId,
      message: `${stack.label}'s primary image must use the Stack action before this review can continue.`,
    };
  }

  const invalidMember = stack.assetIds.find((assetId) => decisions[assetId] !== 'stack');
  if (invalidMember) {
    return {
      kind: 'member_disposition',
      groupId: stack.groupId,
      stackId: stack.id,
      stackLabel: stack.label,
      assetId: invalidMember,
      message: `${stack.label} contains an image that no longer uses the Stack action.`,
    };
  }

  return null;
}

export function duplicateReviewIssues(
  workspace: DuplicateStackWorkspace,
  decisions: Readonly<Record<string, DuplicateDecision>>,
): DuplicateReviewIssue[] {
  return Object.values(workspace.stacks)
    .sort((left, right) => left.label.localeCompare(right.label, undefined, { numeric: true }))
    .map((stack) => issueForStack(stack, decisions))
    .filter((issue): issue is DuplicateReviewIssue => issue !== null);
}

export function duplicateGroupAnchorId(groupId: string): string {
  return `duplicate-group-${groupId}`;
}

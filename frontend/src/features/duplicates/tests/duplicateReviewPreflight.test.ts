import { describe, expect, it } from 'vitest';

import { primaryFor } from '../api/duplicateMapping';
import { duplicateReviewIssues } from '../state/duplicateReviewPreflight';
import {
  assignAssetToActiveStack,
  createDuplicateStackWorkspace,
  createPendingStack,
  removeAssetFromPendingStack,
} from '../state/duplicateStackResolution';
import type { DuplicateStackWorkspace } from '../state/duplicateStackResolution';
import type { DuplicateResolutionPlan } from '../types/contracts';

describe('duplicate review stack preflight', () => {
  it('does not block on an empty pending stack', () => {
    const workspace = createPendingStack(createDuplicateStackWorkspace(), 'group-1');
    expect(duplicateReviewIssues(workspace, {})).toEqual([]);
  });

  it('uses the first explicitly stacked asset as the primary instead of an undecided member', () => {
    const resolution: DuplicateResolutionPlan = { decisions: { stacked: 'stack' }, stacks: [] };

    expect(primaryFor(resolution, ['undecided', 'stacked'])).toBe('stacked');
  });

  it('does not trust a saved primary whose disposition is no longer Stack', () => {
    const resolution: DuplicateResolutionPlan = {
      decisions: { oldPrimary: 'keep', stacked: 'stack' },
      stacks: [{
        id: 'stack-1',
        groupId: 'group-1',
        label: 'Stack 1',
        assetIds: ['oldPrimary', 'stacked'],
        primaryAssetId: 'oldPrimary',
      }],
    };

    expect(primaryFor(resolution, ['oldPrimary', 'stacked'])).toBe('stacked');
  });

  it('reports the first Stack choice immediately as a singleton issue', () => {
    const workspace = assignAssetToActiveStack(createDuplicateStackWorkspace(), 'group-1', 'asset-1');

    expect(duplicateReviewIssues(workspace, { 'asset-1': 'stack' })).toMatchObject([{
      kind: 'incomplete_stack',
      groupId: 'group-1',
      assetId: 'asset-1',
    }]);
  });

  it('reports a singleton after removing one member from a two-image stack', () => {
    let workspace = assignAssetToActiveStack(createDuplicateStackWorkspace(), 'group-1', 'asset-1');
    workspace = assignAssetToActiveStack(workspace, 'group-1', 'asset-2');
    workspace = removeAssetFromPendingStack(workspace, 'asset-1');

    expect(duplicateReviewIssues(workspace, { 'asset-1': 'keep', 'asset-2': 'stack' })).toMatchObject([{
      kind: 'incomplete_stack',
      assetId: 'asset-2',
    }]);
  });

  it('rejects missing and non-Stack primaries before review', () => {
    const baseStack = {
      id: 'stack-1',
      groupId: 'group-1',
      label: 'Stack 1',
      assetIds: ['asset-1', 'asset-2'],
      primaryAssetId: null,
    };
    const workspace: DuplicateStackWorkspace = {
      activeByGroup: { 'group-1': 'stack-1' },
      nextOrdinalByGroup: { 'group-1': 2 },
      assetToStack: { 'asset-1': 'stack-1', 'asset-2': 'stack-1' },
      stacks: { 'stack-1': baseStack },
    };

    expect(duplicateReviewIssues(workspace, { 'asset-1': 'stack', 'asset-2': 'stack' })[0]?.kind).toBe('primary_disposition');
    workspace.stacks['stack-1'].primaryAssetId = 'asset-1';
    expect(duplicateReviewIssues(workspace, { 'asset-1': 'keep', 'asset-2': 'stack' })[0]?.kind).toBe('primary_disposition');
  });

  it('accepts a complete stack whose primary and members all use Stack', () => {
    let workspace = assignAssetToActiveStack(createDuplicateStackWorkspace(), 'group-1', 'asset-1');
    workspace = assignAssetToActiveStack(workspace, 'group-1', 'asset-2');

    expect(duplicateReviewIssues(workspace, { 'asset-1': 'stack', 'asset-2': 'stack' })).toEqual([]);
  });
});

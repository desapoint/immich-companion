import { describe, expect, it } from 'vitest';
import type { DuplicateResolutionPlan } from '../types/contracts';
import {
  applyDuplicateDestinationReview,
  duplicateDestinationConflicts,
} from '../state/duplicateDestinationConflictReview';

function overlappingResolution(): DuplicateResolutionPlan {
  return {
    decisions: { a: 'stack', b: 'stack', c: 'stack', d: 'stack' },
    stacks: [
      { id: 's1', groupId: 'g1', label: 'Stack 1', assetIds: ['a', 'b'], primaryAssetId: 'a' },
      { id: 's2', groupId: 'g2', label: 'Stack 1', assetIds: ['b', 'c'], primaryAssetId: 'b' },
      { id: 's3', groupId: 'g3', label: 'Stack 1', assetIds: ['d', 'c'], primaryAssetId: 'd' },
    ],
  };
}

describe('duplicate proposed destination review', () => {
  it('builds one transitive conflict for connected proposed stacks', () => {
    const conflicts = duplicateDestinationConflicts(overlappingResolution().stacks);

    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].stackIds).toEqual(['s1', 's2', 's3']);
    expect(conflicts[0].sharedAssetIds).toEqual(['b', 'c']);
  });

  it('merges the connected groups and keeps the preferred destination primary', () => {
    const resolution = overlappingResolution();
    const conflicts = duplicateDestinationConflicts(resolution.stacks);

    const merged = applyDuplicateDestinationReview(
      resolution,
      conflicts,
      { [conflicts[0].id]: 's2' },
    );

    expect(merged.stacks).toHaveLength(1);
    expect(merged.stacks[0]).toMatchObject({
      id: 's2',
      groupId: 'g2',
      primaryAssetId: 'b',
      assetIds: ['b', 'c', 'a', 'd'],
      sourceGroupIds: ['g1', 'g2', 'g3'],
    });
  });

  it('leaves disjoint proposed stacks untouched', () => {
    const resolution: DuplicateResolutionPlan = {
      decisions: { a: 'stack', b: 'stack', c: 'stack', d: 'stack' },
      stacks: [
        { id: 's1', groupId: 'g1', label: 'Stack 1', assetIds: ['a', 'b'], primaryAssetId: 'a' },
        { id: 's2', groupId: 'g2', label: 'Stack 1', assetIds: ['c', 'd'], primaryAssetId: 'c' },
      ],
    };

    expect(duplicateDestinationConflicts(resolution.stacks)).toEqual([]);
  });
});

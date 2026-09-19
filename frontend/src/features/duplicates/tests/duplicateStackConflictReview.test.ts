import { describe, expect, it } from 'vitest';
import type { AssetRecord, AssetRepository, DuplicatePendingStack } from '../types/contracts';
import { applyDuplicateStackReview, duplicateStackConflictReviews } from '../state/duplicateStackConflictReview';

function asset(id: string, stack: AssetRecord['stack'] = null): AssetRecord {
  return {
    id,
    original_file_name: `${id}.jpg`,
    stack,
  } as AssetRecord;
}

function repository(records: AssetRecord[]): AssetRepository {
  const byId = new Map(records.map((record) => [record.id, record]));
  return {
    async getMany(ids) {
      return ids.flatMap((id) => byId.get(id) ?? []);
    },
  } as AssetRepository;
}

const destination: DuplicatePendingStack = {
  id: 'pending-1',
  groupId: 'group-1',
  label: 'Stack 1',
  assetIds: ['a', 'b'],
  primaryAssetId: 'a',
};

describe('duplicate stack conflict review', () => {
  it('builds one visual conflict from the live source-stack topology', async () => {
    const source = { id: 'stack-old', primaryAssetId: 'a', assetCount: 3, assets: ['a', 'c', 'd'] };
    const reviews = await duplicateStackConflictReviews(
      [destination],
      repository([asset('a', source), asset('b')]),
    );

    expect(reviews).toHaveLength(1);
    expect(reviews[0].plan.primaryAssetId).toBe('a');
    expect(reviews[0].plan.conflicts).toEqual([{
      stackId: 'stack-old',
      primaryAssetId: 'a',
      memberAssetIds: ['a', 'c', 'd'],
      selectedAssetIds: ['a'],
      selectedCount: 1,
      memberCount: 3,
      includesUnselected: true,
    }]);
  });

  it('fails closed when a source stack summary is incomplete', async () => {
    const source = { id: 'stack-old', primaryAssetId: 'a', assetCount: 3, assets: ['a', 'c'] };
    await expect(duplicateStackConflictReviews(
      [destination],
      repository([asset('a', source), asset('b')]),
    )).rejects.toThrow('could not be loaded completely');
  });

  it('applies reviewed per-source-stack choices to the destination only', () => {
    const stacks = applyDuplicateStackReview([destination], {
      'pending-1': { 'stack-old': 'include_existing' },
    });
    expect(stacks[0].stackResolution).toEqual({ 'stack-old': 'include_existing' });
    expect(destination.stackResolution).toBeUndefined();
  });
});

import { afterEach, describe, expect, it } from 'vitest';
import type { AssetRecord, AssetRepository, DuplicatePreparedPlan, DuplicateRepository, DuplicateResolutionPlan } from './contracts';
import { withDuplicateStackConflictReview } from './duplicateStackConflictReviewRepository';
import { registerStackConflictReviewer } from './stackConflictReviewBridge';

let unregister: (() => void) | null = null;
afterEach(() => {
  unregister?.();
  unregister = null;
});

function asset(id: string, stack: AssetRecord['stack'] = null): AssetRecord {
  return { id, original_file_name: `${id}.jpg`, stack } as AssetRecord;
}

function assets(): AssetRepository {
  const source = { id: '11111111-1111-4111-8111-111111111111', primaryAssetId: 'a', assetCount: 3, assets: ['a', 'c', 'd'] };
  const records = new Map([['a', asset('a', source)], ['b', asset('b')]]);
  return {
    async getMany(ids) { return ids.flatMap((id) => records.get(id) ?? []); },
  } as AssetRepository;
}

function resolution(): DuplicateResolutionPlan {
  return {
    decisions: { a: 'stack', b: 'stack' },
    stacks: [{ id: 'pending-1', groupId: 'group-1', label: 'Stack 1', assetIds: ['a', 'b'], primaryAssetId: 'a' }],
  };
}

function prepared(value: DuplicateResolutionPlan, groupIds: readonly string[]): DuplicatePreparedPlan {
  return { id: `plan-${groupIds.length || 'bulk'}`, resolution: value, groupIds: groupIds.length ? [...groupIds] : ['group-1'] };
}

describe('duplicate stack conflict review repository', () => {
  it('reviews an explicit group before its immutable plan is created', async () => {
    const calls: DuplicateResolutionPlan[] = [];
    const repository = {
      async prepareDecisions(value: DuplicateResolutionPlan, groupIds: readonly string[]) {
        calls.push(value);
        return prepared(value, groupIds);
      },
    } as unknown as DuplicateRepository;
    unregister = registerStackConflictReviewer(async (targets) => ({
      [targets[0].id]: { '11111111-1111-4111-8111-111111111111': 'move_selected' },
    }));

    const plan = await withDuplicateStackConflictReview(repository, assets()).prepareDecisions(resolution(), ['group-1']);

    expect(calls).toHaveLength(1);
    expect(calls[0].stacks[0].stackResolution).toEqual({ '11111111-1111-4111-8111-111111111111': 'move_selected' });
    expect(plan.resolution.stacks[0].stackResolution).toEqual(calls[0].stacks[0].stackResolution);
  });

  it('materializes workspace-selected destinations before reviewing off-page conflicts', async () => {
    const calls: DuplicateResolutionPlan[] = [];
    const frozen = resolution();
    const repository = {
      async prepareDecisions(value: DuplicateResolutionPlan, groupIds: readonly string[]) {
        calls.push(value);
        return prepared(calls.length === 1 ? frozen : value, groupIds);
      },
    } as unknown as DuplicateRepository;
    unregister = registerStackConflictReviewer(async (targets) => ({
      [targets[0].id]: { '11111111-1111-4111-8111-111111111111': 'include_existing' },
    }));

    const plan = await withDuplicateStackConflictReview(repository, assets()).prepareDecisions({ decisions: {}, stacks: [] }, []);

    expect(calls).toHaveLength(2);
    expect(calls[1].stacks[0].stackResolution).toEqual({ '11111111-1111-4111-8111-111111111111': 'include_existing' });
    expect(plan.resolution.stacks[0].stackResolution).toEqual(calls[1].stacks[0].stackResolution);
  });
});

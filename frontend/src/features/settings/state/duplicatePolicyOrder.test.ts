import { describe, expect, it } from 'vitest';

import type { DuplicatePolicy, ImmichLibraryOption } from '../types/settings';
import { orderedSourcePriority, sourcePriorityItems } from './duplicatePolicyOrder';

const id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const missingId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const policy = {
  automatic_handling_enabled: true,
  preselect_safe_groups: true,
  exact_file_action: 'resolve',
  keeper_policy: 'prefer_upload',
  source_priority: [id, missingId, 'immich_uploads', 'unlisted'],
  keeper_tiebreakers: [],
  analyze_automatically: true,
  verify_upload_streams: false,
  external_library_ids: [],
  similarity_threshold_percent: 95,
} satisfies DuplicatePolicy;

function library(name: string): ImmichLibraryOption {
  return { id, name, type: 'EXTERNAL', assetCount: 12 };
}

describe('duplicate policy ordering', () => {
  it('keeps rank by stable UUID when a library is renamed', () => {
    const before = sourcePriorityItems(policy.source_priority, [library('Old name')]);
    const after = sourcePriorityItems(policy.source_priority, [library('New name')]);

    expect(after.map((item) => item.id)).toEqual(before.map((item) => item.id));
    expect(after[0]?.label).toBe('New name');
  });

  it('reports saved UUIDs that are no longer returned by Immich', () => {
    const items = sourcePriorityItems(policy.source_priority, [library('Current')]);

    expect(items.find((item) => item.id === missingId)?.unavailable).toBe(true);
    expect(items.find((item) => item.id === missingId)?.description).toContain(missingId);
  });

  it('adds newly discovered libraries immediately before the unlisted fallback', () => {
    const newLibrary = { ...library('New'), id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc' };
    const ordered = orderedSourcePriority(policy, [library('Current'), newLibrary]);

    expect(ordered).toEqual([id, missingId, 'immich_uploads', newLibrary.id, 'unlisted']);
  });
});

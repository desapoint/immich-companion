import { describe, expect, it } from 'vitest';

import type { DuplicateReviewProjection } from './duplicateReviewFilters';
import { paginateDuplicateReviewEntries } from './duplicateReviewPagination';

const entries = Array.from({ length: 29 }, (_, index) => ({
  group: { group_id: `group-${index + 1}` },
})) as DuplicateReviewProjection[];

describe('duplicate review pagination', () => {
  it('limits rendered groups and keeps a stable last page', () => {
    const first = paginateDuplicateReviewEntries(entries, 1, 12);
    const last = paginateDuplicateReviewEntries(entries, 99, 12);

    expect(first.entries).toHaveLength(12);
    expect(first.entries[0].group.group_id).toBe('group-1');
    expect(last.page).toBe(3);
    expect(last.entries.map((entry) => entry.group.group_id)).toEqual([
      'group-25', 'group-26', 'group-27', 'group-28', 'group-29',
    ]);
  });

  it('clamps after a filter reduces the available groups', () => {
    const filtered = paginateDuplicateReviewEntries(entries.slice(0, 3), 3, 12);
    expect(filtered.page).toBe(1);
    expect(filtered.pages).toBe(1);
    expect(filtered.entries).toHaveLength(3);
  });
});

import { describe, expect, it } from 'vitest';

import { duplicateViewerGroupNavigationPlan } from '../state/duplicateViewerGroupNavigation';

describe('duplicate viewer group navigation', () => {
  it('moves between groups already loaded on the current page', () => {
    const state = {
      resultMode: 'Pagination' as const,
      page: 2,
      pageSize: 6,
      total: 20,
      loadedCount: 6,
      currentIndex: 3,
      hasNextCursor: false,
    };

    expect(duplicateViewerGroupNavigationPlan('previous', state)).toEqual({ kind: 'loaded', index: 2 });
    expect(duplicateViewerGroupNavigationPlan('next', state)).toEqual({ kind: 'loaded', index: 4 });
  });

  it('loads the adjacent pagination page at a page boundary', () => {
    expect(duplicateViewerGroupNavigationPlan('previous', {
      resultMode: 'Pagination',
      page: 3,
      pageSize: 6,
      total: 20,
      loadedCount: 6,
      currentIndex: 0,
      hasNextCursor: false,
    })).toEqual({ kind: 'page', page: 2, edge: 'last' });

    expect(duplicateViewerGroupNavigationPlan('next', {
      resultMode: 'Pagination',
      page: 2,
      pageSize: 6,
      total: 20,
      loadedCount: 6,
      currentIndex: 5,
      hasNextCursor: false,
    })).toEqual({ kind: 'page', page: 3, edge: 'first' });
  });

  it('appends the next infinite batch only when the current loaded tail has a cursor', () => {
    const base = {
      resultMode: 'Infinite' as const,
      page: 1,
      pageSize: 6,
      total: 20,
      loadedCount: 12,
      currentIndex: 11,
    };

    expect(duplicateViewerGroupNavigationPlan('next', { ...base, hasNextCursor: true }))
      .toEqual({ kind: 'append', index: 12 });
    expect(duplicateViewerGroupNavigationPlan('next', { ...base, hasNextCursor: false })).toBeNull();
    expect(duplicateViewerGroupNavigationPlan('previous', { ...base, currentIndex: 0, hasNextCursor: true })).toBeNull();
  });

  it('stops at the first and last matching group', () => {
    expect(duplicateViewerGroupNavigationPlan('previous', {
      resultMode: 'Pagination',
      page: 1,
      pageSize: 6,
      total: 4,
      loadedCount: 4,
      currentIndex: 0,
      hasNextCursor: false,
    })).toBeNull();

    expect(duplicateViewerGroupNavigationPlan('next', {
      resultMode: 'Pagination',
      page: 1,
      pageSize: 6,
      total: 4,
      loadedCount: 4,
      currentIndex: 3,
      hasNextCursor: false,
    })).toBeNull();
  });
});

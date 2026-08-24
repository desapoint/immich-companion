import { describe, expect, it } from 'vitest';

import { buildPaginationItems, type PaginationItem } from './pagination';

function values(items: PaginationItem[]): Array<number | 'ellipsis'> {
  return items.map((item) => (item.kind === 'page' ? item.page : 'ellipsis'));
}

describe('buildPaginationItems', () => {
  it('shows boundary pages, siblings, and both ellipses around a middle page', () => {
    expect(values(buildPaginationItems({ currentPage: 10, totalPages: 20 }))).toEqual([
      1,
      'ellipsis',
      8,
      9,
      10,
      11,
      12,
      'ellipsis',
      20,
    ]);
  });

  it('shifts the configured window at the beginning and end', () => {
    expect(values(buildPaginationItems({ currentPage: 1, totalPages: 20 }))).toEqual([
      1,
      2,
      3,
      4,
      5,
      'ellipsis',
      20,
    ]);
    expect(values(buildPaginationItems({ currentPage: 20, totalPages: 20 }))).toEqual([
      1,
      'ellipsis',
      16,
      17,
      18,
      19,
      20,
    ]);
  });

  it('supports custom sibling and boundary counts without duplicate pages', () => {
    expect(values(buildPaginationItems({
      currentPage: 8,
      totalPages: 15,
      siblingCount: 1,
      boundaryCount: 2,
    }))).toEqual([1, 2, 'ellipsis', 7, 8, 9, 'ellipsis', 14, 15]);
  });

  it('fills a one-page gap instead of rendering a misleading ellipsis', () => {
    expect(values(buildPaginationItems({
      currentPage: 4,
      totalPages: 7,
      siblingCount: 1,
    }))).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it('handles empty and out-of-range input safely', () => {
    expect(buildPaginationItems({ currentPage: 1, totalPages: 0 })).toEqual([]);
    expect(values(buildPaginationItems({ currentPage: 99, totalPages: 3 }))).toEqual([1, 2, 3]);
  });
});

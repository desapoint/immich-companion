import { describe, expect, it, vi } from 'vitest';

import {
  buildPaginationItems,
  paginationItemRange,
  scrollToPaginationStart,
  type PaginationItem,
} from './pagination';

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

describe('pagination details', () => {
  it('reports the visible item range and clamps out-of-range pages', () => {
    expect(paginationItemRange(1, 25, 83)).toEqual({ start: 1, end: 25 });
    expect(paginationItemRange(4, 25, 83)).toEqual({ start: 76, end: 83 });
    expect(paginationItemRange(99, 25, 83)).toEqual({ start: 76, end: 83 });
    expect(paginationItemRange(1, 25, 0)).toEqual({ start: 0, end: 0 });
  });

  it('scrolls the collection start with the standard behavior', () => {
    const scrollIntoView = vi.fn();
    scrollToPaginationStart({ scrollIntoView } as unknown as Element);
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
  });
});

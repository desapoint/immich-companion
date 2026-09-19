import { describe, expect, it } from 'vitest';
import { paginationItems, validPageNumber } from './pagination';

describe('V2 pagination window', () => {
  it('shows three pages on each side of a middle page', () => {
    expect(paginationItems(10, 20)).toEqual([
      { kind: 'page', page: 1 },
      { kind: 'gap', from: 2, to: 6 },
      { kind: 'page', page: 7 },
      { kind: 'page', page: 8 },
      { kind: 'page', page: 9 },
      { kind: 'page', page: 10 },
      { kind: 'page', page: 11 },
      { kind: 'page', page: 12 },
      { kind: 'page', page: 13 },
      { kind: 'gap', from: 14, to: 19 },
      { kind: 'page', page: 20 },
    ]);
  });

  it('shows a single omitted page instead of an ellipsis', () => {
    expect(paginationItems(5, 10)).toEqual(
      Array.from({ length: 10 }, (_, index) => ({ kind: 'page', page: index + 1 })),
    );
  });

  it('keeps a single trailing gap near the beginning', () => {
    expect(paginationItems(1, 12)).toEqual([
      { kind: 'page', page: 1 },
      { kind: 'page', page: 2 },
      { kind: 'page', page: 3 },
      { kind: 'page', page: 4 },
      { kind: 'gap', from: 5, to: 11 },
      { kind: 'page', page: 12 },
    ]);
  });

  it('clamps invalid page and radius inputs', () => {
    expect(paginationItems(99, 4, -2)).toEqual([
      { kind: 'page', page: 1 },
      { kind: 'gap', from: 2, to: 3 },
      { kind: 'page', page: 4 },
    ]);
  });

  it('accepts only whole in-range page numbers for direct navigation', () => {
    expect(validPageNumber(' 12 ', 20)).toBe(12);
    expect(validPageNumber('', 20)).toBeNull();
    expect(validPageNumber('1.5', 20)).toBeNull();
    expect(validPageNumber('0', 20)).toBeNull();
    expect(validPageNumber('21', 20)).toBeNull();
  });
});

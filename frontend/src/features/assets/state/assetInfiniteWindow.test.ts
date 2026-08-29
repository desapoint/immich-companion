import { describe, expect, it } from 'vitest';

import {
  decodeAssetListMode,
  firstSurvivingScrollAnchor,
  infiniteWindowPages,
  mergeInfiniteWindowItems,
} from './assetInfiniteWindow';

describe('infinite asset window restoration', () => {
  it('accepts only the persisted infinite mode', () => {
    expect(decodeAssetListMode('infinite')).toBe('infinite');
    expect(decodeAssetListMode('paged')).toBe('paged');
    expect(decodeAssetListMode('unexpected')).toBe('paged');
    expect(decodeAssetListMode(null)).toBe('paged');
  });

  it('rebuilds every page from the beginning through the prior loaded window', () => {
    expect(infiniteWindowPages(4, 9)).toEqual([1, 2, 3, 4]);
    expect(infiniteWindowPages(4, 2)).toEqual([1, 2]);
    expect(infiniteWindowPages(0, 0)).toEqual([1]);
  });

  it('keeps page order while removing duplicates from changing page boundaries', () => {
    expect(mergeInfiniteWindowItems([
      [{ id: 'a' }, { id: 'b' }],
      [{ id: 'b' }, { id: 'c' }],
    ])).toEqual([{ id: 'a' }, { id: 'b' }, { id: 'c' }]);
  });

  it('falls forward when the first viewport asset disappeared', () => {
    const anchors = [
      { id: 'removed', top: 120 },
      { id: 'survivor', top: 360 },
      { id: 'later', top: 600 },
    ];

    expect(firstSurvivingScrollAnchor(anchors, new Set(['survivor', 'later']))).toEqual(
      anchors[1],
    );
    expect(firstSurvivingScrollAnchor(anchors, new Set())).toBeNull();
  });
});

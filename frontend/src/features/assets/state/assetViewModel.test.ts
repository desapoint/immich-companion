import { describe, expect, it } from 'vitest';

import {
  copySearchGroup,
  createSimpleAssetSearchFilters,
  createSearchCondition,
  createSearchGroup,
  formatAssetBytes,
  nextViewerIndex,
  serializeSearchGroup,
  simpleFiltersToSearchGroup,
  toggleSelectedAsset,
} from './assetViewModel';

describe('asset view model', () => {
  it('keeps viewer navigation inside result boundaries', () => {
    expect(nextViewerIndex(0, 'previous', 3)).toBe(0);
    expect(nextViewerIndex(0, 'next', 3)).toBe(1);
    expect(nextViewerIndex(2, 'next', 3)).toBe(2);
  });

  it('toggles selection without mutating the previous set', () => {
    const current = new Set(['first']);
    const added = toggleSelectedAsset(current, 'second');
    const removed = toggleSelectedAsset(added, 'first');

    expect(current).toEqual(new Set(['first']));
    expect(added).toEqual(new Set(['first', 'second']));
    expect(removed).toEqual(new Set(['second']));
  });

  it('formats compact file sizes', () => {
    expect(formatAssetBytes(null)).toBeNull();
    expect(formatAssetBytes(512)).toBe('512 B');
    expect(formatAssetBytes(1536)).toBe('1.5 KB');
    expect(formatAssetBytes(5 * 1024 ** 2)).toBe('5.0 MB');
  });

  it('copies nested search state without sharing child references', () => {
    const root = createSearchGroup();
    const nested = createSearchGroup('or');
    nested.children.push(createSearchCondition('album'));
    root.children.push(nested);

    const copied = copySearchGroup(root);
    expect(copied).toEqual(root);
    (copied.children[0] as typeof nested).negate = true;
    expect(nested.negate).toBe(false);
  });

  it('converts only active simple filters into an AND search group', () => {
    const filters = createSimpleAssetSearchFilters();
    filters.query = '  family trip  ';
    filters.assetType = 'IMAGE';
    filters.favorite = 'true';
    filters.trashed = 'false';

    const group = simpleFiltersToSearchGroup(filters);

    expect(group.operator).toBe('and');
    expect(group.children).toMatchObject([
      { field: 'filename', operator: 'contains', value: 'family trip' },
      { field: 'type', operator: 'equals', value: 'IMAGE' },
      { field: 'favorite', operator: 'equals', value: 'true' },
      { field: 'trashed', operator: 'equals', value: 'false' },
    ]);
  });

  it('restores typed date, dimension, and aspect-ratio ranges in simple search', () => {
    const filters = createSimpleAssetSearchFilters();
    filters.takenAfter = '2026-01-01T08:30';
    filters.takenBefore = '2026-06-30T17:45';
    filters.minWidth = '1280';
    filters.maxWidth = '4096';
    filters.minHeight = '720';
    filters.maxHeight = '2160';
    filters.minAspectRatio = '1.33';
    filters.maxAspectRatio = '1.78';

    expect(serializeSearchGroup(simpleFiltersToSearchGroup(filters))).toMatchObject({
      operator: 'and',
      children: [
        {
          field: 'taken_at',
          operator: 'after',
          value: new Date(filters.takenAfter).toISOString(),
        },
        {
          field: 'taken_at',
          operator: 'before',
          value: new Date(filters.takenBefore).toISOString(),
        },
        { field: 'width', operator: 'at_least', value: 1280 },
        { field: 'width', operator: 'at_most', value: 4096 },
        { field: 'height', operator: 'at_least', value: 720 },
        { field: 'height', operator: 'at_most', value: 2160 },
        { field: 'aspect_ratio', operator: 'at_least', value: 1.33 },
        { field: 'aspect_ratio', operator: 'at_most', value: 1.78 },
      ],
    });
  });
});

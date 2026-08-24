import { describe, expect, it } from 'vitest';

import {
  copySearchGroup,
  comparisonPreviewState,
  createSimpleAssetSearchFilters,
  createSearchCondition,
  createSearchGroup,
  formatAssetBytes,
  nextViewerIndex,
  restoreComparisonState,
  serializeSearchGroup,
  simpleFiltersToSearchGroup,
  stackMembersForAsset,
  toggleSelectedAsset,
} from './assetViewModel';
import type { AssetSummary } from '../types/assets';

describe('asset view model', () => {
  it('excludes trashed assets from the default simple search', () => {
    const filters = createSimpleAssetSearchFilters();

    expect(filters.trashed).toBe('false');
    expect(serializeSearchGroup(simpleFiltersToSearchGroup(filters))).toMatchObject({
      children: [{ field: 'trashed', operator: 'equals', value: false }],
    });
  });

  it('keeps viewer navigation inside result boundaries', () => {
    expect(nextViewerIndex(0, 'previous', 3)).toBe(0);
    expect(nextViewerIndex(0, 'next', 3)).toBe(1);
    expect(nextViewerIndex(2, 'next', 3)).toBe(2);
  });

  it('keeps stack selection independent while similar navigation links both states', () => {
    expect(comparisonPreviewState('stack', 'selected', 'preview')).toEqual({
      selectedId: 'selected',
      visibleId: 'preview',
    });
    expect(comparisonPreviewState('similar', 'selected', 'similar')).toEqual({
      selectedId: 'similar',
      visibleId: 'similar',
    });
    expect(restoreComparisonState('selected')).toEqual({
      selectedId: 'selected',
      visibleId: 'selected',
    });
  });

  it('keeps the selected asset available when stack metadata omits it', () => {
    const asset = {
      id: 'selected',
      type: 'IMAGE',
      original_file_name: 'selected.png',
      original_mime_type: 'image/png',
      width: 1920,
      height: 1080,
      taken_at: '2026-08-24T12:00:00Z',
      stack: {
        id: 'stack',
        primary_asset_id: 'other',
        asset_count: 2,
        assets: [{
          id: 'other',
          type: 'IMAGE',
          original_file_name: 'other.png',
          original_mime_type: 'image/png',
          width: 1280,
          height: 720,
          taken_at: '2026-08-24T12:01:00Z',
        }],
      },
    } as AssetSummary;

    expect(stackMembersForAsset(asset).map((member) => member.id)).toEqual([
      'other',
      'selected',
    ]);
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
    filters.trashed = 'any';
    filters.takenAfter = '2026-01-01T08:30';
    filters.takenBefore = '2026-06-30T17:45';
    filters.minWidth = '1280';
    filters.maxWidth = '4096';
    filters.minHeight = '720';
    filters.maxHeight = '2160';
    filters.minAspectRatio = '4/3';
    filters.maxAspectRatio = '16/9';

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
        { field: 'aspect_ratio', operator: 'at_least', value: 4 / 3 },
        { field: 'aspect_ratio', operator: 'at_most', value: 16 / 9 },
      ],
    });
  });
});

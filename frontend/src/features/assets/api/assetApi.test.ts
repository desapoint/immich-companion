import { describe, expect, it } from 'vitest';

import { createSearchCondition, createSearchGroup } from '../state/assetViewModel';
import { assetOriginalUrl, buildAssetSearchRequest } from './assetApi';

describe('structured asset API', () => {
  it('serializes nested conditions and stable pagination', () => {
    const root = createSearchGroup('and');
    const width = createSearchCondition('width');
    width.value = '1920';
    const favorite = createSearchCondition('favorite');
    favorite.value = 'false';
    const albumChoices = createSearchGroup('or');
    albumChoices.negate = true;
    root.children.push(width, favorite, albumChoices);

    expect(buildAssetSearchRequest(root, 2)).toEqual({
      expression: {
        kind: 'group',
        operator: 'and',
        negate: false,
        children: [
          { kind: 'condition', field: 'width', operator: 'at_least', value: 1920 },
          { kind: 'condition', field: 'favorite', operator: 'equals', value: false },
          { kind: 'group', operator: 'or', negate: true, children: [] },
        ],
      },
      page: 2,
      page_size: 24,
    });
  });

  it('allows callers to override the default number of results per page', () => {
    expect(buildAssetSearchRequest(createSearchGroup(), 3, 96)).toMatchObject({
      page: 3,
      page_size: 96,
    });
  });

  it('uses a distinct original-media endpoint for the fullscreen viewer', () => {
    expect(assetOriginalUrl('asset id')).toBe('/api/assets/asset%20id/original');
  });
});

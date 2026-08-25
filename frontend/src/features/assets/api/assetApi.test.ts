import { afterEach, describe, expect, it, vi } from 'vitest';

import { createSearchCondition, createSearchGroup } from '../state/assetViewModel';
import {
  assetOriginalUrl,
  buildAssetPreviewItems,
  buildAssetSearchRequest,
  executeAssetAction,
  normalizeAssetSearchResponse,
  planAssetAction,
} from './assetApi';

afterEach(() => vi.unstubAllGlobals());

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
      sort_field: 'taken_at',
      sort_direction: 'desc',
      page: 2,
      page_size: 24,
    });
  });

  it('allows callers to override the default number of results per page', () => {
    expect(buildAssetSearchRequest(
      createSearchGroup(),
      3,
      96,
      { field: 'filename', direction: 'asc' },
    )).toMatchObject({
      page: 3,
      page_size: 96,
      sort_field: 'filename',
      sort_direction: 'asc',
    });
  });

  it('uses a distinct original-media endpoint for the fullscreen viewer', () => {
    expect(assetOriginalUrl('asset id')).toBe('/api/assets/asset%20id/original');
  });

  it('builds reusable thumbnail-strip items from comparable assets', () => {
    expect(buildAssetPreviewItems([{
      id: 'stack member',
      type: 'IMAGE',
      original_file_name: 'stack.png',
      width: 800,
      height: 600,
      taken_at: null,
    }])).toEqual([{
      id: 'stack member',
      label: 'stack.png',
      thumbnailUrl: '/api/assets/stack%20member/thumbnail?size=thumbnail',
      meta: '800 × 600',
    }]);
  });

  it('normalizes relation fields while an older backend is being restarted', () => {
    const response = normalizeAssetSearchResponse({
      items: [{ id: 'asset' } as never],
      total: 1,
      page: 1,
      page_size: 24,
      pages: 1,
    });

    expect(response.items[0]).toMatchObject({
      albums: [],
      tags: [],
      stack: null,
      source: { kind: 'upload', library_id: null, original_path: null },
      immich_url: null,
    });
  });

  it('sends reviewed action plan and explicit confirmation contracts', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const path = String(input);
      return new Response(JSON.stringify(path.endsWith('/plan') ? {
        id: 'plan-1',
        action: 'remove_tag',
        operation: 'remove_tag',
        relation_ids: ['tag-1'],
        relations: [{ relation_id: 'tag-1', applicable_count: 1, skipped_count: 1 }],
        target_count: 2,
        applicable_count: 1,
        skipped_count: 1,
        missing_ids: [],
        destructive: false,
        status: 'planned',
        expires_at: '2026-08-25T12:00:00Z',
      } : {
        plan_id: 'plan-1',
        operation: 'remove_tag',
        target_count: 2,
        applied_count: 1,
        skipped_count: 1,
        applied_ids: ['asset-1'],
        skipped_ids: ['asset-2'],
        failed_ids: [],
        relation_results: [],
        verified: true,
        status: 'completed',
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetcher);
    const selection = {
      mode: 'explicit' as const,
      ids: ['asset-1', 'asset-2'],
      excluded_ids: [],
    };

    await planAssetAction(selection, 'remove_tag', ['tag-1']);
    await executeAssetAction('plan-1');

    expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toEqual({
      selection,
      action: 'remove_tag',
      relation_ids: ['tag-1'],
    });
    expect(JSON.parse(String(fetcher.mock.calls[1]?.[1]?.body))).toEqual({
      plan_id: 'plan-1',
      confirm: true,
    });
  });
});

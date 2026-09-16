import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  clearAllDuplicateResolutionHistory,
  clearDuplicateResolutionHistory,
  duplicateResolutionHistoryDetail,
} from './duplicateResolutionHistory';

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('duplicate resolution history helpers', () => {
  it('deletes the selected completed resolution', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('/api/assets/duplicates/history/resolution%2Fwith%20spaces');
      expect(init?.method).toBe('DELETE');
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal('fetch', fetchMock);

    await clearDuplicateResolutionHistory('resolution/with spaces');

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('finds a history detail across paged history', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('page=1')) {
        return jsonResponse({ items: [], total: 1, page: 1, page_size: 200, pages: 2 });
      }
      return jsonResponse({
        items: [{
          id: 'resolution-2',
          occurred_at: '2026-09-16T10:00:00Z',
          discovery_source: 'companion_similarity',
          provider_group_id: 'provider-2',
          review_status: 'reviewed_resolve',
          manual_action: 'resolve',
          member_count: 2,
          member_asset_ids: ['asset-a', 'asset-b'],
        }],
        total: 1,
        page: 2,
        page_size: 200,
        pages: 2,
      });
    });
    vi.stubGlobal('fetch', fetcher);

    const result = await duplicateResolutionHistoryDetail('resolution-2');

    expect(result.member_asset_ids).toEqual(['asset-a', 'asset-b']);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('clears every history page without skipping rows after deletion', async () => {
    let remaining = ['resolution-1', 'resolution-2'];
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'DELETE') {
        const id = decodeURIComponent(url.split('/').at(-1) ?? '');
        remaining = remaining.filter((value) => value !== id);
        return new Response(null, { status: 204 });
      }
      return jsonResponse({
        items: remaining.map((id) => ({
          id,
          occurred_at: '2026-09-16T10:00:00Z',
          discovery_source: 'immich_duplicate',
          provider_group_id: id,
          review_status: 'reviewed_resolve',
          manual_action: 'resolve',
          member_count: 2,
          member_asset_ids: ['asset-a', 'asset-b'],
        })),
        total: remaining.length,
        page: 1,
        page_size: 200,
        pages: remaining.length ? 1 : 0,
      });
    });
    vi.stubGlobal('fetch', fetcher);

    await expect(clearAllDuplicateResolutionHistory()).resolves.toBe(2);
    expect(remaining).toEqual([]);
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(2);
  });
});
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createRelation, deleteRelations, getRelations, getTagOptions, updateRelation } from './relationsApi';

afterEach(() => vi.unstubAllGlobals());

describe('relation management API', () => {
  it('normalizes paginated management data and forwards query state', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({
      items: [{ id: 'album-1', name: 'Trips', asset_count: 12 }],
      total: 51,
      page: 2,
      page_size: 25,
      pages: 3,
    }), {
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetcher);
    const controller = new AbortController();

    await expect(getRelations(
      'albums',
      2,
      ' Family ',
      'asset_count',
      'desc',
      controller.signal,
    )).resolves.toEqual({
      items: [{ id: 'album-1', name: 'Trips', asset_count: 12 }],
      total: 51,
      page: 2,
      pageSize: 25,
      pages: 3,
    });

    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/albums/manage?page=2&page_size=25&sort=asset_count&direction=desc&search=Family');
    expect(fetcher.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
  });

  it('loads tag parent choices from the live paginated management catalog', async () => {
    const fetcher = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      const secondPage = url.includes('page=2');
      return new Response(JSON.stringify(secondPage ? {
        items: [{ id: 'other', name: 'Other', asset_count: 0 }],
        total: 3,
        page: 2,
        page_size: 200,
        pages: 2,
      } : {
        items: [{
          id: 'root',
          name: 'People',
          asset_count: 0,
          children: [{ id: 'child', name: 'Family', parent_id: 'root', asset_count: 0 }],
        }],
        total: 3,
        page: 1,
        page_size: 200,
        pages: 2,
      }), { headers: { 'content-type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetcher);
    const controller = new AbortController();

    await expect(getTagOptions(controller.signal)).resolves.toEqual([
      { id: 'root', name: 'People' },
      { id: 'child', name: 'People / Family' },
      { id: 'other', name: 'Other' },
    ]);
    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/tags/manage?page=1&page_size=200&sort=name&direction=asc');
    expect(String(fetcher.mock.calls[1]?.[0])).toBe('/api/tags/manage?page=2&page_size=200&sort=name&direction=asc');
    expect(fetcher.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
    expect(fetcher.mock.calls[1]?.[1]?.signal).toBe(controller.signal);
  });

  it('uses API-only create, edit, and relation-only batch delete contracts', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ id: 'album-1', name: 'Family', asset_count: 0 }), {
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetcher);

    await createRelation('albums', { name: 'Family', description: 'Summer' });
    await updateRelation('albums', 'album id', { name: 'Family 2026' });
    await deleteRelations('albums', ['album-1', 'album-2']);

    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/albums/manage');
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: 'POST', body: '{"name":"Family","description":"Summer"}' });
    expect(String(fetcher.mock.calls[1]?.[0])).toBe('/api/albums/manage/album%20id');
    expect(fetcher.mock.calls[1]?.[1]).toMatchObject({ method: 'PATCH', body: '{"name":"Family 2026"}' });
    expect(String(fetcher.mock.calls[2]?.[0])).toBe('/api/albums/manage/batch-delete');
    expect(fetcher.mock.calls[2]?.[1]).toMatchObject({ method: 'POST', body: '{"ids":["album-1","album-2"]}' });
  });

  it('surfaces safe API errors to the management interface', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ detail: 'Delete child tags first.' }), {
      status: 409,
      headers: { 'content-type': 'application/json' },
    })));

    await expect(deleteRelations('tags', ['parent'])).rejects.toThrow('Delete child tags first.');
  });
});

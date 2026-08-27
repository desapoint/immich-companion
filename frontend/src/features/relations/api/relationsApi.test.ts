import { afterEach, describe, expect, it, vi } from 'vitest';

import { createRelation, deleteRelations, getRelations, updateRelation } from './relationsApi';

afterEach(() => vi.unstubAllGlobals());

describe('relation management API', () => {
  it('requests paginated album management data with search and sorting', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ items: [], total: 0, page: 2, page_size: 25, pages: 0 }), {
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetcher);

    await getRelations('albums', 2, ' Family ', 'asset_count', 'desc');

    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/albums/manage?page=2&page_size=25&sort=asset_count&direction=desc&search=Family');
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

import { describe, expect, it, vi } from 'vitest';

import { createAlbumRepository, type AlbumApiFetcher } from './albumRepository';

const album = {
  id: '11111111-1111-4111-8111-111111111111',
  name: 'Family',
  description: 'Summer archive',
  album_thumbnail_asset_id: '22222222-2222-4222-8222-222222222222',
  asset_count: 14,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-02T12:00:00Z',
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('live V2 album repository', () => {
  it('maps paged API albums and supports description sorting', async () => {
    const fetcher = vi.fn<AlbumApiFetcher>(async () => jsonResponse({
      items: [album], total: 100, page: 2, page_size: 48, pages: 3,
    }));
    const repository = createAlbumRepository(fetcher);
    const controller = new AbortController();

    const result = await repository.search({
      page: 2,
      pageSize: 48,
      query: ' Summer ',
      sort: { field: 'description', direction: 'desc' },
      signal: controller.signal,
    });

    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/albums/manage?page=2&page_size=48&sort=description&direction=desc&search=Summer');
    expect(fetcher.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
    expect(result).toMatchObject({
      total: 100,
      page: 2,
      pageSize: 48,
      nextCursor: '3',
      items: [{
        id: album.id,
        album_name: 'Family',
        description: 'Summer archive',
        album_thumbnail_asset_id: album.album_thumbnail_asset_id,
        asset_count: 14,
        immich_created_at: album.created_at,
        immich_updated_at: album.updated_at,
        synced_at: album.updated_at,
      }],
    });
  });

  it('uses cursor pages for searchable album options', async () => {
    const fetcher = vi.fn<AlbumApiFetcher>(async () => jsonResponse({
      items: [album], total: 3, page: 2, page_size: 1, pages: 3,
    }));
    const repository = createAlbumRepository(fetcher);
    const controller = new AbortController();

    const result = await repository.searchOptions({ query: 'Fam', pageSize: 1, cursor: '2', signal: controller.signal });

    expect(String(fetcher.mock.calls[0]?.[0])).toBe('/api/albums/manage?page=2&page_size=1&sort=name&direction=asc&search=Fam');
    expect(fetcher.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
    expect(result).toEqual({
      items: [{ value: album.id, label: 'Family', subtitle: '14 assets' }],
      nextCursor: '3',
    });
  });

  it('connects get, create, update, and batch delete operations', async () => {
    const fetcher = vi.fn<AlbumApiFetcher>(async (input, init) => {
      const path = String(input);
      if (path.endsWith('/missing')) return jsonResponse({ detail: 'The Immich relation was not found.' }, 404);
      if (path.endsWith('/batch-delete')) {
        return jsonResponse({ completed: [album.id], failed: ['failed-id'], total: 2 });
      }
      if (init?.method === 'PATCH') return jsonResponse(album);
      return jsonResponse(album);
    });
    const repository = createAlbumRepository(fetcher);

    expect(await repository.getById(album.id)).toMatchObject({ id: album.id, album_name: 'Family' });
    expect(await repository.getById('missing')).toBeUndefined();
    expect(await repository.create('Family', 'Summer archive')).toMatchObject({ id: album.id });
    expect(await repository.update(album.id, { name: 'Family 2026' })).toEqual({ affectedIds: [album.id], failed: [] });
    expect(await repository.delete([album.id, 'failed-id'])).toEqual({
      affectedIds: [album.id],
      failed: [{ id: 'failed-id', reason: 'Immich could not delete this album.' }],
    });

    expect(fetcher.mock.calls.map(([input]) => String(input))).toEqual([
      `/api/albums/manage/${album.id}`,
      '/api/albums/manage/missing',
      '/api/albums/manage',
      `/api/albums/manage/${album.id}`,
      '/api/albums/manage/batch-delete',
    ]);
    expect(fetcher.mock.calls[2]?.[1]).toMatchObject({
      method: 'POST',
      body: '{"name":"Family","description":"Summer archive"}',
    });
    expect(fetcher.mock.calls[3]?.[1]).toMatchObject({
      method: 'PATCH',
      body: '{"name":"Family 2026"}',
    });
  });

  it('returns a per-album update failure without losing its reason', async () => {
    const fetcher = vi.fn<AlbumApiFetcher>(async () => jsonResponse({ detail: 'Album update rejected.' }, 409));
    const repository = createAlbumRepository(fetcher);

    expect(await repository.update(album.id, { description: 'Changed' })).toEqual({
      affectedIds: [],
      failed: [{ id: album.id, reason: 'Album update rejected.' }],
    });
  });
});

import type {
  AlbumRecord,
  AlbumRepository,
  AlbumSearchQuery,
  MutationResult,
  OptionSearchQuery,
  PageResult,
} from '../contracts';

export type AlbumApiFetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

interface AlbumManagementItem {
  id: string;
  name: string;
  description: string;
  album_thumbnail_asset_id: string | null;
  asset_count: number;
  created_at: string | null;
  updated_at: string | null;
}

interface AlbumManagementPage {
  items: AlbumManagementItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface AlbumBatchDeleteResponse {
  completed: string[];
  failed: string[];
  total: number;
}

class AlbumApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'AlbumApiError';
  }
}

async function requestJson<T>(fetcher: AlbumApiFetcher, path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has('accept')) headers.set('accept', 'application/json');
  const response = await fetcher(path, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const message = typeof body?.detail === 'string'
      ? body.detail
      : `Album request failed with HTTP ${response.status}.`;
    throw new AlbumApiError(response.status, message);
  }
  return response.status === 204 ? undefined as T : await response.json() as T;
}

function normalizeAlbum(item: AlbumManagementItem): AlbumRecord {
  return {
    id: item.id,
    album_name: item.name,
    description: item.description ?? '',
    album_thumbnail_asset_id: item.album_thumbnail_asset_id ?? null,
    asset_count: item.asset_count,
    immich_created_at: item.created_at ?? '',
    immich_updated_at: item.updated_at ?? '',
    synced_at: item.updated_at ?? '',
  };
}

function pageFromCursor(cursor: string | null | undefined): number {
  if (!cursor) return 1;
  const parsed = Number.parseInt(cursor, 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function managementPath(query: AlbumSearchQuery, page: number): string {
  const sort = query.sort.field === 'assets' ? 'asset_count' : query.sort.field;
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(query.pageSize),
    sort,
    direction: query.sort.direction,
  });
  if (query.query?.trim()) params.set('search', query.query.trim());
  return `/api/albums/manage?${params}`;
}

function mutationFailure(id: string, error: unknown): MutationResult {
  return {
    affectedIds: [],
    failed: [{ id, reason: error instanceof Error ? error.message : 'Immich could not update this album.' }],
  };
}

export function createAlbumRepository(fetcher: AlbumApiFetcher = globalThis.fetch): AlbumRepository {
  async function search(query: AlbumSearchQuery): Promise<PageResult<AlbumRecord>> {
    const page = query.page ?? pageFromCursor(query.cursor);
    const result = await requestJson<AlbumManagementPage>(fetcher, managementPath(query, page), {
      signal: query.signal,
    });
    return {
      items: result.items.map(normalizeAlbum),
      total: result.total,
      pageSize: result.page_size,
      page: result.page,
      nextCursor: result.page < result.pages ? String(result.page + 1) : null,
    };
  }

  async function searchOptions(query: OptionSearchQuery) {
    const result = await search({
      pageSize: query.pageSize,
      cursor: query.cursor,
      query: query.query,
      sort: { field: 'name', direction: 'asc' },
      signal: query.signal,
    });
    return {
      items: result.items.map((album) => ({
        value: album.id,
        label: album.album_name,
        subtitle: `${album.asset_count.toLocaleString()} assets`,
      })),
      nextCursor: result.nextCursor,
    };
  }

  return {
    search,
    searchOptions,
    async getById(id) {
      try {
        return normalizeAlbum(await requestJson<AlbumManagementItem>(fetcher, `/api/albums/manage/${encodeURIComponent(id)}`));
      } catch (error) {
        if (error instanceof AlbumApiError && error.status === 404) return undefined;
        throw error;
      }
    },
    async create(name, description = '') {
      return normalizeAlbum(await requestJson<AlbumManagementItem>(fetcher, '/api/albums/manage', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name, description }),
      }));
    },
    async update(id, update) {
      try {
        await requestJson<AlbumManagementItem>(fetcher, `/api/albums/manage/${encodeURIComponent(id)}`, {
          method: 'PATCH',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(update),
        });
        return { affectedIds: [id], failed: [] };
      } catch (error) {
        return mutationFailure(id, error);
      }
    },
    async delete(ids) {
      const result = await requestJson<AlbumBatchDeleteResponse>(fetcher, '/api/albums/manage/batch-delete', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ ids }),
      });
      return {
        affectedIds: result.completed,
        failed: result.failed.map((id) => ({ id, reason: 'Immich could not delete this album.' })),
      };
    },
  };
}

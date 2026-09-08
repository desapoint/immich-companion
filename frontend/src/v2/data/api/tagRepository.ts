import type {
  MutationResult,
  OptionSearchQuery,
  PageResult,
  TagHierarchyRow,
  TagRecord,
  TagRepository,
  TagSearchQuery,
} from '../contracts';

export type TagApiFetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

interface TagManagementItem {
  id: string;
  name: string;
  color: string | null;
  parent_id: string | null;
  parent_path: string[];
  asset_count: number;
  child_count: number;
  children: TagManagementItem[];
}

interface TagManagementPage {
  items: TagManagementItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface TagBatchDeleteResponse {
  completed: string[];
  failed: string[];
  total: number;
}

class TagApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'TagApiError';
  }
}

async function requestJson<T>(fetcher: TagApiFetcher, path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has('accept')) headers.set('accept', 'application/json');
  const response = await fetcher(path, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const message = typeof body?.detail === 'string'
      ? body.detail
      : `Tag request failed with HTTP ${response.status}.`;
    throw new TagApiError(response.status, message);
  }
  return response.status === 204 ? undefined as T : await response.json() as T;
}

function canonicalPath(item: TagManagementItem): string {
  return [...item.parent_path, item.name].join(' / ');
}

function normalizeTag(item: TagManagementItem): TagRecord {
  const path = canonicalPath(item);
  return {
    id: item.id,
    tag_name: path,
    tag_value: path,
    color: item.color,
    asset_count: item.asset_count,
    synced_at: '',
  };
}

function normalizeRow(item: TagManagementItem): TagHierarchyRow {
  return {
    id: item.id,
    name: item.name,
    path: canonicalPath(item),
    parent: item.parent_path.join(' / '),
    assets: item.asset_count,
    children: item.child_count,
    color: item.color,
    synthetic: false,
    realTagIds: [item.id],
  };
}

function pageFromCursor(cursor: string | null | undefined): number {
  if (!cursor) return 1;
  const parsed = Number.parseInt(cursor, 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function managementPath(query: TagSearchQuery, page: number): string {
  const sort = query.sort.field === 'assets'
    ? 'asset_count'
    : query.sort.field === 'children'
      ? 'child_count'
      : query.sort.field;
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(query.pageSize),
    sort,
    direction: query.sort.direction,
    flat: 'true',
    include_hierarchy: String(query.includeHierarchy === true),
  });
  if (query.query?.trim()) params.set('search', query.query.trim());
  return `/api/tags/manage?${params}`;
}

function mutationFailure(id: string, error: unknown): MutationResult {
  return {
    affectedIds: [],
    failed: [{ id, reason: error instanceof Error ? error.message : 'Immich could not update this tag.' }],
  };
}

export function createTagRepository(fetcher: TagApiFetcher = globalThis.fetch): TagRepository {
  async function search(query: TagSearchQuery): Promise<PageResult<TagHierarchyRow>> {
    const page = query.page ?? pageFromCursor(query.cursor);
    const result = await requestJson<TagManagementPage>(fetcher, managementPath(query, page), {
      signal: query.signal,
    });
    return {
      items: result.items.map(normalizeRow),
      total: result.total,
      pageSize: result.page_size,
      page: result.page,
      nextCursor: result.page < result.pages ? String(result.page + 1) : null,
    };
  }

  async function allTags(): Promise<TagManagementItem[]> {
    const items: TagManagementItem[] = [];
    let page = 1;
    while (true) {
      const result = await requestJson<TagManagementPage>(
        fetcher,
        managementPath({
          page,
          pageSize: 200,
          includeHierarchy: true,
          sort: { field: 'path', direction: 'asc' },
        }, page),
      );
      items.push(...result.items);
      if (page >= result.pages) return items;
      page += 1;
    }
  }

  async function resolveParentId(parentPath: string): Promise<string | null> {
    const normalized = parentPath.trim();
    if (!normalized) return null;
    const parent = (await allTags()).find((item) => canonicalPath(item) === normalized);
    if (!parent) throw new Error(`Parent tag “${normalized}” no longer exists.`);
    return parent.id;
  }

  return {
    search,
    async searchOptions(query: OptionSearchQuery) {
      const result = await search({
        pageSize: query.pageSize,
        cursor: query.cursor,
        query: query.query,
        includeHierarchy: true,
        sort: { field: 'path', direction: 'asc' },
        signal: query.signal,
      });
      return {
        items: result.items.map((tag) => ({
          value: tag.id,
          label: tag.path,
          subtitle: `${tag.assets.toLocaleString()} assets`,
        })),
        nextCursor: result.nextCursor,
      };
    },
    async parentOptions(excludeTagId) {
      const items = await allTags();
      const excluded = excludeTagId ? items.find((item) => item.id === excludeTagId) : undefined;
      const excludedPath = excluded ? canonicalPath(excluded) : '';
      return items
        .filter((item) => {
          const path = canonicalPath(item);
          return item.id !== excludeTagId
            && (!excludedPath || !path.startsWith(`${excludedPath} / `));
        })
        .map((item) => ({
          value: canonicalPath(item),
          label: item.name,
          subtitle: item.parent_path.length ? item.parent_path.join(' / ') : 'Root',
        }));
    },
    async getById(id) {
      try {
        return normalizeTag(await requestJson<TagManagementItem>(
          fetcher,
          `/api/tags/manage/${encodeURIComponent(id)}`,
        ));
      } catch (error) {
        if (error instanceof TagApiError && error.status === 404) return undefined;
        throw error;
      }
    },
    async create(name, color = null, parentPath = '') {
      const parentId = await resolveParentId(parentPath);
      return normalizeTag(await requestJson<TagManagementItem>(fetcher, '/api/tags/manage', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name, color, parent_id: parentId }),
      }));
    },
    async update(id, update) {
      try {
        await requestJson<TagManagementItem>(fetcher, `/api/tags/manage/${encodeURIComponent(id)}`, {
          method: 'PATCH',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ color: update.color }),
        });
        return { affectedIds: [id], failed: [] };
      } catch (error) {
        return mutationFailure(id, error);
      }
    },
    async delete(ids) {
      if (!ids.length) return { affectedIds: [], failed: [] };
      const result = await requestJson<TagBatchDeleteResponse>(fetcher, '/api/tags/manage/batch-delete', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ ids }),
      });
      return {
        affectedIds: result.completed,
        failed: result.failed.map((id) => ({
          id,
          reason: 'Immich could not delete this tag. Delete child tags first if it is a parent.',
        })),
      };
    },
  };
}

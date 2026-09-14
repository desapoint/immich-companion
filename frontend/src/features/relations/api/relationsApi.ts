import { requestJson } from '../../shared/api/http';
import type { PageResult } from '../../../lib/types/collection';
import type { ManagedRelation, RelationKind, RelationPage } from '../types/relations';

export interface RelationOption { id: string; name: string; }

export async function getRelations(
  kind: RelationKind,
  page: number,
  search: string,
  sort: 'name' | 'asset_count',
  direction: 'asc' | 'desc',
  signal?: AbortSignal,
): Promise<PageResult<ManagedRelation>> {
  const params = new URLSearchParams({ page: String(page), page_size: '25', sort, direction });
  if (search.trim()) params.set('search', search.trim());
  const result = await requestJson<RelationPage>(`/api/${kind}/manage?${params}`, { signal });
  return {
    items: result.items,
    page: result.page,
    pageSize: result.page_size,
    pages: result.pages,
    total: result.total,
  };
}

function flattenTagOptions(nodes: ManagedRelation[], parentPath: string[] = []): RelationOption[] {
  return nodes.flatMap((node) => {
    const path = [...parentPath, node.name];
    return [
      { id: node.id, name: path.join(' / ') },
      ...flattenTagOptions(node.children ?? [], path),
    ];
  });
}

/**
 * Parent choices come from Immich's live management catalog rather than the
 * companion search-option cache. Fetch sequentially in bounded pages so a
 * create, rename, move, or delete is reflected immediately without a sync.
 */
export async function getTagOptions(signal?: AbortSignal): Promise<RelationOption[]> {
  const options: RelationOption[] = [];
  let page = 1;
  let pages = 1;
  do {
    const params = new URLSearchParams({
      page: String(page),
      page_size: '200',
      sort: 'name',
      direction: 'asc',
    });
    const result = await requestJson<RelationPage>(`/api/tags/manage?${params}`, { signal });
    options.push(...flattenTagOptions(result.items));
    pages = result.pages;
    page += 1;
  } while (page <= pages);
  return options;
}

export function createRelation(
  kind: RelationKind,
  data: Record<string, unknown>,
): Promise<ManagedRelation> {
  return requestJson(`/api/${kind}/manage`, { method: 'POST', json: data });
}

export function updateRelation(
  kind: RelationKind,
  id: string,
  data: Record<string, unknown>,
): Promise<ManagedRelation> {
  return requestJson(`/api/${kind}/manage/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    json: data,
  });
}

export function deleteRelations(
  kind: RelationKind,
  ids: string[],
): Promise<{ completed: string[]; failed: string[]; total: number }> {
  return requestJson(`/api/${kind}/manage/batch-delete`, {
    method: 'POST',
    json: { ids },
  });
}

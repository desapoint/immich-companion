import type {
  MutationResult,
  AssetSelectionMembership,
  AssetSelectionWorkspace,
  CollectionDeletePlan,
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
  real_tag_ids?: string[];
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
type ApiSelection={id:string;entity_kind:'tag';revision:number;selected_count:number;status:'active'|'cancelled'|'expired';expires_at:string};
type ApiMembership={selection:ApiSelection;selected_ids:string[]};
type ApiDeletePlan={id:string;entity_kind:'tag';selection_id:string;target_digest:string;target_count:number;applicable_count:number;skipped_count:number;status:CollectionDeletePlan['status'];expires_at:string;results:Array<{id:string;status:'completed'|'skipped'|'failed';reason:string|null}>};

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
    realTagIds: item.real_tag_ids?.length ? [...new Set(item.real_tag_ids)] : [item.id],
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
function normalizeSelection(value:ApiSelection):AssetSelectionWorkspace{return{id:value.id,entityKind:value.entity_kind,revision:value.revision,selectedCount:value.selected_count,status:value.status,expiresAt:value.expires_at}}
function normalizePlan(value:ApiDeletePlan):CollectionDeletePlan{return{id:value.id,entityKind:value.entity_kind,selectionId:value.selection_id,targetDigest:value.target_digest,targetCount:value.target_count,applicableCount:value.applicable_count,skippedCount:value.skipped_count,status:value.status,expiresAt:value.expires_at,results:value.results}}

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
    async createSelection(){return normalizeSelection(await requestJson<ApiSelection>(fetcher,'/api/tags/selections',{method:'POST'}))},
    async selectAllIntoSelection(selectionId,criteria){return normalizeSelection(await requestJson<ApiSelection>(fetcher,`/api/tags/selections/${encodeURIComponent(selectionId)}/select-all`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({query:criteria.query,include_hierarchy:criteria.includeHierarchy??false})}))},
    async updateMatchingSelection(selectionId,criteria,selected,revision){return normalizeSelection(await requestJson<ApiSelection>(fetcher,`/api/tags/selections/${encodeURIComponent(selectionId)}/matching`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({query:criteria.query,include_hierarchy:criteria.includeHierarchy??false,selected,revision})}))},
    async matchingSelectionState(selectionId,criteria){const state=await requestJson<{matching_count:number;selected_matching_count:number}>(fetcher,`/api/tags/selections/${encodeURIComponent(selectionId)}/matching-status`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({query:criteria.query,include_hierarchy:criteria.includeHierarchy??false})});return{matchingCount:state.matching_count,selectedMatchingCount:state.selected_matching_count}},
    async updateSelectionMembers(selectionId,ids,selected,revision){return normalizeSelection(await requestJson<ApiSelection>(fetcher,`/api/tags/selections/${encodeURIComponent(selectionId)}/members`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({ids:[...new Set(ids)],selected,revision})}))},
    async selectionMembership(selectionId,ids){try{const value=await requestJson<ApiMembership>(fetcher,`/api/tags/selections/${encodeURIComponent(selectionId)}/membership`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({ids:[...new Set(ids)]})});return{selection:normalizeSelection(value.selection),selectedIds:value.selected_ids} satisfies AssetSelectionMembership}catch(error){if(error instanceof TagApiError&&error.status===404)return null;throw error}},
    async planDelete(selectionId){return normalizePlan(await requestJson<ApiDeletePlan>(fetcher,'/api/tags/actions/delete/plan',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({selection_id:selectionId})}))},
    async executeDelete(planId){let previousCount=-1;for(;;){const plan=normalizePlan(await requestJson<ApiDeletePlan>(fetcher,'/api/tags/actions/delete/execute',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({plan_id:planId})}));if(plan.status!=='partial')return plan;if(plan.results.length<=previousCount)throw new Error('Tag deletion made no progress; retry the saved plan.');previousCount=plan.results.length}},
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

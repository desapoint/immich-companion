import type { ManagedRelation, RelationKind, RelationPage } from '../types/relations';

export interface RelationOption { id: string; name: string; }

async function request<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, { headers: { Accept: 'application/json', ...init?.headers }, ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed with HTTP ${response.status}.`);
  }
  return response.status === 204 ? (undefined as T) : (await response.json() as T);
}

export function getRelations(kind: RelationKind, page: number, search: string, sort: 'name' | 'asset_count', direction: 'asc' | 'desc'): Promise<RelationPage> {
  const params = new URLSearchParams({ page: String(page), page_size: '25', sort, direction });
  if (search.trim()) params.set('search', search.trim());
  return request(`/api/${kind}/manage?${params}`);
}

export function getTagOptions(): Promise<RelationOption[]> {
  return request('/api/tags');
}

export function createRelation(kind: RelationKind, data: Record<string, unknown>): Promise<ManagedRelation> {
  return request(`/api/${kind}/manage`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
}

export function updateRelation(kind: RelationKind, id: string, data: Record<string, unknown>): Promise<ManagedRelation> {
  return request(`/api/${kind}/manage/${encodeURIComponent(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
}

export function deleteRelations(kind: RelationKind, ids: string[]): Promise<{ completed: string[]; failed: string[]; total: number }> {
  return request(`/api/${kind}/manage/batch-delete`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids }) });
}

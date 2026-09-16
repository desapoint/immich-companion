import type {
  AssetSearchCriteria,
  PageResult,
  ResolvedLibraryDataSource,
  SavedSearchRecord,
  SavedSearchRepository,
  SavedSearchQuery,
} from '../contracts';

const STORAGE_KEY = 'immichCompanionV2DemoSavedSearches.v1';
const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
const delay = () => sleep(80 + Math.floor(Math.random() * 121));

function cloneCriteria(criteria: AssetSearchCriteria): AssetSearchCriteria {
  return JSON.parse(JSON.stringify(criteria)) as AssetSearchCriteria;
}

function seedRecords(): SavedSearchRecord[] {
  const now = new Date().toISOString();
  return [
    {
      id: 'saved-favorite-images',
      name: 'Favorite images not archived',
      description: 'Favorite image assets that are not archived.',
      criteria: { mode: 'expert', sort: { field: 'takenDate', direction: 'desc' }, logic: 'AND', negated: false, rules: [
        { field: 'mediaType', op: 'is', value: 'Image' },
        { field: 'favorite', op: 'is', value: 'true' },
        { field: 'archived', op: 'is', value: 'false' },
      ], groups: [] },
      createdAt: now,
      updatedAt: now,
    },
    {
      id: 'saved-family-vacation',
      name: 'Family album or Vacation tag',
      description: 'Images in a Family album or tagged Vacation.',
      criteria: { mode: 'expert', sort: { field: 'takenDate', direction: 'desc' }, logic: 'AND', negated: false, rules: [
        { field: 'mediaType', op: 'is', value: 'Image' },
      ], groups: [{ logic: 'OR', negated: false, rules: [
        { field: 'album', op: 'contains', value: 'Family' },
        { field: 'tag', op: 'contains', value: 'Vacation' },
      ], groups: [] }] },
      createdAt: now,
      updatedAt: now,
    },
    {
      id: 'saved-large-landscape',
      name: 'Large landscape images',
      description: 'Large images wider than they are tall.',
      criteria: { mode: 'expert', sort: { field: 'takenDate', direction: 'desc' }, logic: 'AND', negated: false, rules: [
        { field: 'mediaType', op: 'is', value: 'Image' },
        { field: 'width', op: 'gte', value: '3000' },
        { field: 'aspectRatio', op: 'gt', value: '1' },
      ], groups: [] },
      createdAt: now,
      updatedAt: now,
    },
  ];
}

let records: SavedSearchRecord[] | null = null;

function persist(): void {
  if (typeof localStorage !== 'undefined' && records) localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
}

function ensureRecords(): SavedSearchRecord[] {
  if (records) return records;
  if (typeof localStorage !== 'undefined') {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as SavedSearchRecord[];
        if (Array.isArray(parsed)) {
          records = parsed;
          return records;
        }
      }
    } catch {}
  }
  records = seedRecords();
  persist();
  return records;
}

function page(items: SavedSearchRecord[], query: SavedSearchQuery): PageResult<SavedSearchRecord> {
  const pageSize = Math.max(1, query.pageSize);
  const offset = query.page !== undefined ? Math.max(0, (Math.max(1, query.page) - 1) * pageSize) : Math.max(0, Number(query.cursor ?? 0) || 0);
  const slice = items.slice(offset, offset + pageSize);
  return { items: slice, total: items.length, pageSize, page: query.page, nextCursor: offset + slice.length < items.length ? String(offset + slice.length) : null };
}

export function createDemoSavedSearchRepository(): SavedSearchRepository {
  return {
    async getById(id) {
      await delay();
      const row = ensureRecords().find((record) => record.id === id);
      return row ? { ...row, criteria: cloneCriteria(row.criteria) } : undefined;
    },
    async search(query) {
      await delay();
      const normalized = (query.query ?? '').trim().toLowerCase();
      const sort = query.sort ?? { field: 'updatedAt', direction: 'desc' as const };
      const mul = sort.direction === 'desc' ? -1 : 1;
      const filtered = ensureRecords()
        .filter((record) => !normalized || `${record.name}\n${record.description}`.toLowerCase().includes(normalized))
        .sort((a, b) => sort.field === 'name' ? a.name.localeCompare(b.name) * mul : a.updatedAt.localeCompare(b.updatedAt) * mul)
        .map((record) => ({ ...record, criteria: cloneCriteria(record.criteria) }));
      return page(filtered, query);
    },
    async create(input) {
      await delay();
      const name = input.name.trim();
      if (!name) throw new Error('Saved search name is required.');
      const now = new Date().toISOString();
      const record: SavedSearchRecord = {
        id: `saved-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
        name,
        description: input.description?.trim() ?? '',
        criteria: cloneCriteria(input.criteria),
        createdAt: now,
        updatedAt: now,
      };
      ensureRecords().unshift(record);
      persist();
      return { ...record, criteria: cloneCriteria(record.criteria) };
    },
    async update(id, patch) {
      await delay();
      const index = ensureRecords().findIndex((record) => record.id === id);
      if (index < 0) return { affectedIds: [], failed: [{ id, reason: 'Saved search not found' }] };
      const current = ensureRecords()[index];
      const name = patch.name === undefined ? current.name : patch.name.trim();
      if (!name) return { affectedIds: [], failed: [{ id, reason: 'Saved search name is required' }] };
      ensureRecords()[index] = {
        ...current,
        name,
        description: patch.description === undefined ? current.description : patch.description.trim(),
        criteria: patch.criteria ? cloneCriteria(patch.criteria) : current.criteria,
        updatedAt: new Date().toISOString(),
      };
      persist();
      return { affectedIds: [id], failed: [] };
    },
    async delete(ids) {
      await delay();
      const idSet = new Set(ids);
      const existing = ensureRecords().filter((record) => idSet.has(record.id)).map((record) => record.id);
      records = ensureRecords().filter((record) => !idSet.has(record.id));
      persist();
      return { affectedIds: existing, failed: ids.filter((id) => !existing.includes(id)).map((id) => ({ id, reason: 'Saved search not found' })) };
    },
  };
}

export function withDemoSavedSearches(source: Omit<ResolvedLibraryDataSource, 'savedSearches'> & { savedSearches?: SavedSearchRepository }): ResolvedLibraryDataSource {
  return { ...source, savedSearches: source.savedSearches ?? createDemoSavedSearchRepository() } as ResolvedLibraryDataSource;
}

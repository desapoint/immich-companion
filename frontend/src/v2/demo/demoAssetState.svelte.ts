import type { AssetSelectionState } from '../components/assetSelection';

export type DemoAssetRecord = {
  id: string;
  owner_id: string | null;
  library_id: string | null;
  asset_type: 'IMAGE' | 'VIDEO' | 'AUDIO' | 'OTHER';
  original_file_name: string;
  original_path: string | null;
  original_mime_type: string | null;
  checksum: string | null;
  file_size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  file_created_at: string;
  file_modified_at: string;
  local_date_time: string | null;
  immich_created_at: string | null;
  immich_updated_at: string | null;
  is_favorite: boolean;
  is_archived: boolean;
  is_offline: boolean;
  is_edited: boolean;
  has_metadata: boolean;
  visibility: string | null;
  live_photo_video_id: string | null;
  tags: DemoAssetTagSnapshot[];
  stack: DemoAssetStackSnapshot | null;
  synced_at: string;
};

export type DemoTrashApiAsset = {
  id: string;
  type: DemoAssetRecord['asset_type'];
  original_file_name: string;
  original_mime_type: string | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  taken_at: string;
  file_modified_at: string;
  is_favorite: boolean;
  is_archived: boolean;
  restore_path: string | null;
};

export type DemoAssetTagSnapshot = { id: string; name: string; value: string; color: string | null };
export type DemoAssetStackSnapshot = { id: string; primaryAssetId: string; assetCount: number; assets: string[] };

export type DemoAlbumRecord = {
  id: string;
  album_name: string;
  description: string;
  album_thumbnail_asset_id: string | null;
  asset_count: number;
  immich_created_at: string;
  immich_updated_at: string;
  synced_at: string;
};

export type DemoAlbumAssetRecord = { album_id: string; asset_id: string };
export type DemoTagRecord = { id: string; tag_name: string; tag_value: string; color: string | null; asset_count: number; synced_at: string };
export type DemoTagAssetRecord = { tag_id: string; asset_id: string };

type DemoAssetOverride = Pick<DemoAssetRecord, 'is_favorite' | 'is_archived'>;
type PersistedDemoState = {
  version: 2;
  asset_overrides: Record<string, DemoAssetOverride>;
  trash_api_ids: string[];
};

const STORAGE_KEY = 'immichCompanionV2DemoAssetState.v2';
const LEGACY_STORAGE_KEY = 'immichCompanionV2DemoAssetState.v1';
const INDEXED_ASSET_COUNT = 2418;
const INITIAL_TRASH_COUNT = 126;
const TOTAL_DEMO_ASSET_COUNT = INDEXED_ASSET_COUNT + INITIAL_TRASH_COUNT;
const DEMO_OWNER_ID = uuidFor(900001);
const DEMO_LIBRARY_ID = uuidFor(900002);

function uuidFor(index: number): string {
  return `00000000-0000-4000-8000-${index.toString(16).padStart(12, '0')}`;
}

function isoFor(index: number): string {
  const day = 21 - (index % 18);
  const hour = index % 24;
  return `2026-08-${String(Math.max(1, day)).padStart(2, '0')}T${String(hour).padStart(2, '0')}:00:00.000Z`;
}

function buildAsset(index: number): DemoAssetRecord {
  const isVideo = index % 11 === 0;
  const created = isoFor(index);
  return {
    id: uuidFor(index + 1),
    owner_id: DEMO_OWNER_ID,
    library_id: index % 5 === 0 ? DEMO_LIBRARY_ID : null,
    asset_type: isVideo ? 'VIDEO' : 'IMAGE',
    original_file_name: `${isVideo ? 'VID' : 'IMG'}_${String(index + 1).padStart(4, '0')}.${isVideo ? 'mp4' : 'jpg'}`,
    original_path: `/demo/library/2026/${isVideo ? 'video' : 'photo'}/${index + 1}`,
    original_mime_type: isVideo ? 'video/mp4' : 'image/jpeg',
    checksum: `demo-checksum-${index + 1}`,
    file_size_bytes: 1_500_000 + index * 4096,
    width: isVideo ? 1920 : index % 4 === 0 ? 4032 : 3024,
    height: isVideo ? 1080 : index % 4 === 0 ? 3024 : 4032,
    duration: isVideo ? 12_000 + (index % 40) * 1000 : null,
    file_created_at: created,
    file_modified_at: created,
    local_date_time: created,
    immich_created_at: created,
    immich_updated_at: created,
    is_favorite: index % 7 === 0,
    is_archived: index % 13 === 0,
    is_offline: false,
    is_edited: index % 17 === 0,
    has_metadata: true,
    visibility: null,
    live_photo_video_id: null,
    tags: [],
    stack: null,
    synced_at: '2026-09-05T20:00:00.000Z',
  };
}

const baseAssetsById = new Map<string, DemoAssetRecord>(
  Array.from({ length: TOTAL_DEMO_ASSET_COUNT }, (_, index) => {
    const asset = buildAsset(index);
    return [asset.id, asset] as const;
  }),
);

function cloneAsset(asset: DemoAssetRecord): DemoAssetRecord {
  return { ...asset, tags: asset.tags.map((tag) => ({ ...tag })), stack: asset.stack ? { ...asset.stack, assets: [...asset.stack.assets] } : null };
}

function toTrashApiAsset(asset: DemoAssetRecord): DemoTrashApiAsset {
  return {
    id: asset.id,
    type: asset.asset_type,
    original_file_name: asset.original_file_name,
    original_mime_type: asset.original_mime_type,
    width: asset.width,
    height: asset.height,
    duration: asset.duration,
    taken_at: asset.file_created_at,
    file_modified_at: asset.file_modified_at,
    is_favorite: asset.is_favorite,
    is_archived: asset.is_archived,
    restore_path: asset.original_path,
  };
}

function initialTrashIds(): Set<string> {
  return new Set(Array.from({ length: INITIAL_TRASH_COUNT }, (_, offset) => uuidFor(INDEXED_ASSET_COUNT + offset + 1)));
}

function buildStateFromTrashIds(trashIds: Set<string>) {
  const assets: DemoAssetRecord[] = [];
  const trash_api_items: DemoTrashApiAsset[] = [];
  for (const base of baseAssetsById.values()) {
    const asset = cloneAsset(base);
    if (trashIds.has(asset.id)) trash_api_items.push(toTrashApiAsset(asset));
    else assets.push(asset);
  }
  return { assets, trash_api_items };
}

function seedAlbums(): DemoAlbumRecord[] {
  return ['Family', 'Vacation', 'Favorites review'].map((name, index) => ({
    id: uuidFor(910000 + index), album_name: name, description: '', album_thumbnail_asset_id: null, asset_count: 0,
    immich_created_at: '2026-08-01T00:00:00.000Z', immich_updated_at: '2026-09-01T00:00:00.000Z', synced_at: '2026-09-05T20:00:00.000Z',
  }));
}

function seedTags(): DemoTagRecord[] {
  return [
    ['People', 'people', '#8ab4f8'], ['Vacation', 'vacation', '#f7c66b'], ['Review', 'review', null], ['Keep', 'keep', '#81c995'],
  ].map(([name, value, color], index) => ({ id: uuidFor(920000 + index), tag_name: name!, tag_value: value!, color, asset_count: 0, synced_at: '2026-09-05T20:00:00.000Z' }));
}

const initialState = buildStateFromTrashIds(initialTrashIds());

export const demoAssetState = $state({
  assets: initialState.assets,
  trash_api_items: initialState.trash_api_items,
  albums: seedAlbums(),
  album_assets: [] as DemoAlbumAssetRecord[],
  tags: seedTags(),
  tag_assets: [] as DemoTagAssetRecord[],
  initialized: false,
  revision: 0,
});

export function initializeDemoAssetState(): void {
  if (demoAssetState.initialized) return;
  demoAssetState.initialized = true;
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const persisted = JSON.parse(raw) as PersistedDemoState;
    if (persisted.version !== 2 || !Array.isArray(persisted.trash_api_ids)) return;
    const rebuilt = buildStateFromTrashIds(new Set(persisted.trash_api_ids));
    for (const asset of rebuilt.assets) {
      const override = persisted.asset_overrides?.[asset.id];
      if (!override) continue;
      asset.is_favorite = Boolean(override.is_favorite);
      asset.is_archived = Boolean(override.is_archived);
    }
    for (const item of rebuilt.trash_api_items) {
      const override = persisted.asset_overrides?.[item.id];
      if (!override) continue;
      item.is_favorite = Boolean(override.is_favorite);
      item.is_archived = Boolean(override.is_archived);
    }
    demoAssetState.assets = rebuilt.assets;
    demoAssetState.trash_api_items = rebuilt.trash_api_items;
    demoAssetState.revision += 1;
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
  }
}

function persist(): void {
  demoAssetState.revision += 1;
  if (typeof sessionStorage === 'undefined') return;
  const overrides: Record<string, DemoAssetOverride> = {};
  for (const asset of demoAssetState.assets) {
    const base = baseAssetsById.get(asset.id);
    if (!base) continue;
    if (asset.is_favorite !== base.is_favorite || asset.is_archived !== base.is_archived) {
      overrides[asset.id] = { is_favorite: asset.is_favorite, is_archived: asset.is_archived };
    }
  }
  for (const item of demoAssetState.trash_api_items) {
    const base = baseAssetsById.get(item.id);
    if (!base) continue;
    if (item.is_favorite !== base.is_favorite || item.is_archived !== base.is_archived) {
      overrides[item.id] = { is_favorite: item.is_favorite, is_archived: item.is_archived };
    }
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
    version: 2,
    asset_overrides: overrides,
    trash_api_ids: demoAssetState.trash_api_items.map((asset) => asset.id),
  } satisfies PersistedDemoState));
}

export function resetDemoAssetState(): void {
  const rebuilt = buildStateFromTrashIds(initialTrashIds());
  demoAssetState.assets = rebuilt.assets;
  demoAssetState.trash_api_items = rebuilt.trash_api_items;
  demoAssetState.album_assets = [];
  demoAssetState.tag_assets = [];
  demoAssetState.revision += 1;
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  }
}

export function indexedDemoAssets(): DemoAssetRecord[] {
  return demoAssetState.assets;
}

export function trashApiDemoAssets(): DemoTrashApiAsset[] {
  return demoAssetState.trash_api_items;
}

export function demoAssetById(id: string): DemoAssetRecord | undefined {
  return demoAssetState.assets.find((asset) => asset.id === id);
}

export function selectedDemoAssetIds(selection: AssetSelectionState<string>, matchingIds: readonly string[]): string[] {
  if (selection.allMatchingSelected) return matchingIds.filter((id) => !selection.excludedIds.has(id));
  return matchingIds.filter((id) => selection.selectedIds.has(id));
}

function mutateIndexedAssets(ids: readonly string[], mutate: (asset: DemoAssetRecord) => void): void {
  const idSet = new Set(ids);
  for (const asset of demoAssetState.assets) if (idSet.has(asset.id)) mutate(asset);
  persist();
}

export function setDemoAssetsFavorite(ids: readonly string[], favorite: boolean): void {
  mutateIndexedAssets(ids, (asset) => { asset.is_favorite = favorite; });
}

export function setDemoAssetsArchived(ids: readonly string[], archived: boolean): void {
  mutateIndexedAssets(ids, (asset) => { asset.is_archived = archived; });
}

export function trashDemoAssets(ids: readonly string[]): void {
  const idSet = new Set(ids);
  const moving = demoAssetState.assets.filter((asset) => idSet.has(asset.id));
  if (moving.length === 0) return;
  demoAssetState.assets = demoAssetState.assets.filter((asset) => !idSet.has(asset.id));
  demoAssetState.trash_api_items = [...demoAssetState.trash_api_items, ...moving.map(toTrashApiAsset)];
  demoAssetState.album_assets = demoAssetState.album_assets.filter((membership) => !idSet.has(membership.asset_id));
  demoAssetState.tag_assets = demoAssetState.tag_assets.filter((membership) => !idSet.has(membership.asset_id));
  persist();
}

export function restoreDemoTrashAssets(ids: readonly string[]): void {
  const idSet = new Set(ids);
  const restoring = demoAssetState.trash_api_items.filter((asset) => idSet.has(asset.id));
  if (restoring.length === 0) return;
  demoAssetState.trash_api_items = demoAssetState.trash_api_items.filter((asset) => !idSet.has(asset.id));
  const existing = new Set(demoAssetState.assets.map((asset) => asset.id));
  for (const item of restoring) {
    if (existing.has(item.id)) continue;
    const base = baseAssetsById.get(item.id);
    if (!base) continue;
    const refreshed = cloneAsset(base);
    refreshed.is_favorite = item.is_favorite;
    refreshed.is_archived = item.is_archived;
    refreshed.synced_at = new Date().toISOString();
    demoAssetState.assets.push(refreshed);
  }
  persist();
}

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
  is_trashed: boolean;
  is_offline: boolean;
  is_edited: boolean;
  has_metadata: boolean;
  visibility: string | null;
  live_photo_video_id: string | null;
  tags: DemoAssetTagSnapshot[];
  stack: DemoAssetStackSnapshot | null;
  synced_at: string;
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

type DemoAssetOverride = Pick<DemoAssetRecord, 'is_favorite' | 'is_archived' | 'is_trashed'>;
type PersistedDemoState = { version: 1; assets: Record<string, DemoAssetOverride> };

const STORAGE_KEY = 'immichCompanionV2DemoAssetState.v1';
const ACTIVE_ASSET_COUNT = 2418;
const TRASHED_ASSET_COUNT = 126;
const TOTAL_ASSET_COUNT = ACTIVE_ASSET_COUNT + TRASHED_ASSET_COUNT;
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

function seedAssets(): DemoAssetRecord[] {
  return Array.from({ length: TOTAL_ASSET_COUNT }, (_, index) => {
    const isVideo = index % 11 === 0;
    const isTrashed = index >= ACTIVE_ASSET_COUNT;
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
      is_trashed: isTrashed,
      is_offline: false,
      is_edited: index % 17 === 0,
      has_metadata: true,
      visibility: null,
      live_photo_video_id: null,
      tags: [],
      stack: null,
      synced_at: '2026-09-05T20:00:00.000Z',
    };
  });
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

export const demoAssetState = $state({
  assets: seedAssets(),
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
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const persisted = JSON.parse(raw) as PersistedDemoState;
    if (persisted.version !== 1 || !persisted.assets) return;
    for (const asset of demoAssetState.assets) {
      const override = persisted.assets[asset.id];
      if (!override) continue;
      asset.is_favorite = Boolean(override.is_favorite);
      asset.is_archived = Boolean(override.is_archived);
      asset.is_trashed = Boolean(override.is_trashed);
    }
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
    const index = Number.parseInt(asset.id.slice(-12), 16) - 1;
    const baseFavorite = index % 7 === 0;
    const baseArchived = index % 13 === 0;
    const baseTrashed = index >= ACTIVE_ASSET_COUNT;
    if (asset.is_favorite !== baseFavorite || asset.is_archived !== baseArchived || asset.is_trashed !== baseTrashed) {
      overrides[asset.id] = { is_favorite: asset.is_favorite, is_archived: asset.is_archived, is_trashed: asset.is_trashed };
    }
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, assets: overrides } satisfies PersistedDemoState));
}

export function resetDemoAssetState(): void {
  demoAssetState.assets = seedAssets();
  demoAssetState.album_assets = [];
  demoAssetState.tag_assets = [];
  demoAssetState.revision += 1;
  if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(STORAGE_KEY);
}

export function activeDemoAssets(): DemoAssetRecord[] {
  return demoAssetState.assets.filter((asset) => !asset.is_trashed);
}

export function trashedDemoAssets(): DemoAssetRecord[] {
  return demoAssetState.assets.filter((asset) => asset.is_trashed);
}

export function demoAssetById(id: string): DemoAssetRecord | undefined {
  return demoAssetState.assets.find((asset) => asset.id === id);
}

export function selectedDemoAssetIds(selection: AssetSelectionState<string>, matchingIds: readonly string[]): string[] {
  if (selection.allMatchingSelected) return matchingIds.filter((id) => !selection.excludedIds.has(id));
  return matchingIds.filter((id) => selection.selectedIds.has(id));
}

function mutateAssets(ids: readonly string[], mutate: (asset: DemoAssetRecord) => void): void {
  const idSet = new Set(ids);
  for (const asset of demoAssetState.assets) if (idSet.has(asset.id)) mutate(asset);
  persist();
}

export function setDemoAssetsFavorite(ids: readonly string[], favorite: boolean): void {
  mutateAssets(ids, (asset) => { asset.is_favorite = favorite; });
}

export function setDemoAssetsArchived(ids: readonly string[], archived: boolean): void {
  mutateAssets(ids, (asset) => { asset.is_archived = archived; });
}

export function trashDemoAssets(ids: readonly string[]): void {
  mutateAssets(ids, (asset) => { asset.is_trashed = true; });
}

export function restoreDemoAssets(ids: readonly string[]): void {
  mutateAssets(ids, (asset) => { asset.is_trashed = false; });
}

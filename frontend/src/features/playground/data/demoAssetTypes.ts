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
export type DemoTrashRelationshipSnapshot = { album_ids: string[]; tag_ids: string[]; stack: DemoAssetStackSnapshot | null };
export type DemoAssetOverride = Pick<DemoAssetRecord, 'is_favorite' | 'is_archived'>;

export type PersistedDemoState = {
  version: 4;
  asset_overrides: Record<string, DemoAssetOverride>;
  trash_api_ids: string[];
  albums: DemoAlbumRecord[];
  tags: DemoTagRecord[];
  album_assets: DemoAlbumAssetRecord[];
  tag_assets: DemoTagAssetRecord[];
  trash_relationships: Record<string, DemoTrashRelationshipSnapshot>;
  stacks: Record<string, DemoAssetStackSnapshot | null>;
};

export type PersistedDemoStateV3 = Omit<PersistedDemoState, 'version' | 'albums' | 'tags' | 'trash_relationships'> & { version: 3 };

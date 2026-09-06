export type AssetTag = { id: string; name: string; value: string; color: string | null };
export type AssetStack = { id: string; primaryAssetId: string; assetCount: number; assets: string[] };

export type AssetRecord = {
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
  tags: AssetTag[];
  stack: AssetStack | null;
  synced_at: string;
};

export type TrashAssetRecord = {
  id: string;
  type: AssetRecord['asset_type'];
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

export type AlbumRecord = {
  id: string;
  album_name: string;
  description: string;
  album_thumbnail_asset_id: string | null;
  asset_count: number;
  immich_created_at: string;
  immich_updated_at: string;
  synced_at: string;
};

export type TagRecord = {
  id: string;
  tag_name: string;
  tag_value: string;
  color: string | null;
  asset_count: number;
  synced_at: string;
};

export type AlbumAssetRecord = { album_id: string; asset_id: string };
export type TagAssetRecord = { tag_id: string; asset_id: string };

export type MutationFailure = { id: string; reason: string };
export type MutationResult = { affectedIds: string[]; failed: MutationFailure[] };

export type LibraryDataSnapshot = {
  readonly revision: number;
  readonly assets: AssetRecord[];
  readonly trash: TrashAssetRecord[];
  readonly albums: AlbumRecord[];
  readonly albumAssets: AlbumAssetRecord[];
  readonly tags: TagRecord[];
  readonly tagAssets: TagAssetRecord[];
};

export interface AssetRepository {
  list(): AssetRecord[];
  getById(id: string): AssetRecord | undefined;
  listTrash(): TrashAssetRecord[];
  setFavorite(ids: readonly string[], favorite: boolean): Promise<MutationResult>;
  setArchived(ids: readonly string[], archived: boolean): Promise<MutationResult>;
  sync(ids: readonly string[]): Promise<MutationResult>;
  trash(ids: readonly string[]): Promise<MutationResult>;
  restore(ids: readonly string[]): Promise<MutationResult>;
  addToAlbum(ids: readonly string[], albumId: string): Promise<MutationResult>;
  removeFromAlbums(ids: readonly string[], albumIds?: readonly string[]): Promise<MutationResult>;
  addTags(ids: readonly string[], tagIds: readonly string[]): Promise<MutationResult>;
  removeTags(ids: readonly string[], tagIds?: readonly string[]): Promise<MutationResult>;
  stack(ids: readonly string[]): Promise<MutationResult>;
  unstack(ids: readonly string[]): Promise<MutationResult>;
  setStackPrimary(assetId: string): Promise<MutationResult>;
  removeCompleteStack(assetId: string): Promise<MutationResult>;
}

export interface AlbumRepository {
  list(): AlbumRecord[];
  create(name: string, description?: string): Promise<AlbumRecord | undefined>;
  update(id: string, patch: { name?: string; description?: string }): Promise<MutationResult>;
  delete(ids: readonly string[]): Promise<MutationResult>;
}

export interface TagRepository {
  list(): TagRecord[];
  create(name: string, color?: string | null, parentPath?: string): Promise<TagRecord | undefined>;
  update(id: string, patch: { name?: string; color?: string | null; parentPath?: string }): Promise<MutationResult>;
  delete(ids: readonly string[]): Promise<MutationResult>;
}

export interface MediaRepository {
  thumbnail(asset: Pick<AssetRecord, 'id' | 'original_file_name' | 'width' | 'height' | 'asset_type'> | TrashAssetRecord): string;
  fullSize(asset: Pick<AssetRecord, 'id' | 'original_file_name' | 'width' | 'height' | 'asset_type'> | TrashAssetRecord): string;
}

export interface LibraryDataSource {
  readonly kind: 'demo' | 'api';
  readonly state: LibraryDataSnapshot;
  readonly assets: AssetRepository;
  readonly albums: AlbumRepository;
  readonly tags: TagRepository;
  readonly media: MediaRepository;
  initialize(): Promise<void>;
}

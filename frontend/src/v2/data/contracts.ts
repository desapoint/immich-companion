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

export type TagHierarchyRow = {
  id: string;
  name: string;
  path: string;
  parent: string;
  assets: number;
  children: number;
  color: string | null;
  synthetic: boolean;
  realTagIds: string[];
};

export type MutationFailure = { id: string; reason: string };
export type MutationResult = { affectedIds: string[]; failed: MutationFailure[] };
export type DifferenceOptions = { hue?: number; contrast?: number; binary?: boolean };
export type PageRequest = { page: number; pageSize: number };
export type PageResult<T> = { items: T[]; total: number; page: number; pageSize: number };

export type AssetSearchRule = { field: string; op: string; value: string };
export type AssetSearchGroup = { logic: 'AND' | 'OR'; negated: boolean; rules: AssetSearchRule[] };
export type AssetSort = { field: 'takenDate' | 'filename'; direction: 'asc' | 'desc' };
export type AssetSimpleSearch = {
  filename?: string;
  mediaType?: 'Image' | 'Video' | '';
  favorite?: 'Favorite' | 'Not favorite' | '';
  archived?: 'Archived' | 'Not archived' | '';
  albumIds?: string[];
  tagIds?: string[];
  noAlbum?: boolean;
  noTag?: boolean;
  takenAfter?: string;
  takenBefore?: string;
  minWidth?: string;
  maxWidth?: string;
  minHeight?: string;
  maxHeight?: string;
  minAspectRatio?: string;
  maxAspectRatio?: string;
};
export type AssetSearchCriteria =
  | { mode: 'simple'; filters: AssetSimpleSearch; sort: AssetSort }
  | { mode: 'expert'; rules: AssetSearchRule[]; groups: AssetSearchGroup[]; logic: 'AND' | 'OR'; negated: boolean; sort: AssetSort };
export type AssetSearchQuery = AssetSearchCriteria & PageRequest;
export type TrashSearchQuery = PageRequest & { sort: { field: 'deletedAt' | 'takenAt' | 'name'; direction: 'asc' | 'desc' } };
export type AlbumSearchQuery = PageRequest & { query?: string; sort: { field: 'name' | 'assets' | 'description'; direction: 'asc' | 'desc' } };
export type TagSearchQuery = PageRequest & { query?: string; includeHierarchy?: boolean; sort: { field: 'name' | 'path' | 'assets' | 'children'; direction: 'asc' | 'desc' } };
export type RelationshipPresence = { assetId: string; hasTags: boolean; hasAlbums: boolean };

export interface AssetRepository {
  getById(id: string): Promise<AssetRecord | undefined>;
  getMany(ids: readonly string[]): Promise<AssetRecord[]>;
  search(query: AssetSearchQuery): Promise<PageResult<AssetRecord>>;
  searchIds(criteria: AssetSearchCriteria): Promise<string[]>;
  searchTrash(query: TrashSearchQuery): Promise<PageResult<TrashAssetRecord>>;
  searchTrashIds(): Promise<string[]>;
  relationshipPresence(ids: readonly string[]): Promise<RelationshipPresence[]>;
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
  search(query: AlbumSearchQuery): Promise<PageResult<AlbumRecord>>;
  getById(id: string): Promise<AlbumRecord | undefined>;
  create(name: string, description?: string): Promise<AlbumRecord | undefined>;
  update(id: string, patch: { name?: string; description?: string }): Promise<MutationResult>;
  delete(ids: readonly string[]): Promise<MutationResult>;
}

export interface TagRepository {
  search(query: TagSearchQuery): Promise<PageResult<TagHierarchyRow>>;
  getById(id: string): Promise<TagRecord | undefined>;
  parentOptions(excludeTagId?: string): Promise<Array<{ value: string; label: string; subtitle: string }>>;
  create(name: string, color?: string | null, parentPath?: string): Promise<TagRecord | undefined>;
  update(id: string, patch: { name?: string; color?: string | null; parentPath?: string }): Promise<MutationResult>;
  delete(ids: readonly string[]): Promise<MutationResult>;
}

export interface MediaRepository {
  thumbnail(asset: Pick<AssetRecord, 'id' | 'original_file_name' | 'width' | 'height' | 'asset_type'> | TrashAssetRecord): string;
  fullSize(asset: Pick<AssetRecord, 'id' | 'original_file_name' | 'width' | 'height' | 'asset_type'> | TrashAssetRecord): string;
  difference(selected: AssetRecord, reference: AssetRecord, options?: DifferenceOptions): string;
}

export interface LibraryDataSource {
  readonly kind: 'demo' | 'api';
  readonly assets: AssetRepository;
  readonly albums: AlbumRepository;
  readonly tags: TagRepository;
  readonly media: MediaRepository;
  initialize(): Promise<void>;
}

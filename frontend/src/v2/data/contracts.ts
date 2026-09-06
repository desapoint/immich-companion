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

export type AlbumCreateInput = { name: string; description?: string };
export type AlbumUpdateInput = { name?: string; description?: string };
export type TagCreateInput = { name: string; color?: string | null; parentPath?: string };
export type TagUpdateInput = { name?: string; color?: string | null; parentPath?: string };
export type AlbumCreateArgs = [name: string, description?: string];
export type TagCreateArgs = [name: string, color?: string | null, parentPath?: string];

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
export type MediaDelivery = 'original' | 'thumbnail' | 'preview' | 'decoded' | 'transcoded' | 'difference';
export type MediaPurpose = 'thumbnail' | 'view';
export type MediaResource = {
  url: string;
  mimeType: string | null;
  posterUrl: string | null;
  delivery: MediaDelivery;
  originalMimeType: string | null;
  expiresAt: string | null;
};

export type CollectionRequest = {
  pageSize: number;
  page?: number;
  cursor?: string | null;
};

export type PageResult<T> = {
  items: T[];
  total: number;
  pageSize: number;
  page?: number;
  nextCursor: string | null;
};

export type RelationOption = { value: string; label: string; subtitle: string };
export type OptionSearchQuery = { query?: string; pageSize: number; cursor?: string | null };
export type OptionSearchResult = { items: RelationOption[]; nextCursor: string | null };

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

export type AssetSearchQuery = AssetSearchCriteria & CollectionRequest;
export type TrashSearchCriteria = { sort: { field: 'deletedAt' | 'takenAt' | 'name'; direction: 'asc' | 'desc' } };
export type TrashSearchQuery = TrashSearchCriteria & CollectionRequest;
export type AlbumSearchQuery = CollectionRequest & { query?: string; sort: { field: 'name' | 'assets' | 'description'; direction: 'asc' | 'desc' } };
export type TagSearchQuery = CollectionRequest & { query?: string; includeHierarchy?: boolean; sort: { field: 'name' | 'path' | 'assets' | 'children'; direction: 'asc' | 'desc' } };

export type AssetSelectionTarget =
  | { kind: 'ids'; ids: string[] }
  | { kind: 'query'; criteria: AssetSearchCriteria; excludedIds: string[] };

export type TrashSelectionTarget =
  | { kind: 'ids'; ids: string[] }
  | { kind: 'all'; excludedIds: string[] };

export type AssetSelectionCapabilities = {
  count: number;
  allFavorite: boolean;
  allArchived: boolean;
  hasTags: boolean;
  hasAlbums: boolean;
  hasStackMembers: boolean;
  canStack: boolean;
  singleAssetId: string | null;
  canSetStackPrimary: boolean;
  canRemoveCompleteStack: boolean;
};

export type DuplicateState = 'Actionable' | 'Needs review' | 'Needs decisions' | 'Blocked';
export type DuplicateDecision = 'keep' | 'delete' | 'stack';
export type DuplicateMemberRecord = { asset: AssetRecord; similarity: number };
export type DuplicateGroupRecord = {
  id: number;
  state: DuplicateState;
  kind: string;
  members: DuplicateMemberRecord[];
};
export type DuplicateSearchQuery = CollectionRequest & { state?: DuplicateState | 'All groups' | 'Auto-ready' };
export type DuplicateCapabilities = {
  canRunDiscovery: boolean;
  canApplyDecisions: boolean;
  canViewHistory: boolean;
  reviewFilters: Array<DuplicateState | 'All groups' | 'Auto-ready'>;
  decisions: DuplicateDecision[];
};
export type DuplicateDiscoveryOptions = { similarityThreshold: number; includeSimilar: boolean; includeExact: boolean; maxCandidates: number };
export type DuplicateDiscoveryResult = { groupCount: number; candidateCount: number };
export type DuplicateHistoryRecord = { id: string; occurredAt: string; groupLabel: string; summary: string };
export type DuplicateHistoryQuery = CollectionRequest & { range: 'Last 30 days' | 'Last 90 days' | 'All history' };

export interface CrudRepository<TRecord, TCreateArgs extends unknown[], TUpdateInput> {
  getById(id: string): Promise<TRecord | undefined>;
  create(...args: TCreateArgs): Promise<TRecord | undefined>;
  update(id: string, patch: TUpdateInput): Promise<MutationResult>;
  delete(ids: readonly string[]): Promise<MutationResult>;
}

export interface AssetRepository {
  getById(id: string): Promise<AssetRecord | undefined>;
  getMany(ids: readonly string[]): Promise<AssetRecord[]>;
  getTrashById(id: string): Promise<TrashAssetRecord | undefined>;
  search(query: AssetSearchQuery): Promise<PageResult<AssetRecord>>;
  searchTrash(query: TrashSearchQuery): Promise<PageResult<TrashAssetRecord>>;
  selectionCapabilities(target: AssetSelectionTarget): Promise<AssetSelectionCapabilities>;
  setFavorite(target: AssetSelectionTarget, favorite: boolean): Promise<MutationResult>;
  setArchived(target: AssetSelectionTarget, archived: boolean): Promise<MutationResult>;
  sync(target: AssetSelectionTarget): Promise<MutationResult>;
  trash(target: AssetSelectionTarget): Promise<MutationResult>;
  restore(target: TrashSelectionTarget): Promise<MutationResult>;
  addToAlbum(target: AssetSelectionTarget, albumId: string): Promise<MutationResult>;
  removeFromAlbums(target: AssetSelectionTarget, albumIds?: readonly string[]): Promise<MutationResult>;
  addTags(target: AssetSelectionTarget, tagIds: readonly string[]): Promise<MutationResult>;
  removeTags(target: AssetSelectionTarget, tagIds?: readonly string[]): Promise<MutationResult>;
  stack(target: AssetSelectionTarget): Promise<MutationResult>;
  unstack(target: AssetSelectionTarget): Promise<MutationResult>;
  setStackPrimary(assetId: string): Promise<MutationResult>;
  removeCompleteStack(assetId: string): Promise<MutationResult>;
}

export interface AlbumRepository extends CrudRepository<AlbumRecord, AlbumCreateArgs, AlbumUpdateInput> {
  search(query: AlbumSearchQuery): Promise<PageResult<AlbumRecord>>;
  searchOptions(query: OptionSearchQuery): Promise<OptionSearchResult>;
}

export interface TagRepository extends CrudRepository<TagRecord, TagCreateArgs, TagUpdateInput> {
  search(query: TagSearchQuery): Promise<PageResult<TagHierarchyRow>>;
  searchOptions(query: OptionSearchQuery): Promise<OptionSearchResult>;
  parentOptions(excludeTagId?: string): Promise<Array<{ value: string; label: string; subtitle: string }>>;
}

export interface DuplicateRepository {
  capabilities(): Promise<DuplicateCapabilities>;
  search(query: DuplicateSearchQuery): Promise<PageResult<DuplicateGroupRecord>>;
  runDiscovery(options: DuplicateDiscoveryOptions): Promise<DuplicateDiscoveryResult>;
  applyDecisions(decisions: Record<string, DuplicateDecision>): Promise<MutationResult>;
  history(query: DuplicateHistoryQuery): Promise<PageResult<DuplicateHistoryRecord>>;
}

type MediaAsset = Pick<AssetRecord, 'id' | 'original_file_name' | 'original_mime_type' | 'width' | 'height' | 'asset_type'> | TrashAssetRecord;

export interface MediaRepository {
  thumbnail(asset: MediaAsset): MediaResource;
  view(asset: MediaAsset): MediaResource;
  difference(selected: AssetRecord, reference: AssetRecord, options?: DifferenceOptions): Promise<MediaResource>;
  refresh(asset: MediaAsset, purpose: MediaPurpose): Promise<MediaResource>;
}

export interface LibraryDataSource {
  readonly kind: 'demo' | 'api';
  readonly assets: AssetRepository;
  readonly albums: AlbumRepository;
  readonly tags: TagRepository;
  readonly duplicates: DuplicateRepository;
  readonly media: MediaRepository;
  initialize(): Promise<void>;
}
